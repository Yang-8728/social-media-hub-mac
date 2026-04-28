"""
扫描最近3个视频的全部评论（含楼中楼），发到 TG TOPIC_COMMENT 带操作按钮。
用法: python3 scripts/scan_all_comments_tg.py
Closes #134
"""
import os, sys, json, time, threading

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from bot.handlers.bilibili_comments import (
    _get_session, _get_my_uid, register_reply_target, _is_spam,
)
from bot import tg_client as tg

SCAN_VIDEOS   = 3
DELAY_BETWEEN = 0.4  # 请求间隔（秒），避免触发频率限制


def _get_recent_oids(session, my_uid: str, n: int) -> list[str]:
    """
    获取最近 n 个视频的 OID（aid）。
    优先从 pending_comments.json 取（已知活跃视频），不够再调 API。
    """
    oids: list[str] = []
    seen: set[str]  = set()

    # 1. pending_comments.json（最可靠，不受频率限制）
    pending_file = os.path.join(PROJECT_DIR, "temp", "pending_comments.json")
    try:
        pending = json.load(open(pending_file))
        # 按 ts 降序取 OID
        for item in sorted(pending.values(), key=lambda x: x.get("ts", 0), reverse=True):
            oid = str(item.get("oid", ""))
            if oid and oid not in seen:
                seen.add(oid)
                oids.append(oid)
    except Exception:
        pass

    if len(oids) >= n:
        return oids[:n]

    # 2. 创作中心接口（备用）
    try:
        r = session.get(
            "https://member.bilibili.com/x/web/archives",
            params={"status": "0,1,2,3,4", "pn": 1, "ps": n, "order": "pubdate"},
            timeout=10,
        )
        items = ((r.json().get("data") or {}).get("archives")) or []
        for it in items:
            oid = str(it.get("aid", ""))
            if oid and oid not in seen:
                seen.add(oid)
                oids.append(oid)
    except Exception as e:
        print(f"[scan] 创作中心接口失败: {e}", flush=True)

    return oids[:n]


def _fetch_sub_replies(session, oid: str, root_rpid) -> list[dict]:
    """拉取某条评论的全部子回复。"""
    results = []
    pn = 1
    while True:
        try:
            r = session.get(
                "https://api.bilibili.com/x/v2/reply/reply",
                params={"oid": oid, "type": 1, "root": root_rpid, "ps": 20, "pn": pn},
                timeout=10,
            )
            subs = ((r.json().get("data") or {}).get("replies")) or []
        except Exception:
            break
        if not subs:
            break
        for s in subs:
            member  = s.get("member") or {}
            content = (s.get("content") or {}).get("message", "")
            results.append({
                "rpid":  s.get("rpid", 0),
                "uid":   str(member.get("mid", "")),
                "uname": member.get("uname", "?"),
                "text":  content,
                "root":  root_rpid,
            })
        cursor = (r.json().get("data") or {}).get("cursor") or {}
        if cursor.get("is_end", True):
            break
        pn += 1
        time.sleep(DELAY_BETWEEN)
    return results


def send_comment_to_tg(oid: str, rpid, uid: str, uname: str, text: str,
                       bvid: str, is_sub: bool = False, root_rpid=None) -> None:
    """把一条评论发到 TOPIC_COMMENT 并注册 reply target。"""
    spam_tag = _is_spam(text)
    prefix   = "🔴 " if spam_tag else ("↳ " if is_sub else "")
    label    = f"[{bvid}]" if bvid else f"[oid:{oid}]"
    uid_str  = uid or "?"
    header   = f"{prefix}{label} 👤 {uname}（uid:{uid_str}）"
    body     = text[:300] + ("…" if len(text) > 300 else "")
    msg_text = f"{header}\n{body}"

    markup = tg.inline_keyboard([[
        ("🗑️ 拉黑删除", f"ban:{oid}:{rpid}:{uid_str}"),
        ("💬 回复",     f"reply_c:{oid}:{rpid}"),
        ("⏭️ 跳过",    f"skip:{oid}:{rpid}"),
    ]])

    mid = tg.send_topic(tg.TOPIC_COMMENT, msg_text, reply_markup=markup)
    if mid:
        register_reply_target(mid, oid, rpid, uname, uid=uid_str, content=text)
    time.sleep(0.15)


