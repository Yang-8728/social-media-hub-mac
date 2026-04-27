"""
B站通知监控模块
从 Cookie 文件轮询 B站通知 API，返回新消息列表。
"""
import os, json, time, requests
from pathlib import Path

ACCOUNT_NAME = "ai_vanvan"
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STATE_FILE = os.path.join(_PROJECT_DIR, "temp", "bili_monitor_state.json")

PROFILE_PATH = os.path.join(
    _PROJECT_DIR,
    "tools", "profiles", f"chrome_profile_{ACCOUNT_NAME}", "Default"
)

COOKIE_FILE = os.path.join(_PROJECT_DIR, "temp", f"bili_cookies_{ACCOUNT_NAME}.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

# ── Cookie 读取 ────────────────────────────────────────────────────────────────

def get_bilibili_session():
    """从 JSON 文件读取 B站 Cookie（用 export_bili_cookies.py 导出）"""
    if not os.path.exists(COOKIE_FILE):
        raise RuntimeError(
            f"Cookie 文件不存在: {COOKIE_FILE}\n"
            f"请先运行: python3 export_bili_cookies.py"
        )
    with open(COOKIE_FILE) as f:
        cookies = json.load(f)
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".bilibili.com")
    session.headers.update(HEADERS)
    return session

def get_csrf(session):
    return session.cookies.get("bili_jct", domain=".bilibili.com")

# ── 状态持久化（记录已推送的最新通知 ID，避免重复推送）─────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_reply_cursor": 0, "last_at_cursor": 0, "last_dm_session": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def update_dm_ts(new_ts: int):
    """DM 通知发送成功后才调用，避免 Telegram 失败导致通知丢失。"""
    state = load_state()
    if new_ts > state.get("last_dm_session", 0):
        state["last_dm_session"] = new_ts
        save_state(state)

# ── B站 API 调用 ───────────────────────────────────────────────────────────────

def api_get(session, url, params=None):
    try:
        r = session.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("code") == -101:  # 账号未登录
            return {"code": -101, "error": "cookie_expired"}
        return data
    except Exception as e:
        return {"error": str(e)}

# ── 拉取新评论回复通知 ─────────────────────────────────────────────────────────

def _extract_bvid(uri: str) -> str:
    import re
    m = re.search(r'/video/(BV\w+)', uri or "")
    return m.group(1) if m else ""

def fetch_new_replies(session, last_cursor):
    r = api_get(session, "https://api.bilibili.com/x/msgfeed/reply",
                params={"platform": "web", "build": 0, "mobi_app": "web"})

    if not r:
        return [], last_cursor
    if r.get("code") == -101:
        return [{"error": "cookie_expired"}], last_cursor
    if r.get("code") != 0:
        return [], last_cursor

    items = (r.get("data") or {}).get("items") or []
    max_id = max((item.get("id", 0) for item in items), default=last_cursor)
    new_cursor = max(max_id, last_cursor)

    results = []
    for item in items:
        item_id = item.get("id", 0)
        if item_id <= last_cursor:
            break

        user     = item.get("user") or {}
        sub_item = item.get("item") or {}

        results.append({
            "type":        "reply",
            "uname":       user.get("nickname", "?"),
            "uid":         user.get("mid", ""),
            "content":     sub_item.get("source_content", ""),
            "video_title": sub_item.get("title", ""),
            "bvid":        _extract_bvid(sub_item.get("uri", "")),
            "rpid":        sub_item.get("source_id", 0),
            "oid":         sub_item.get("subject_id", 0),
            "ts":          item.get("reply_time", 0),
        })

    return results, new_cursor

# ── 拉取新 @我 通知 ────────────────────────────────────────────────────────────

