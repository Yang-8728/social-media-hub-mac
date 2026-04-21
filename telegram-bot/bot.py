"""
Telegram Bot — 调度中心。
只负责：收消息 → 路由命令 → 分发到 features / 处理交互队列回复。
业务逻辑全在 features/ 里。
"""
import sys, os, time, threading, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config  import BOT_TOKEN, CHAT_ID
from core         import tg_client as tg
from core         import interaction_queue as iq
import features.bili_pipeline   as bili_pipeline
import features.spam_cleaner    as spam_cleaner
import features.comment_monitor as comment_monitor
import features.download_only   as download_only
from features.comment_monitor   import add_keyword

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── 队列消费线程：负责把待确认消息逐条发给用户 ────────────────────────────────

def _queue_dispatcher():
    """持续从队列取消息，发给用户，标记为 pending，等 resolve() 被调用后取下一条。"""
    while True:
        item = iq.pop()          # 阻塞等待
        iq.set_pending(item)
        tg.send(item["message"])
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
    tg.send_md("Bot started on Mac\\!")

    # 后台线程
    threading.Thread(target=_queue_dispatcher, daemon=True).start()
    if not os.environ.get("NO_MONITOR"):
        threading.Thread(target=comment_monitor.run, daemon=True).start()

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

                if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"[{time.strftime('%H:%M:%S')}] Received: {text}", flush=True)

                # ── 交互回复（队列等待中）────────────────────────────────────
                if iq.has_pending():
                    iq.resolve(text)
                    continue

                # ── 命令路由 ─────────────────────────────────────────────────
                if text == "/bilibili":
                    threading.Thread(target=bili_pipeline.run, daemon=True).start()

                elif text == "/download":
                    threading.Thread(target=download_only.run, daemon=True).start()

                elif text == "/clean_comments":
                    threading.Thread(target=spam_cleaner.run, daemon=True).start()

                elif text == "/auto_clean":
                    threading.Thread(target=spam_cleaner.run_auto, daemon=True).start()

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
                        "/help — 显示此帮助"
                    )

                else:
                    tg.send("未知命令，发送 /help 查看可用命令。")

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
