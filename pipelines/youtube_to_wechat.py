"""
YouTube → 微信视频号流程：yt-dlp 下载 → Selenium 上传。
"""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import tg_client as tg
from platforms.youtube.downloader import YouTubeDownloader
from platforms.wechat.uploader import WeChatUploader


def run(url: str):
    """下载 YouTube 视频并上传到微信视频号。由 bot.py 在后台线程调用。"""
    tg.send(f"🎬 开始处理视频号任务\n🔗 {url}")

    tg.send("📥 第 1/2 步：正在用 yt-dlp 下载视频...")
    downloader = YouTubeDownloader()

    last_tg_time = [0]

    def progress_cb(line):
        now = time.time()
        if now - last_tg_time[0] >= 30:
            tg.send(f"⏳ 下载中: {line.strip()}")
            last_tg_time[0] = now

    files = downloader.download(url, progress_callback=progress_cb)

    if not files:
        tg.send("❌ 下载失败，未获取到视频文件，请检查链接或 yt-dlp 是否已安装")
        return

    tg.send(f"✅ 下载完成，共 {len(files)} 个文件")

    uploader = WeChatUploader()
    success_count = 0

    for i, video_path in enumerate(files, 1):
        filename = os.path.basename(video_path)
        title = os.path.splitext(filename)[0][:80]
        tg.send(f"📤 第 2/2 步：上传 {i}/{len(files)}\n📄 {filename}")

        ok = uploader.upload(video_path, title=title)
        if ok:
            success_count += 1
            tg.send(f"✅ 上传成功：{filename}")
        else:
            tg.send(f"❌ 上传失败：{filename}\n请查看 Mac 上的 Chrome 窗口或 temp/ 目录下的截图")

    tg.send(f"📊 视频号任务完成\n✅ 成功 {success_count}/{len(files)} 个")
