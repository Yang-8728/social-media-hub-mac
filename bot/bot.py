"""
Telegram Bot — 调度中心。
只负责：收消息 → 路由命令 → 分发到 pipelines / 处理交互队列回复。
"""
import sys, os, time, threading, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.tg_client import BOT_TOKEN, CHAT_ID
from bot import tg_client as tg
from bot import interaction_queue as iq
import pipelines.instagram_to_bili as instagram_to_bili
import pipelines.quark_share as quark_share
import pipelines.youtube_to_wechat as wechat_pipeline
from bot.handlers import bilibili_comments
from bot.handlers.bilibili_comments import add_keyword

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── 队列消费线程：负责把待确认消息逐条发给用户 ────────────────────────────────

def _queue_dispatcher():
    """持续从队列取消息，发给用户，标记为 pending，等 resolve() 被调用后取下一条。"""
    while True:
        item = iq.pop()          # 阻塞等待
        iq.set_pending(item)
        mid = tg.send(item["message"], no_preview=item.get("no_preview", False))
        if mid and item.get("on_sent"):
            try:
                item["on_sent"](mid)
            except Exception:
                pass
        # 等 resolve() 在回调里把 pending 清掉后，自然进入下一次 pop()
        while iq.has_pending():
            time.sleep(0.2)


# ── 获取 Telegram updates ─────────────────────────────────────────────────────

def _get_updates(offset=None):
    resp = requests.get(f"{BASE_URL}/getUpdates",
                        params={"timeout": 30, "offset": offset}, timeout=35)
    return resp.json().get("result", [])


# ── 主循环 ────────────────────────────────────────────────────────────────────

