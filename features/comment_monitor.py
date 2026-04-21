"""
B站通知监控 feature（评论、@、私信）。
- 垃圾评论：自动删除并通知
- 真实评论：转发给用户
"""
import sys, os, time, json, re, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bili_monitor
from core import tg_client as tg
from core import interaction_queue as iq

INTERVAL = 30

PROJECT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE   = os.path.join(PROJECT_DIR, "bili_cookies_ai_vanvan.json")
CUSTOM_KW_FILE = os.path.join(PROJECT_DIR, "spam_keywords_custom.json")

# ── 关键词加载 ─────────────────────────────────────────────────────────────────

def _load_custom_keywords() -> list:
    if os.path.exists(CUSTOM_KW_FILE):
        try:
            return json.load(open(CUSTOM_KW_FILE))
        except Exception:
            pass
    return []

def add_keyword(kw: str):
    """由 /addspam 命令调用，持久化新关键词"""
    kws = _load_custom_keywords()
    if kw not in kws:
        kws.append(kw)
        with open(CUSTOM_KW_FILE, "w") as f:
            json.dump(kws, f, ensure_ascii=False, indent=2)
    return kws

# ── 垃圾检测 ──────────────────────────────────────────────────────────────────

from features.spam_cleaner import SPAM_KEYWORDS, URL_RE
import re as _re
_IMG_RE = _re.compile(r'\[[^\[\]]{3,}\]')  # [xxx] 图片/贴纸标记

def _is_spam(text: str) -> str | None:
    for kw in SPAM_KEYWORDS + _load_custom_keywords():
        if kw in text:
            return f"关键词: {kw}"
    if URL_RE.search(text):
        return "含链接"
    return None

def _has_image(text: str) -> bool:
    return bool(_IMG_RE.search(text))

# ── 删除评论（通过 requests，无需 Selenium）───────────────────────────────────

def _get_session():
    if not os.path.exists(COOKIE_FILE):
        return None, None
    cookies = json.load(open(COOKIE_FILE))
    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v, domain=".bilibili.com")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    })
    csrf = cookies.get("bili_jct", "")
    return session, csrf

def _delete_comment(oid, rpid) -> bool:
    session, csrf = _get_session()
    if not session or not csrf:
        return False
    try:
        r = session.post(
            "https://api.bilibili.com/x/v2/reply/del",
            data={"oid": str(oid), "type": "1", "rpid": str(rpid), "csrf": csrf},
            timeout=10
        )
        return r.json().get("code") == 0
    except Exception:
        return False

def _blacklist_user(uid) -> bool:
    session, csrf = _get_session()
    if not session or not csrf or not uid:
        return False
    try:
        r = session.post(
            "https://api.bilibili.com/x/relation/modify",
            data={"fid": str(uid), "act": "5", "re_src": "11", "csrf": csrf},
            timeout=10
        )
        return r.json().get("code") == 0
    except Exception:
        return False

# ── 消息格式化 ────────────────────────────────────────────────────────────────

def _format_fan(item: dict) -> str | None:
    t     = item.get("type")
    uname = tg.esc(item.get("uname", "?"))

    if t == "reply":
        content = tg.esc(item.get("content", "")[:120])
        title   = tg.esc(item.get("video_title", "")[:40])
        bvid    = item.get("bvid", "")
        rpid    = item.get("rpid", "")
        comment_link = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
        msg = f"💬 *{uname}* 评论了你的视频\n"
        if title:
            msg += f"🎬 《{title}》\n"
        msg += f"📝 {content}"
        if comment_link:
            msg += f"\n🔗 [查看评论]({tg.esc(comment_link)})"
        return msg

    elif t == "at":
        content = tg.esc(item.get("content", "")[:120])
        title   = tg.esc(item.get("video_title", "")[:40])
        bvid    = item.get("bvid", "")
        rpid    = item.get("rpid", "")
        comment_link = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
        msg = f"📣 *{uname}* @了你\n"
        if title:
            msg += f"🎬 《{title}》\n"
        msg += f"📝 {content}"
        if comment_link:
            msg += f"\n🔗 [查看评论]({tg.esc(comment_link)})"
        return msg

    elif t == "dm":
        content = tg.esc(item.get("content", "")[:120])
        unread  = item.get("unread", 1)
        msg = f"✉️ *{uname}* 发来私信"
        if unread > 1:
            msg += f"（{unread}条未读）"
        if content:
            msg += f"\n📝 {content}"
        return msg

    elif t == "error":
        return f"⚠️ B站监控错误：{tg.esc(item.get('content', ''))}"

    return None

