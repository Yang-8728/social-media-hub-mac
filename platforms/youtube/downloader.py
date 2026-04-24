import os
import subprocess
from urllib.parse import urlparse, parse_qs

YT_DLP = "/opt/homebrew/bin/yt-dlp"
BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "videos", "youtube")


class YouTubeDownloader:

    def download(self, url: str, progress_callback=None) -> list:
        output_dir = self._build_output_dir(url)
        os.makedirs(output_dir, exist_ok=True)

        archive_path = os.path.join(output_dir, ".archive.txt")
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

        cmd = [
            YT_DLP,
            "--cookies-from-browser", "chrome",
            "--format", "bestvideo[height<=1080][vcodec^=avc][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
            "--merge-output-format", "mp4",
            "--download-archive", archive_path,
            "--output", output_template,
            "--print", "after_move:filepath",
            "--no-warnings",
        ]

        if self._is_playlist(url):
            cmd += ["--yes-playlist"]
        else:
            cmd += ["--no-playlist"]

        cmd.append(url)
        print(f"▶ yt-dlp 命令: {' '.join(cmd)}")

        files = []
        last_progress_line = ""

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("/") and line.endswith(".mp4"):
                files.append(line)
                print(f"✅ 已下载: {os.path.basename(line)}")
            else:
                if "%" in line and line != last_progress_line:
                    last_progress_line = line
                    print(line)
                    if progress_callback:
                        progress_callback(line)

        proc.wait()
        if proc.returncode != 0 and not files:
            print(f"❌ yt-dlp 退出码: {proc.returncode}")

        return files

    def _build_output_dir(self, url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        if "list" in qs:
            playlist_id = qs["list"][0]
            return os.path.join(BASE_DIR, playlist_id)

        return os.path.join(BASE_DIR, "singles")

    def fetch_latest_liked_short(self) -> str | None:
        """从 YouTube 点赞列表获取最新一个 Short 的 URL（时长≤60秒，需 Chrome 已登录 YouTube）"""
        cmd = [
            YT_DLP,
            "--cookies-from-browser", "chrome",
            "--flat-playlist",
            "--playlist-end", "30",
            "--print", "%(webpage_url)s\t%(duration)s",
            "--no-warnings",
            "https://www.youtube.com/playlist?list=LL",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, _ = proc.communicate()
        for line in stdout.splitlines():
            line = line.strip()
            if "\t" not in line:
                continue
            url, duration_str = line.split("\t", 1)
            try:
                if int(duration_str) <= 60:
                    return url
            except ValueError:
                continue
        return None

    def _is_playlist(self, url: str) -> bool:
        return "list=" in url
