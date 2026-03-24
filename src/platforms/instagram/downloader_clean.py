"""
Instagram 下载器实现
基于 instaloader 实现 Instagram 内容下载
"""
import os
from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect
from instaloader import Instaloader, ConnectionException
from typing import List, Any

from ...core.interfaces import IDownloader
from ...core.models import Account, Post, DownloadResult
from ...utils.logger import Logger


class InstagramDownloader(IDownloader):
    """Instagram 下载器"""
    
    def __init__(self):
        self.loader = None
        self.logger = None

    def get_cookiefile(self):
        """获取 Firefox cookies 文件路径"""
        if system() == "Windows":
            # Windows Firefox cookies 路径
            firefox_dir = os.path.join(expanduser("~"), "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
            for profile in glob(os.path.join(firefox_dir, "*")):
                if os.path.isdir(profile):
                    cookiefile = os.path.join(profile, "cookies.sqlite")
                    if os.path.exists(cookiefile):
                        return cookiefile
        else:
            # Linux/Mac Firefox cookies 路径
            firefox_dir = os.path.join(expanduser("~"), ".mozilla", "firefox")
            for profile in glob(os.path.join(firefox_dir, "*")):
                if os.path.isdir(profile):
                    cookiefile = os.path.join(profile, "cookies.sqlite")
                    if os.path.exists(cookiefile):
                        return cookiefile
        return None

    def get_session_file_path(self, username: str) -> str:
        """获取 session 文件路径"""
        session_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(session_dir, exist_ok=True)
        return os.path.join(session_dir, f"{username}_session")

    def validate_login(self, cookiefile, input_username):
        """验证登录状态"""
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

    def login(self, account: Account) -> bool:
        """登录 Instagram 账号"""
        self.logger = Logger(account.name)
        
        try:
            # 创建安全的 Instaloader 实例，限制请求频率
            self.loader = Instaloader(
                max_connection_attempts=3,  # 最大连接尝试次数
                request_timeout=10,         # 请求超时时间
                rate_control_sleep_min=1,   # 最小睡眠时间
                rate_control_sleep_max=3    # 最大睡眠时间
            )
            
            # 尝试从 session 文件登录
            session_file = self.get_session_file_path(account.username)
            if os.path.exists(session_file):
                self.loader.load_session_from_file(account.username, session_file)
                if self.loader.test_login() == account.username:
                    self.logger.success(f"从 session 文件登录成功: {account.username}")
                    return True
            
            # 尝试从 Firefox cookies 登录
            cookiefile = self.get_cookiefile()
            if self.validate_login(cookiefile, account.username):
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
                self.loader.save_session_to_file(session_file)
                self.logger.success(f"从 Firefox cookies 登录成功: {account.username}")
                return True
            
            self.logger.error(f"登录失败: {account.username}")
            return False
            
        except Exception as e:
            self.logger.error(f"登录过程出错: {e}")
            return False

    def get_post_owner(self, post) -> str:
        """获取帖子所有者"""
        try:
            if hasattr(post, 'owner_username'):
                return post.owner_username
            elif hasattr(post, 'owner') and hasattr(post.owner, 'username'):
                return post.owner.username
            else:
                return "unknown"
        except Exception as e:
            self.logger.warning(f"无法获取帖子所有者: {e}")
            return "unknown"

    def download_posts(self, account: Account, count: int = 10) -> List[DownloadResult]:
        """下载帖子"""
        import time
        from ...utils.folder_manager import FolderManager
        
        if not self.loader or not self.logger:
            if not self.login(account):
                return [DownloadResult(success=False, posts=[], message="登录失败")]
        
        try:
            # 获取配置
            from main import load_account_config
            config = load_account_config()
            account_config = config.get(account.name, {})
            
            # 安全设置
            safety_config = account_config.get("download_safety", {})
            max_posts = safety_config.get("max_posts_per_session", 50)
            request_delay = safety_config.get("request_delay", 2)
            
            # 限制处理数量
            MAX_PROCESS_COUNT = min(count * 3, max_posts)
            
            self.logger.info(f"开始下载 {account.username} 的保存内容，限制处理 {MAX_PROCESS_COUNT} 个posts")
            
            # 初始化文件夹管理器
            folder_manager = FolderManager(account.name, account_config)
            
            # 获取保存的帖子
            profile = self.loader.check_profile_pic(account.username)
            saved_posts = profile.get_saved_posts()
            
            downloaded_count = 0
            skipped_count = 0
            failed_count = 0
            posts = []
            
            for i, post in enumerate(saved_posts):
                if i >= MAX_PROCESS_COUNT:
                    self.logger.warning(f"达到最大处理数量限制 ({MAX_PROCESS_COUNT})，停止下载")
                    break
                
                try:
                    # 检查是否已下载
                    shortcode = post.shortcode
                    if self.logger.is_downloaded(shortcode):
                        self.logger.info(f"跳过已下载: {shortcode}")
                        skipped_count += 1
                        continue
                    
                    # 获取帖子所有者
                    post_owner = self.get_post_owner(post)
                    
                    # 获取下载文件夹
                    download_folder = folder_manager.get_download_folder(post_owner)
                    os.makedirs(download_folder, exist_ok=True)
                    
                    # 下载帖子
                    self.loader.download_post(post, target=download_folder)
                    
                    # 记录下载成功
                    post_obj = Post(
                        shortcode=shortcode,
                        url=f"https://www.instagram.com/p/{shortcode}/",
                        caption=post.caption or "",
                        date=post.date_utc
                    )
                    posts.append(post_obj)
                    
                    self.logger.log_download(shortcode, download_folder, "success")
                    downloaded_count += 1
                    
                    self.logger.success(f"下载成功 ({downloaded_count}/{MAX_PROCESS_COUNT}): {shortcode}")
                    
                    # 安全延迟
                    time.sleep(request_delay)
                    
                except Exception as e:
                    self.logger.error(f"下载失败 {post.shortcode}: {e}")
                    failed_count += 1
            
            # 统计信息
            self.logger.info(f"下载完成: 成功 {downloaded_count}, 跳过 {skipped_count}, 失败 {failed_count}")
            
            return [DownloadResult(
                success=True,
                posts=posts,
                message=f"成功下载 {downloaded_count} 个帖子，跳过 {skipped_count} 个，失败 {failed_count} 个"
            )]
            
        except Exception as e:
            self.logger.error(f"下载过程出错: {e}")
            return [DownloadResult(success=False, posts=[], message=str(e))]

    def setup_session(self, account_name: str) -> bool:
        """设置下载会话"""
        # 从配置文件加载账号信息
        from main import load_account_config, create_account_from_config
        config = load_account_config()
        account = create_account_from_config(account_name, config)
        return self.login(account)
    
    def download_saved_posts(self, account_name: str, limit: int = None) -> List[Any]:
        """下载保存的帖子"""
        # 从配置文件加载账号信息
        from main import load_account_config, create_account_from_config
        config = load_account_config()
        account = create_account_from_config(account_name, config)
        
        # 设置默认限制
        if limit is None:
            limit = 10
            
        return self.download_posts(account, limit)
