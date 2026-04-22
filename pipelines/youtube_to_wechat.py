"""
YouTube → 微信视频号流程：yt-dlp 下载 → Selenium 上传。
"""
import os, sys, time, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import tg_client as tg
from platforms.youtube.downloader import YouTubeDownloader
from platforms.wechat.uploader import WeChatUploader

PROJECT_DIR = Path(__file__).resolve().parents[1]
STATE_FILE  = PROJECT_DIR / "temp" / "wechat_state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"next_ep": 1, "uploaded": []}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_liked():
    """从 YouTube 点赞列表取最新 Short，下载并上传微信视频号。"""
    tg.send("🎬 开始微信视频号任务：获取最新点赞 Short...")

    downloader = YouTubeDownloader()

    tg.send("🔍 正在读取 YouTube 点赞列表...")
    short_url = downloader.fetch_latest_liked_short()

    if not short_url:
        tg.send("❌ 未找到点赞列表中的 Shorts，请确认 Chrome 已登录 YouTube")
        return

    state = _load_state()
    if short_url in state["uploaded"]:
        tg.send(f"⚠️ 最新点赞的 Short 已上传过，跳过\n🔗 {short_url}")
        return

    tg.send(f"📥 正在下载：{short_url}")
    last_tg_time = [0]

    def progress_cb(line):
        now = time.time()
        if now - last_tg_time[0] >= 30:
            tg.send(f"⏳ 下载中: {line.strip()}")
            last_tg_time[0] = now

    files = downloader.download(short_url, progress_callback=progress_cb)

    if not files:
        tg.send("❌ 下载失败")
        return

    ep = state["next_ep"]
    title = f"INS海外离大谱#{ep}"
    video_path = files[0]

    tg.send(f"📤 正在上传：{title}")
    uploader = WeChatUploader()
    ok = uploader.upload(video_path, title=title)

    if ok:
        state["next_ep"] = ep + 1
        state["uploaded"].append(short_url)
        _save_state(state)
        tg.send(f"✅ 上传成功：{title}")
    else:
        tg.send(f"❌ 上传失败：{title}\n请查看 Mac 上的 Chrome 窗口")


def run(url: str):
    """手动指定 URL 下载并上传到微信视频号。"""
    tg.send(f"🎬 开始处理视频号任务\n🔗 {url}")

    tg.send("📥 正在下载...")
    downloader = YouTubeDownloader()

    last_tg_time = [0]

    def progress_cb(line):
        now = time.time()
        if now - last_tg_time[0] >= 30:
            tg.send(f"⏳ 下载中: {line.strip()}")
            last_tg_time[0] = now

    files = downloader.download(url, progress_callback=progress_cb)

    if not files:
        tg.send("❌ 下载失败，未获取到视频文件")
        return

    tg.send(f"✅ 下载完成，共 {len(files)} 个文件")
    uploader = WeChatUploader()

    for i, video_path in enumerate(files, 1):
        filename = os.path.basename(video_path)
        title = os.path.splitext(filename)[0][:80]
        tg.send(f"📤 上传 {i}/{len(files)}：{filename}")
        ok = uploader.upload(video_path, title=title)
        if ok:
            tg.send(f"✅ 上传成功：{filename}")
        else:
            tg.send(f"❌ 上传失败：{filename}")
