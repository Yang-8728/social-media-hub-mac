import subprocess
import time
import re
import requests
import os

BOT_TOKEN = "8783329976:AAHtpcx-FXEARHNHAE859MeNhE7f97SoTPY"
CHAT_ID = "6930861685"  # Only accept commands from yourself
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

PROJECT_DIR = "/Users/yanglan/Code/social-media-hub"
VENV_PYTHON = "/opt/homebrew/bin/python3"


def esc(text: str) -> str:
    """Escape special chars for MarkdownV2"""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text

def send_message(text):
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2"
    })


def run_command(cmd, timeout=30, cwd=None):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or os.path.expanduser("~")
        )
        output = result.stdout or result.stderr or "(no output)"
        return output[:4000]
    except subprocess.TimeoutExpired:
        return f"Command timed out ({timeout}s)"
    except Exception as e:
        return f"Error: {e}"


def get_video_duration(video_path: str) -> str:
    """Get video duration using ffprobe"""
    try:
        result = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        seconds = float(result.stdout.strip())
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    except:
        return "unknown"


def run_vanvan_pipeline():
    """Run full ai_vanvan pipeline with real-time progress updates"""
    send_message("🚀 开始执行 ai\\_vanvan 全流程，请稍候\\.\\.\\.")

    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python3"

    # Stream output line by line for real-time progress
    proc = subprocess.Popen(
        f"{python} -u main.py --ai_vanvan",
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=PROJECT_DIR
    )

    output_lines = []
    step_sent = set()

    def maybe_send_step(line):
        """关键步骤时发 Telegram 进度消息"""
        if "步骤1" in line or "下载最新内容" in line:
            if "download" not in step_sent:
                step_sent.add("download")
                send_message("📥 第 1/3 步：正在下载最新内容\\.\\.\\.")
        elif "步骤2" in line or "合并视频" in line:
            if "merge" not in step_sent:
                step_sent.add("merge")
                send_message("🔄 第 2/3 步：正在合并视频\\.\\.\\.")
        elif "步骤3" in line or "上传最新视频" in line:
            if "upload" not in step_sent:
                step_sent.add("upload")
                send_message("📤 第 3/3 步：正在上传到 B 站\\.\\.\\.")
        elif "等待审核" in line or "还在审核中" in line:
            if "review" not in step_sent:
                step_sent.add("review")
                send_message("⏳ 视频审核中，每10秒检查一次，请耐心等待\\.\\.\\.")
        elif "审核已通过" in line:
            if "review_passed" not in step_sent:
                step_sent.add("review_passed")
                send_message("✅ 审核通过\\! 正在发章节评论并置顶\\.\\.\\.")
        elif "评论已置顶" in line:
            if "comment" not in step_sent:
                step_sent.add("comment")
                send_message("📌 章节评论已发布并置顶\\!")

    try:
        for line in proc.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"[pipeline] {line}", flush=True)
            maybe_send_step(line)
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        proc.kill()
        send_message("⏰ 流程超时（超过 1 小时），已终止")
        return

    output = "\n".join(output_lines)

    # --- Parse results ---
    downloaded = "0"
    match = re.search(r"成功下载\s*(\d+)\s*个帖子", output)
    if match:
        downloaded = match.group(1)
    elif "没有新内容需要下载" in output:
        downloaded = "0 \\(no new content\\)"

    merged = "0"
    match = re.search(r"合并完成.*?成功:\s*(\d+)", output)
    if match:
        merged = match.group(1)

    if "上传流程完成" in output:
        upload_status = "✅ 成功"
    elif "没有新的视频需要合并" in output or "无需上传" in output or "跳过上传" in output:
        upload_status = "⏭ 跳过（无新视频）"
    elif "上传失败" in output or "上传流程未完成" in output:
        upload_status = "❌ 失败"
    else:
        upload_status = "❓ 未知"

    title = "N/A"
    match = re.search(r"标题已设置:\s*(.+)", output)
    if match:
        title = esc(match.group(1).strip())

    duration = "N/A"
    match = re.search(r"找到最新视频:\s*(.+\.mp4)", output)
    if match:
        video_name = match.group(1).strip()
        find_result = subprocess.run(
            f'find "{PROJECT_DIR}" -name "{video_name}" -type f',
            shell=True, capture_output=True, text=True, timeout=10
        )
        video_path = find_result.stdout.strip().split("\n")[0]
        if video_path:
            duration = get_video_duration(video_path)

    comment_status = "✅ 已发布并置顶" if "评论已置顶" in output else ("✅ 已发布" if "评论已发送" in output else "—")

    summary = (
        f"*ai\\_vanvan 流程完成*\n\n"
        f"📥 下载：`{esc(downloaded)}` 个视频\n"
        f"🔄 合并：`{esc(merged)}` 个视频\n"
        f"⏱ 时长：`{esc(duration)}`\n"
        f"📤 上传：{esc(upload_status)}\n"
        f"🎬 标题：`{title}`\n"
        f"📌 评论：{esc(comment_status)}"
    )
    send_message(summary)


