"""
Instagram 下载器（基于 instaloader + Firefox Cookie）。
"""
import os
import sys
import contextlib
from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect
from instaloader import Instaloader, ConnectionException
from typing import List, Any

from platforms.instagram.logger import Logger
from platforms.instagram.path_utils import clean_unicode_path
from platforms.instagram.account_mapping import get_display_name


class InstagramDownloader:

    def __init__(self):
        self.loader = None
        self.logger = None

    @contextlib.contextmanager
    def suppress_instaloader_errors(self):
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            yield
        finally:
            sys.stderr = old_stderr

    def get_cookiefile(self, firefox_profile=None):
        if system() == "Darwin":
            firefox_dir = os.path.join(expanduser("~"), "Library", "Application Support", "Firefox", "Profiles")
        else:
            firefox_dir = os.path.join(expanduser("~"), ".mozilla", "firefox")

        if firefox_profile:
            profile_path = os.path.join(firefox_dir, firefox_profile)
            if os.path.isdir(profile_path):
                cookiefile = os.path.join(profile_path, "cookies.sqlite")
                if os.path.exists(cookiefile):
                    return cookiefile
            return None
        else:
            for profile in glob(os.path.join(firefox_dir, "*")):
                if os.path.isdir(profile):
                    cookiefile = os.path.join(profile, "cookies.sqlite")
                    if os.path.exists(cookiefile):
                        return cookiefile
        return None

    def get_session_file_path(self, username: str) -> str:
        session_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(session_dir, exist_ok=True)
        return os.path.join(session_dir, f"{username}_session")

    def validate_login(self, cookiefile, input_username):
        conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
        try:
            cookie_data = conn.execute(
                "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
            )
        except OperationalError:
            cookie_data = conn.execute(
                "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
            )
        loader = Instaloader(max_connection_attempts=1)
        loader.context._session.cookies.update(cookie_data)
        actual_username = loader.test_login()
        return actual_username == input_username

    def login(self, account) -> bool:
        self.logger = Logger(account.name)
        try:
            self.loader = Instaloader(
                max_connection_attempts=3,
                request_timeout=30,
                quiet=True,
                save_metadata=False,
                compress_json=False,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                sleep=True,
            )

            session_file = self.get_session_file_path(account.username)
            if os.path.exists(session_file):
                print(f"Loaded session from {session_file}.")
                self.loader.load_session_from_file(account.username, session_file)
                self.loader.context.username = account.username
                try:
                    with self.suppress_instaloader_errors():
                        if self.loader.test_login() == account.username:
                            self.logger.success(f"从 session 文件登录成功: {account.username}")
                            return True
                except Exception:
                    pass

            firefox_profile = getattr(account, 'firefox_profile', None) or (
                hasattr(account, 'config') and account.config.get('firefox_profile', None)
            )
            cookiefile = self.get_cookiefile(firefox_profile)
            if cookiefile and self.validate_login(cookiefile, account.username):
                conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
                try:
                    cookie_data = conn.execute(
                        "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
                    )
                except OperationalError:
                    cookie_data = conn.execute(
                        "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
                    )
                self.loader.context._session.cookies.update(cookie_data)
                self.loader.context.username = account.username
                self.loader.save_session_to_file(session_file)
                self.logger.success(f"从 Firefox cookies 登录成功: {account.username}")
                return True

            self.logger.error(f"登录失败: {account.username}")
            return False

        except Exception as e:
            self.logger.error(f"登录过程出错: {e}")
            return False

    def get_post_owner(self, post) -> str:
        try:
            if hasattr(post, 'owner_username'):
                return post.owner_username
            elif hasattr(post, 'owner') and hasattr(post.owner, 'username'):
                return post.owner.username
            return "unknown"
        except Exception:
            return "unknown"

    def download_posts(self, account, count: int = 10) -> List[Any]:
        import time
        from platforms.instagram.folder_manager import FolderManager

        if not self.loader or not self.logger:
            if not self.login(account):
                return [_make_result(False, message="登录失败")]

        try:
            from main import load_account_config
            config = load_account_config()
            account_config = config.get(account.name, {})

            safety_config = account_config.get("download_safety", {})
            max_posts = safety_config.get("max_posts_per_session", 20)
            request_delay = safety_config.get("request_delay", 2)

            MAX_PROCESS_COUNT = min(count, max_posts)

            self.logger.info(f"开始下载任务：{account.name}")

            sync_count = self.logger.sync_missing_downloads()
            if sync_count > 0:
                self.logger.info(f"已同步 {sync_count} 个已存在但未记录的视频")

            folder_manager = FolderManager(account.name, account_config)

            from instaloader import Profile
            profile = Profile.from_username(self.loader.context, account.username)
            saved_posts = profile.get_saved_posts()

            self.logger.info("正在扫描新视频...")
            new_videos = []
            scan_count = 0
            scan_limit = min(MAX_PROCESS_COUNT, 20)

            for post in saved_posts:
                scan_count += 1
                if scan_count > scan_limit:
                    break
                shortcode = post.shortcode
                if not self.logger.is_downloaded(shortcode):
                    new_videos.append(post)
                    if len(new_videos) >= MAX_PROCESS_COUNT:
                        break

            actual_download_count = min(len(new_videos), MAX_PROCESS_COUNT)
            self.logger.info(f"发现 {len(new_videos)} 个新视频，准备下载 {actual_download_count} 个")

            if len(new_videos) == 0:
                self.logger.info("没有新视频需要下载")
                return [_make_result(True, message="没有新视频")]

            downloaded_count = 0
            skipped_count = 0
            failed_count = 0
            start_time = time.time()

            for post in new_videos:
                if downloaded_count >= actual_download_count:
                    break
                try:
                    shortcode = post.shortcode
                    if self.logger.is_downloaded(shortcode):
                        skipped_count += 1
                        continue

                    post_owner = self.get_post_owner(post)
                    download_folder = folder_manager.get_download_folder(post_owner)
                    download_folder = clean_unicode_path(download_folder)
                    os.makedirs(download_folder, exist_ok=True)

                    files_before = set(os.listdir(download_folder))
                    print(f"🔄 开始下载 {shortcode}")
                    download_start_time = time.time()

                    import requests as _requests
                    video_url = post.video_url if post.is_video else None
                    if video_url:
                        out_path = os.path.join(download_folder, f"{shortcode}.mp4")
                        r = _requests.get(video_url, stream=True, timeout=60)
                        r.raise_for_status()
                        with open(out_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=65536):
                                f.write(chunk)
                    else:
                        self.loader.download_post(post, target=download_folder)

                    files_after = set(os.listdir(download_folder))
                    new_files = files_after - files_before
                    download_success = bool(new_files)

                    if download_success:
                        self.logger.record_download(shortcode, "success", download_folder, folder=download_folder, blogger=post_owner)
                        downloaded_count += 1
                    else:
                        self.logger.record_download(shortcode, "skipped", download_folder, error="文件未找到", folder=download_folder, blogger=post_owner)
                        skipped_count += 1

                    processed_count = downloaded_count + skipped_count
                    progress = (processed_count / actual_download_count) * 100
                    elapsed = time.time() - start_time
                    progress_bar = "█" * int(progress // 5) + "░" * (20 - int(progress // 5))
                    time_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒" if elapsed >= 60 else f"{int(elapsed)}秒"
                    print(f"\r下载进度: ({processed_count}/{actual_download_count}) [成功:{downloaded_count}] [{progress:.1f}%] [{progress_bar}] 用时: {time_str}", end="", flush=True)

                    if processed_count >= actual_download_count:
                        print()

                    time.sleep(request_delay)

                except Exception as e:
                    self.logger.error(f"下载失败: {e}")
                    failed_count += 1

            total_time = time.time() - start_time
            time_str = f"{int(total_time // 60)}分{int(total_time % 60)}秒" if total_time >= 60 else f"{int(total_time)}秒"
            print()
            self.logger.info(f"下载完成：成功 {downloaded_count}，跳过 {skipped_count}，失败 {failed_count}，用时 {time_str}")
            return [_make_result(True, message=f"成功下载 {downloaded_count} 个帖子，跳过 {skipped_count} 个，失败 {failed_count} 个，用时 {time_str}")]

        except Exception as e:
            self.logger.error(f"下载过程出错: {e}")
            return [_make_result(False, message=str(e))]


def _make_result(success: bool, message: str = ""):
    class R:
        def __init__(self, s, m): self.success = s; self.message = m; self.error = "" if s else m
    return R(success, message)
