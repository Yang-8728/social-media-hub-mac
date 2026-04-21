"""
ai_vanvan 全流程 feature（下载 → 合并 → 上传）。
"""
import os, re, subprocess, time
from core import tg_client as tg
from core.config import PROJECT_DIR, VENV_PYTHON


def _get_video_duration(video_path: str) -> str:
    try:
        result = subprocess.run(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"',
            shell=True, capture_output=True, text=True, timeout=10
        )
        seconds = float(result.stdout.strip())
        mins, secs = int(seconds // 60), int(seconds % 60)
        return f"{mins}m {secs}s"
    except:
        return "unknown"


def run():
    """由 bot.py 在后台线程调用"""
    tg.send_md("🚀 开始执行 ai\\_vanvan 全流程，请稍候\\.\\.\\.")

    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python3"
    proc   = subprocess.Popen(
        f"{python} -u main.py --ai_vanvan",
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=PROJECT_DIR
    )

    output_lines = []
    step_sent    = set()

    def maybe_step(line):
        if "步骤1" in line or "下载最新内容" in line:
            if "dl" not in step_sent:
                step_sent.add("dl"); tg.send_md("📥 第 1/3 步：正在下载最新内容\\.\\.\\.")
        elif "步骤2" in line or "合并视频" in line:
            if "mg" not in step_sent:
                step_sent.add("mg"); tg.send_md("🔄 第 2/3 步：正在合并视频\\.\\.\\.")
        elif "步骤3" in line or "上传最新视频" in line:
            if "up" not in step_sent:
                step_sent.add("up"); tg.send_md("📤 第 3/3 步：正在上传到 B 站\\.\\.\\.")
        elif "等待审核" in line or "还在审核中" in line:
            if "rv" not in step_sent:
                step_sent.add("rv"); tg.send_md("⏳ 视频审核中，每10秒检查一次\\.\\.\\.")
        elif "审核已通过" in line:
            if "rp" not in step_sent:
                step_sent.add("rp"); tg.send_md("✅ 审核通过\\! 正在发章节评论并置顶\\.\\.\\.")
        elif "评论已置顶" in line:
            if "cm" not in step_sent:
                step_sent.add("cm"); tg.send_md("📌 章节评论已发布并置顶\\!")

    try:
        for line in proc.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"[pipeline] {line}", flush=True)
            maybe_step(line)
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        proc.kill()
        tg.send_md("⏰ 流程超时（超过 1 小时），已终止")
        return

    output = "\n".join(output_lines)

    m = re.search(r"成功下载:\s*(\d+)\s*个视频", output)
    if not m:
        m = re.search(r"发现\s*(\d+)\s*个新视频", output)
    downloaded = m.group(1) if m else "0"

    m = re.search(r"准备合并\s*(\d+)\s*个视频", output)
    merged = m.group(1) if m else ("0" if "合并成功" not in output else "?")

    if "审核通过" in output or "评论已置顶" in output or "评论已发送" in output:
        upload_status = "✅ 成功"
    elif any(x in output for x in ("没有新的视频需要合并", "无需上传", "跳过上传", "发现 0 个新视频")):
        upload_status = "⏭ 跳过（无新视频）"
    elif any(x in output for x in ("上传失败", "❌ 上传失败")):
        upload_status = "❌ 失败"
    else:
        upload_status = "❓ 未知"

    m = re.search(r"📝 标题已设置:\s*(.+)", output)
    title = tg.esc(m.group(1).strip()) if m else "N/A"

    duration = "N/A"
    m = re.search(r"合并成功.*?输出文件:\s*(.+?\.mp4)", output)
    if m:
        rel_path = m.group(1).strip()
        full_path = os.path.join(PROJECT_DIR, rel_path)
        if os.path.exists(full_path):
            duration = _get_video_duration(full_path)

    comment_status = ("✅ 已发布并置顶" if "评论已置顶" in output
                      else ("✅ 已发布" if "评论已发送" in output else "—"))

    tg.send_md(
        f"*ai\\_vanvan 流程完成*\n\n"
        f"📥 下载：`{tg.esc(downloaded)}` 个视频\n"
        f"🔄 合并：`{tg.esc(merged)}` 个视频\n"
        f"⏱ 时长：`{tg.esc(duration)}`\n"
        f"📤 上传：{tg.esc(upload_status)}\n"
        f"🎬 标题：`{title}`\n"
        f"📌 评论：{tg.esc(comment_status)}"
    )