def test_vanvan_pipeline():
    """模拟流程输出，验证消息格式"""
    send_message("🧪 测试模式，不会真实下载\\.\\.\\.")

    fake_output = (
        "成功下载 3 个帖子\n"
        "合并完成 - 成功: 1, 跳过: 0, 失败: 0\n"
        "找到最新视频: test_merged_video.mp4\n"
        "标题已设置: ins海外离大谱#238\n"
        "上传流程完成！\n"
        "评论已置顶\n"
    )

    downloaded = "0"
    match = re.search(r"成功下载\s*(\d+)\s*个帖子", fake_output)
    if match:
        downloaded = match.group(1)

    merged = "0"
    match = re.search(r"合并完成.*?成功:\s*(\d+)", fake_output)
    if match:
        merged = match.group(1)

    if "上传流程完成" in fake_output:
        upload_status = "✅ 成功"
    elif "没有新的视频需要合并" in fake_output or "无需上传" in fake_output or "跳过上传" in fake_output:
        upload_status = "⏭ 跳过（无新视频）"
    elif "上传失败" in fake_output or "上传流程未完成" in fake_output:
        upload_status = "❌ 失败"
    else:
        upload_status = "❓ 未知"

    title = "N/A"
    match = re.search(r"标题已设置:\s*(.+)", fake_output)
    if match:
        title = esc(match.group(1).strip())

    comment_status = "✅ 已发布并置顶" if "评论已置顶" in fake_output else "—"

    summary = (
        f"*\[TEST\] ai\\_vanvan 流程完成*\n\n"
        f"📥 下载：`{esc(downloaded)}` 个视频\n"
        f"🔄 合并：`{esc(merged)}` 个视频\n"
        f"⏱ 时长：`N/A`\n"
        f"📤 上传：{esc(upload_status)}\n"
        f"🎬 标题：`{title}`\n"
        f"📌 评论：{esc(comment_status)}\n\n"
        f"_这是测试，没有真实执行_"
    )
    send_message(summary)


def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
    return resp.json().get("result", [])


def main():
    print(f"[{time.strftime('%H:%M:%S')}] Bot starting...", flush=True)
    send_message("Bot started on Mac!")
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})

                # Security: only respond to your own chat
                if str(msg.get("chat", {}).get("id")) != str(CHAT_ID):
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"[{time.strftime('%H:%M:%S')}] Received: {text}", flush=True)

                if text == "/bilibili":
                    try:
                        run_vanvan_pipeline()
                    except subprocess.TimeoutExpired:
                        send_message("Pipeline timed out after 1 hour")
                    except Exception as e:
                        send_message(f"Pipeline error: {e}")

                elif text == "/test":
                    try:
                        test_vanvan_pipeline()
                    except Exception as e:
                        send_message(f"Test error: {e}")

                elif text == "/help":
                    send_message(
                        "*可用命令：*\n"
                        "/bilibili — 执行完整流程（下载 → 合并 → 上传）\n"
                        "/test — 模拟测试（不真实下载）\n"
                        "/help — 显示此帮助"
                    )

                else:
                    send_message("未知命令，发送 /help 查看可用命令。")

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