def fetch_new_at(session, last_cursor):
    r = api_get(session, "https://api.bilibili.com/x/msgfeed/at",
                params={"build": 0, "mobi_app": "web"})

    if not r or r.get("code") != 0:
        return [], last_cursor

    items = (r.get("data") or {}).get("items") or []
    # Use max item id from this page as new cursor (API cursor field may be missing)
    max_id = max((item.get("id", 0) for item in items), default=last_cursor)
    new_cursor = max(max_id, last_cursor)

    results = []
    for item in items:
        item_id = item.get("id", 0)
        if item_id <= last_cursor:
            break

        user     = item.get("user") or {}
        sub_item = item.get("item") or {}

        results.append({
            "type":        "at",
            "uname":       user.get("nickname", "?"),
            "uid":         user.get("mid", ""),
            "content":     sub_item.get("source_content", ""),
            "video_title": sub_item.get("title", ""),
            "bvid":        _extract_bvid(sub_item.get("uri", "")),
            "rpid":        sub_item.get("source_id", 0),
            "oid":         sub_item.get("subject_id", 0),
            "source":      sub_item.get("title", ""),
            "ts":          item.get("at_time", 0),
        })

    return results, new_cursor

# ── 拉取新私信 ─────────────────────────────────────────────────────────────────

def fetch_sub_replies(session, oid: int, rpid: int) -> list:
    """拉取某条评论的所有子回复，每条格式：{rpid, uid, uname, content}"""
    results, pn = [], 1
    while True:
        r = api_get(session, "https://api.bilibili.com/x/v2/reply/reply",
                    params={"oid": oid, "type": 1, "root": rpid, "ps": 20, "pn": pn})
        if not r or r.get("code") != 0:
            break
        replies = ((r.get("data") or {}).get("replies")) or []
        if not replies:
            break
        for rep in replies:
            member  = rep.get("member") or {}
            content = (rep.get("content") or {}).get("message", "")
            results.append({
                "rpid":    rep.get("rpid", 0),
                "uid":     member.get("mid", ""),
                "uname":   member.get("uname", "?"),
                "content": content,
            })
        cursor = (r.get("data") or {}).get("cursor") or {}
        if cursor.get("is_end", True):
            break
        pn += 1
        time.sleep(0.2)
    return results


def fetch_comment_has_images(session, oid: int, rpid: int) -> bool:
    """检查评论是否含图片附件（通知 API 的 source_content 不含此信息）"""
    r = api_get(session, "https://api.bilibili.com/x/v2/reply/info",
                params={"oid": oid, "type": 1, "root": rpid})
    if not r or r.get("code") != 0:
        return False
    content = ((r.get("data") or {}).get("reply") or {}).get("content") or {}
    return bool(content.get("pictures"))


def _fetch_uname(session, uid: int) -> str:
    r = api_get(session, "https://api.bilibili.com/x/web-interface/card",
                params={"mid": uid})
    return ((r.get("data") or {}).get("card") or {}).get("name", str(uid))


def _fetch_dm_history(session, talker_id: int, size: int = 5) -> list:
    """返回最近几条消息，每条 {"from_me": bool, "text": str}"""
    r = api_get(session, "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs",
                params={"talker_id": talker_id, "session_type": 1, "size": size})
    messages = (r.get("data") or {}).get("messages") or []
    try:
        my_uid = int(session.cookies.get("DedeUserID", domain=".bilibili.com") or 0)
    except Exception:
        my_uid = None
    result = []
    for m in reversed(messages):  # 最新的排最后
        if m.get("msg_type") != 1:
            continue
        try:
            text = json.loads(m.get("content", "{}")).get("content", "")
        except Exception:
            text = ""
        if text:
            from_me = (m.get("sender_uid") == my_uid)
            result.append({"from_me": from_me, "text": text})
    return result