def scan_video(session, oid: str, my_uid: str, bvid: str) -> int:
    """扫描单个视频的全部评论，返回发送条数。"""
    sent = 0
    pn   = 1
    print(f"[scan] 开始扫 oid={oid} bvid={bvid}", flush=True)
    while True:
        try:
            r = session.get(
                "https://api.bilibili.com/x/v2/reply",
                params={"oid": oid, "type": 1, "pn": pn, "ps": 20, "sort": 0},
                timeout=10,
            )
            data    = r.json().get("data") or {}
            replies = data.get("replies") or []
        except Exception as e:
            print(f"[scan] 获取评论页{pn}失败: {e}", flush=True)
            break

        if not replies:
            break

        for reply in replies:
            member = reply.get("member") or {}
            uid    = str(member.get("mid", ""))
            uname  = member.get("uname", "?")
            rpid   = reply.get("rpid", 0)
            text   = (reply.get("content") or {}).get("message", "")

            if uid == my_uid:
                continue

            send_comment_to_tg(oid, rpid, uid, uname, text, bvid)
            sent += 1

            # 楼中楼
            if reply.get("rcount", 0) > 0:
                subs = _fetch_sub_replies(session, oid, rpid)
                for sub in subs:
                    if sub["uid"] == my_uid:
                        continue
                    send_comment_to_tg(oid, sub["rpid"], sub["uid"], sub["uname"],
                                       sub["text"], bvid, is_sub=True, root_rpid=rpid)
                    sent += 1

        cursor_info = data.get("cursor") or {}
        if cursor_info.get("is_end", True):
            break
        pn += 1
        time.sleep(DELAY_BETWEEN)

    print(f"[scan] oid={oid} 完成，共发送 {sent} 条", flush=True)
    return sent


def main():
    session, _ = _get_session()
    if not session:
        print("❌ 找不到 cookies，请先运行 export_bili_cookies.py", flush=True)
        return

    my_uid = _get_my_uid()
    print(f"[scan] 我的 UID: {my_uid}", flush=True)

    # 先建 OID→bvid 映射（pending_comments.json 最可靠）
    bvid_map: dict[str, str] = {}
    try:
        pending = json.load(open(os.path.join(PROJECT_DIR, "temp", "pending_comments.json")))
        for item in pending.values():
            oid = str(item.get("oid", ""))
            bvid = item.get("bvid", "")
            if oid and bvid:
                bvid_map[oid] = bvid
    except Exception:
        pass

    oids = _get_recent_oids(session, my_uid, SCAN_VIDEOS)
    if not oids:
        print("❌ 获取不到最近视频列表，退出", flush=True)
        return

    print(f"[scan] 准备扫描 {len(oids)} 个视频: {oids}", flush=True)
    tg.send_topic(tg.TOPIC_COMMENT, f"🔍 开始全量扫描最近 {len(oids)} 个视频评论，请稍候…")

    total = 0
    for oid in oids:
        bvid = bvid_map.get(oid, "")
        # 尝试通过 API 获取 bvid
        if not bvid:
            try:
                r = session.get(
                    "https://api.bilibili.com/x/web-interface/view",
                    params={"aid": oid},
                    timeout=8,
                )
                bvid = (r.json().get("data") or {}).get("bvid", "")
            except Exception:
                pass
        n = scan_video(session, oid, my_uid, bvid)
        total += n
        time.sleep(1)

    tg.send_topic(tg.TOPIC_COMMENT, f"✅ 扫描完成，共发送 {total} 条评论到本话题，请逐一审核。")
    print(f"[scan] 全部完成，共发 {total} 条", flush=True)


if __name__ == "__main__":
    main()