# ── 主循环 ────────────────────────────────────────────────────────────────────

def run():
    print(f"[comment_monitor] 启动，轮询间隔 {INTERVAL}s", flush=True)
    # drain：跳过5分钟前的旧通知，保留最近5分钟内的
    RECENT_SECS = 300
    boot_ts = time.time()
    total_skipped = 0
    recent_items = []
    while True:
        items = bili_monitor.poll()
        if not items:
            break
        for item in items:
            if boot_ts - item.get("ts", 0) < RECENT_SECS:
                recent_items.append(item)
            else:
                total_skipped += 1
    if total_skipped:
        print(f"[comment_monitor] 已忽略 {total_skipped} 条历史通知，从现在开始监控", flush=True)
    # 先处理启动时保留下来的近期通知
    _process_items(recent_items)

    while True:
        try:
            items = bili_monitor.poll()
            if items:
                if iq.is_interactive():
                    print(f"[comment_monitor] 交互模式中，暂存 {len(items)} 条通知", flush=True)
                else:
                    _process_items(items)
        except Exception as e:
            print(f"[comment_monitor] 异常: {e}", flush=True)
        time.sleep(INTERVAL)


def _process_items(items):
    import threading as _t
    for item in items:
        if item.get("type") not in ("reply", "at", "dm", "error"):
            continue

        content = item.get("content", "")
        spam_reason = _is_spam(content) if item.get("type") in ("reply", "at") else None

        if spam_reason:
            oid   = item.get("oid")
            rpid  = item.get("rpid")
            uid   = item.get("uid") or item.get("mid")
            uname = item.get("uname", "?")
            bvid  = item.get("bvid", "")
            comment_link = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
            ok    = _delete_comment(oid, rpid) if oid and rpid else False
            bl    = _blacklist_user(uid) if ok and uid else False
            status = "已删除" + ("＋已拉黑" if bl else "") if ok else "删除失败"
            msg = (
                f"🗑️ 自动删除垃圾评论\n"
                f"👤 {tg.esc(uname)}\n"
                f"🏷️ {tg.esc(spam_reason)}\n"
                f"📝 {tg.esc(content[:80])}\n"
                f"{'✅' if ok else '❌'} {status}"
            )
            if comment_link:
                msg += f"\n🔗 [查看评论]({tg.esc(comment_link)})"
            tg.send_md(msg)
        else:
            msg = _format_fan(item)
            if msg:
                oid  = item.get("oid")
                rpid = item.get("rpid")
                uid  = item.get("uid")
                if item.get("type") in ("reply", "at") and oid and rpid:
                    warning = "\n⚠️ *含图片内容，请注意检查*" if _has_image(content) else ""
                    ask_msg = msg + warning + "\n\n❓ 垃圾评论？1 删除\\+拉黑\\+加词库，0 跳过"
                    ev = _t.Event()
                    def _cb(ans, _oid=oid, _rpid=rpid, _uid=uid, _content=content, _ev=ev):
                        ans = ans.strip().lower()
                        if ans in ("y", "1"):
                            ok = _delete_comment(_oid, _rpid)
                            _blacklist_user(_uid) if ok and _uid else None
                            if ok:
                                add_keyword(_content[:30])
                                tg.send(f"✅ 已删除＋已拉黑，关键词「{_content[:30]}」已加入词库")
                            else:
                                tg.send("❌ 删除失败")
                        else:
                            tg.send("⏭ 已跳过")
                        _ev.set()
                    iq.push(ask_msg, _cb)
                    ev.wait()
                    ev.clear()
                else:
                    tg.send_md(msg)

        time.sleep(0.3)