def main():
    print(f"[{time.strftime('%H:%M:%S')}] Bot starting...", flush=True)

    # 后台线程
    threading.Thread(target=_queue_dispatcher, daemon=True).start()
    if not os.environ.get("NO_MONITOR"):
        threading.Thread(target=bilibili_comments.run, daemon=True).start()

    # Drain pending updates so we don't replay old commands on startup
    try:
        stale = _get_updates()
        if stale:
            offset = stale[-1]["update_id"] + 1
            print(f"[{time.strftime('%H:%M:%S')}] Drained {len(stale)} stale update(s), offset={offset}", flush=True)
        else:
            offset = None
    except Exception:
        offset = None

    while True:
        try:
            updates = _get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg    = update.get("message", {})

                chat    = msg.get("chat", {})
                chat_id = str(chat.get("id"))

                # 陌生人私信 → 转发给自己
                if chat_id != str(CHAT_ID):
                    if chat.get("type") == "private":
                        text   = msg.get("text", "").strip()
                        sender = msg.get("from", {})
                        name   = sender.get("first_name", "")
                        if sender.get("last_name"):
                            name += " " + sender["last_name"]
                        username = sender.get("username", "")
                        uid      = sender.get("id", "")
                        header   = f"📩 私信 from {name}"
                        if username:
                            header += f" (@{username})"
                        header += f" [id={uid}]"
                        tg.send(f"{header}\n{text}")
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"[{time.strftime('%H:%M:%S')}] Received: {text}", flush=True)

                # ── Reply 回复 B站评论 / 私信 ────────────────────────────────
                reply_to = msg.get("reply_to_message", {})
                if reply_to:
                    reply_mid = reply_to.get("message_id")
                    target = bilibili_comments.lookup_reply_target(reply_mid)
                    print(f"[reply] mid={reply_mid} target={'found' if target else 'not found'}", flush=True)
                    if target:
                        if iq.has_pending() and target["type"] == "comment" and text.strip() in ("0", "1", "y"):
                            # Reply to an uncertain-question message: treat as IQ answer
                            iq.resolve(text)
                        elif target["type"] == "comment":
                            oid, rpid, uname = target["oid"], target["rpid"], target["uname"]
                            if text.startswith("/share "):
                                ig_user = text.split()[1]
                                def _do_share_comment(ig=ig_user, r=rpid):
                                    quark_share.run(ig, str(r))
                                threading.Thread(target=_do_share_comment, daemon=True).start()
                            else:
                                def _do_reply(t=text, o=oid, r=rpid, u=uname):
                                    from pipelines.quark_share import _reply_bilibili
                                    ok = _reply_bilibili(o, r, t)
                                    tg.send(f"✅ 已回复 {u}" if ok else "❌ 回复失败")
                                threading.Thread(target=_do_reply, daemon=True).start()
                            if iq.has_pending():
                                iq.resolve("0")
                        elif target["type"] == "dm":
                            uid, uname = target["uid"], target["uname"]
                            if text.strip() == "/share":
                                def _do_share(u=uid, n=uname):
                                    from platforms.bilibili.monitor import get_bilibili_session, _fetch_dm_history
                                    from bot.handlers.bilibili_comments import _extract_ig_from_history
                                    try:
                                        tg.send(f"🔍 正在查找 {n} 的私信中的 IG 账号...")
                                        sess = get_bilibili_session()
                                        history = _fetch_dm_history(sess, int(u), size=20)
                                        ig_names = _extract_ig_from_history(history)
                                        if not ig_names:
                                            tg.send("⚠️ 未在私信历史中找到IG账号")
                                            return
                                        safe_uname = n.replace(" ", "_")
                                        t_arg = f"dm:{u}:{safe_uname}"
                                        quark_share.run(ig_names[0], t_arg)
                                    except Exception as e:
                                        tg.send(f"❌ /share 出错: {e}")
                                threading.Thread(target=_do_share, daemon=True).start()
                            elif text.startswith("/share "):
                                ig_user = text.split()[1]
                                def _do_share_ig(u=uid, n=uname, ig=ig_user):
                                    safe_uname = n.replace(" ", "_")
                                    quark_share.run(ig, f"dm:{u}:{safe_uname}")
                                threading.Thread(target=_do_share_ig, daemon=True).start()
                            else:
                                def _do_dm(t=text, u=uid, n=uname):
                                    from platforms.bilibili.monitor import send_dm, get_bilibili_session, get_csrf
                                    try:
                                        sess = get_bilibili_session()
                                        ok = send_dm(sess, get_csrf(sess), int(u), t)
                                        tg.send(f"✅ 私信已发给 {n}" if ok else "❌ 发送失败")
                                    except Exception as e:
                                        tg.send(f"❌ 发送失败: {e}")
                                threading.Thread(target=_do_dm, daemon=True).start()
                            if iq.has_pending():
                                iq.resolve("0")
                        continue
                    else:
                        # 尝试从通知消息文本里解析 UID 和 IG 账号，兜底处理离线期间未注册的消息
                        import re as _re
                        replied_text = reply_to.get("text", "") or reply_to.get("caption", "") or ""
                        uid_m = _re.search(r'UID[：:]\s*(\d+)', replied_text)
                        ig_m  = _re.search(r'IG 账号[：:`]+\s*([A-Za-z0-9._]{3,30})', replied_text)
                        if uid_m and (text.strip() == "/share" or text.startswith("/share ")):
                            uid_val  = uid_m.group(1)
                            uname_m  = _re.search(r'✉️\s*(.+?)（UID', replied_text)
                            uname_fb = uname_m.group(1).strip() if uname_m else uid_val
                            ig_user  = text.split()[1] if text.startswith("/share ") else (ig_m.group(1) if ig_m else None)
                            if ig_user:
                                bilibili_comments.register_dm_target(reply_mid, int(uid_val), uname_fb, ig_username=ig_user)
                                def _do_share_fb(u=uid_val, n=uname_fb, ig=ig_user):
                                    quark_share.run(ig, f"dm:{u}:{n.replace(' ','_')}")
                                threading.Thread(target=_do_share_fb, daemon=True).start()
                            else:
                                tg.send("⚠️ 未能从消息中识别 IG 账号，请用 /share ig账号名 重试")
                        else:
                            tg.send("⚠️ 找不到对应的评论/私信目标，可能已超出记录范围")
                        continue

                # ── 交互回复（队列等待中）────────────────────────────────────
                if iq.has_pending():
                    iq.resolve(text)
                    continue

                # ── 命令路由 ─────────────────────────────────────────────────
                if text == "/bilibili":
                    threading.Thread(target=instagram_to_bili.run, daemon=True).start()

                elif text == "/download":
                    threading.Thread(target=instagram_to_bili.run_download, daemon=True).start()

                elif text == "/clean_comments":
                    threading.Thread(target=bilibili_comments.run_clean, daemon=True).start()

                elif text == "/auto_clean":
                    threading.Thread(target=bilibili_comments.run_auto_clean, daemon=True).start()

                elif text.startswith("/wechat "):
                    url = text[8:].strip()
                    if url:
                        threading.Thread(target=wechat_pipeline.run, args=(url,), daemon=True).start()
                    else:
                        threading.Thread(target=wechat_pipeline.run_liked, daemon=True).start()


                elif text == "/share":
                    tg.send("用法：回复粉丝私信消息后发 /share，或直接用 /share ig用户名 [rpid]")

                elif text.startswith("/share "):
                    parts = text.split()
                    ig_user = parts[1] if len(parts) > 1 else None
                    rpid = parts[2] if len(parts) > 2 else None
                    if ig_user:
                        threading.Thread(target=quark_share.run, args=(ig_user, rpid), daemon=True).start()
                    else:
                        tg.send("用法：/share ig用户名 [rpid]\nrpid 可从评论通知链接的 comment_root_id 参数获取")

                elif text.startswith("/addspam "):
                    kw = text[9:].strip()
                    if kw:
                        kws = add_keyword(kw)
                        tg.send(f"✅ 已添加关键词「{kw}」，当前自定义词库共 {len(kws)} 条")
                    else:
                        tg.send("用法：/addspam 关键词")

                elif text == "/help":
                    tg.send(
                        "可用命令：\n"
                        "/bilibili — 执行完整流程（下载 → 合并 → 上传）\n"
                        "/download — 仅下载新视频（不合并不上传）\n"
                        "/clean_comments — 扫描垃圾评论（逐条确认）\n"
                        "/auto_clean — 自动删除所有垃圾评论\n"
                        "/addspam 关键词 — 添加自定义垃圾词\n"
                        "/share ig用户名 [rpid] — 下载IG合集打包上传夸克并回复粉丝\n"
                        "/wechat — 取最新点赞 Short 上传微信视频号\n"
                        "/wechat <YouTube URL> — 指定视频上传微信视频号\n"
                        "/help — 显示此帮助"
                    )

                elif text.startswith("/"):
                    tg.send("未知命令，发送 /help 查看可用命令。")

        except Exception as e:
            err = str(e)
            if "ProxyError" in err or "SSLError" in err or "ConnectionError" in err:
                print(f"[{time.strftime('%H:%M:%S')}] 网络波动，5秒后重试", flush=True)
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