def send_dm(session, csrf: str, receiver_uid: int, message: str) -> bool:
    """向指定 B站用户发送私信"""
    my_uid = None
    # 从 cookie 里拿自己的 UID
    try:
        my_uid = int(session.cookies.get("DedeUserID", domain=".bilibili.com") or 0)
    except Exception:
        pass
    try:
        r = session.post(
            "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg",
            data={
                "msg[sender_uid]":       str(my_uid or ""),
                "msg[receiver_id]":      str(receiver_uid),
                "msg[receiver_type]":    "1",
                "msg[msg_type]":         "1",
                "msg[msg_status]":       "0",
                "msg[content]":          json.dumps({"content": message}),
                "msg[timestamp]":        str(int(time.time())),
                "msg[new_face_version]": "0",
                "msg[dev_id]":           "A0E97B93-D44A-4FC5-9C55-E8F3CA4A7BD3",
                "csrf":                  csrf,
                "csrf_token":            csrf,
            },
            timeout=10,
        )
        return r.json().get("code") == 0
    except Exception:
        return False


def fetch_new_dm(session, last_session_ts):
    r = api_get(session, "https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions",
                params={"session_type": 1, "group_fold": 1, "unread_fold": 0,
                        "build": 0, "mobi_app": "web"})

    if not r or r.get("code") != 0:
        return [], last_session_ts

    sessions = (r.get("data") or {}).get("session_list") or []
    results = []
    new_ts = last_session_ts

    try:
        my_uid = int(session.cookies.get("DedeUserID", domain=".bilibili.com") or 0)
    except Exception:
        my_uid = 0

    for s in sessions:
        last_msg = s.get("last_msg") or {}
        ts = last_msg.get("timestamp", 0)
        unread = s.get("unread_count", 0)

        if ts <= last_session_ts:
            continue

        # 最后一条消息是 bot 自己发的，说明已经自动回复过，不再推送
        if my_uid and last_msg.get("sender_uid") == my_uid:
            new_ts = max(new_ts, ts)
            continue

        new_ts = max(new_ts, ts)
        talker_id = s.get("talker_id") or last_msg.get("sender_uid", 0)
        content = ""
        try:
            content = json.loads(last_msg.get("content", "{}")).get("content", "")
        except Exception:
            pass

        uname = _fetch_uname(session, talker_id)
        history = _fetch_dm_history(session, talker_id, size=10)

        results.append({
            "type":    "dm",
            "uid":     talker_id,
            "uname":   uname,
            "content": content,
            "unread":  unread,
            "history": history,
        })

    return results, new_ts

# ── 主入口：轮询一次，返回所有新通知 ──────────────────────────────────────────

def poll():
    """
    轮询一次 B站通知，返回新通知列表（可能为空）
    每条通知格式:
      {"type": "reply"|"at"|"dm", "uname": ..., "content": ..., ...}
    """
    state = load_state()

    try:
        session = get_bilibili_session()
    except RuntimeError as e:
        return [{"type": "error", "content": str(e)}]

    all_new = []

    replies, new_reply_cursor = fetch_new_replies(session, state["last_reply_cursor"])
    if replies and replies[0].get("error") == "cookie_expired":
        return [{"type": "error", "content": "⚠️ B站Cookie已过期，请在Mac上运行：python3 export_bili_cookies.py"}]
    all_new.extend(replies)
    state["last_reply_cursor"] = new_reply_cursor

    ats, new_at_cursor = fetch_new_at(session, state["last_at_cursor"])
    all_new.extend(ats)
    state["last_at_cursor"] = new_at_cursor

    dms, new_dm_ts = fetch_new_dm(session, state["last_dm_session"])
    all_new.extend(dms)
    # DM 的 ts 不在这里保存，由调用方发送成功后调用 update_dm_ts() 保存

    save_state(state)
    return all_new, new_dm_ts


if __name__ == "__main__":
    print("🔍 手动测试轮询一次...\n")
    items = poll()
    if not items:
        print("✅ 没有新通知")
    for item in items:
        t = item.get("type")
        if t == "reply":
            print(f"💬 [{item['uname']}] 评论了《{item['video_title']}》: {item['content'][:60]}")
        elif t == "at":
            print(f"@ [{item['uname']}] @了你: {item['content'][:60]}")
        elif t == "dm":
            print(f"✉️  [{item['uname']}] 私信({item['unread']}条): {item['content'][:60]}")
        elif t == "error":
            print(f"❌ 错误: {item['content']}")
