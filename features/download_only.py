"""
仅下载 feature：扫描并下载新视频，不合并不上传。
"""
import os, re, subprocess
from core import tg_client as tg
from core.config import PROJECT_DIR, VENV_PYTHON


def run():
    tg.send_md("🔍 开始扫描并下载新视频（不合并、不上传）\\.\\.\\.")

    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else "python3"
    proc = subprocess.Popen(
        f"{python} -u main.py --download --ai_vanvan --limit 50",
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=PROJECT_DIR
    )

    output_lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"[download_only] {line}", flush=True)
        proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        proc.kill()
        tg.send("⏰ 下载超时（超过10分钟），已终止")
        return

    output = "\n".join(output_lines)

    m = re.search(r"成功下载:\s*(\d+)\s*个视频", output)
    if not m:
        m = re.search(r"发现\s*(\d+)\s*个新视频", output)
    downloaded = m.group(1) if m else "0"

    if "没有新的内容" in output or "0 个新视频" in output or downloaded == "0":
        tg.send(f"✅ 扫描完成，没有新视频")
    else:
        tg.send(f"✅ 扫描完成，下载了 {downloaded} 个新视频")
