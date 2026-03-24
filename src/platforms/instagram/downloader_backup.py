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
from typing import List

from ...core.interfaces import IDownloader
from ...core.models import Account, Post, DownloadResult
from ...utils.logger import Logger


class InstagramDownloader(IDownloader):
    """Instagram 下载器"""
    
    def __init__(self):
        self.loader = None
        self.logger = None
    
    def get_cookiefile(self):
        """获取 Firefox cookies.sqlite 文件路径"""
        default_cookiefile = {
            "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
            "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
            "Linux": "~/.mozilla/firefox/*/cookies.sqlite",
        }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")

        cookiefiles = glob(expanduser(default_cookiefile))
        if not cookiefiles:
            raise SystemExit("❌ No Firefox cookies.sqlite file found.")
        return cookiefiles[0]

    def get_session_file_path(self, username: str) -> str:
        """返回 session 文件完整路径"""
        config_dir = expanduser("~/.config/instaloader")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, f"session-{username}")

    def validate_login(self, cookiefile, input_username):
        """检查浏览器登录的 IG 账号是否匹配"""
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
            
            self.logger.error("登录失败：无法从 session 或 cookies 获取有效登录")
            return False
            
        except Exception as e:
            self.logger.error(f"登录失败: {e}")
            return False

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
from typing import List

from ...core.interfaces import IDownloader
from ...core.models import Account, Post, DownloadResult
from ...utils.logger import Logger
from ...utils.folder_manager import FolderManager


class InstagramDownloader(IDownloader):
    """Instagram 下载器"""
    
    def __init__(self):
        self.loader = None
        self.logger = None
        self.folder_manager = None
    
    def get_cookiefile(self):
        """获取 Firefox cookies.sqlite 文件路径"""
        default_cookiefile = {
            "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
            "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
            "Linux": "~/.mozilla/firefox/*/cookies.sqlite",
        }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")

        cookiefiles = glob(expanduser(default_cookiefile))
        if not cookiefiles:
            raise SystemExit("❌ No Firefox cookies.sqlite file found.")
        return cookiefiles[0]

    def get_session_file_path(self, username: str) -> str:
        """返回 session 文件完整路径"""
        config_dir = expanduser("~/.config/instaloader")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, f"session-{username}")

    def validate_login(self, cookiefile, input_username):
        """检查浏览器登录的 IG 账号是否匹配"""
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
        
        # 初始化文件夹管理器
        config = getattr(account, 'auth_data', {})
        if hasattr(account, 'config'):
            config.update(account.config)
        self.folder_manager = FolderManager(account.name, config)
        
        try:
            self.loader = Instaloader()
            
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
            
            self.logger.error("登录失败：无法从 session 或 cookies 获取有效登录")
            return False
            
        except Exception as e:
            self.logger.error(f"登录失败: {e}")
            return False

    def get_post_owner(self, post) -> str:
        """获取帖子的原作者"""
        try:
            # 尝试获取帖子的原作者
            if hasattr(post, 'owner_username'):
                return post.owner_username
            elif hasattr(post, 'owner'):
                return post.owner.username if post.owner else "unknown"
            else:
                return "unknown"
        except:
            return "unknown"

    def download_posts(self, account: Account, count: int = 10) -> List[DownloadResult]:
        """下载帖子"""
        if not self.loader:
            self.logger.error("请先登录")
            return [DownloadResult(success=False, posts=[], error="未登录")]
        
        if not self.logger:
            self.logger = Logger(account.name)
        
        if not self.folder_manager:
            config = getattr(account, 'auth_data', {})
            if hasattr(account, 'config'):
                config.update(account.config)
            self.folder_manager = FolderManager(account.name, config)
        
        self.logger.info(f"开始下载 {account.username} 的保存内容，目标数量: {count}")
        
        try:
            # 获取用户的保存内容
            profile = self.loader.profile(account.username)
            saved_posts = profile.get_saved_posts()
            
            posts = []
            downloaded_count = 0
            skipped_count = 0
            failed_count = 0
            processed_count = 0  # 添加处理计数器
            
            # 限制最大处理数量，防止请求过多
            MAX_PROCESS_COUNT = min(count * 3, 50)  # 最多处理50个，避免过度请求
            
            for post in saved_posts:
                processed_count += 1
                
                # 超过最大处理数或已下载足够数量就停止
                if downloaded_count >= count or processed_count > MAX_PROCESS_COUNT:
                    if processed_count > MAX_PROCESS_COUNT:
                        self.logger.warning(f"为避免过度请求，停止在处理第 {MAX_PROCESS_COUNT} 个帖子")
                    break
                
                # 获取帖子所有者
                post_owner = self.get_post_owner(post)
                
                # 根据策略获取下载目录
                download_dir = self.folder_manager.get_download_folder(post_owner)
                
                self.logger.info(f"处理帖子: {post.shortcode} (作者: {post_owner})")
                self.logger.info(f"下载目录: {download_dir}")
                
                # 检查是否已经下载过
                existing_files = glob(f"{download_dir}/{post.shortcode}*")
                if existing_files:
                    self.logger.warning(f"已存在，跳过: {post.shortcode}")
                    self.logger.record_download(post.shortcode, "skipped", existing_files[0], folder=download_dir, blogger=post_owner)
                    skipped_count += 1
                    continue
                
                # 创建 Post 对象
                post_obj = Post(
                    shortcode=post.shortcode,
                    url=f"https://www.instagram.com/p/{post.shortcode}/",
                    caption=post.caption or "",
                    date=post.date
                )
                
                # 下载媒体文件
                try:
                    # 添加请求延迟，避免被封
                    import time
                    account_config = getattr(account, 'config', {})
                    safety_config = account_config.get('download_safety', {})
                    delay = safety_config.get('request_delay', 2)
                    
                    if processed_count > 1:  # 第一个不延迟
                        time.sleep(delay)
                        self.logger.info(f"等待 {delay} 秒后继续...")
                    
                    self.loader.download_post(post, target=download_dir)
                    
                    # 查找下载的文件
                    downloaded_files = glob(f"{download_dir}/{post.shortcode}*")
                    if downloaded_files:
                        post_obj.media_urls = downloaded_files
                        posts.append(post_obj)
                        downloaded_count += 1
                        
                        # 记录下载成功
                        self.logger.record_download(post.shortcode, "success", downloaded_files[0], folder=download_dir, blogger=post_owner)
                        self.logger.success(f"下载成功: {post.shortcode} -> {download_dir}")
                    else:
                        self.logger.error(f"下载后未找到文件: {post.shortcode}")
                        self.logger.record_download(post.shortcode, "failed", error="下载后未找到文件", folder=download_dir, blogger=post_owner)
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"下载失败 {post.shortcode}: {e}")
                    self.logger.record_download(post.shortcode, "failed", error=str(e), folder=download_dir, blogger=post_owner)
                    failed_count += 1
            
            # 显示汇总信息
            self.logger.info(f"下载完成 - 新下载: {downloaded_count}, 跳过: {skipped_count}, 失败: {failed_count}")
            self.logger.info(self.logger.get_download_summary())
            
            # 显示文件夹信息
            folder_info = self.folder_manager.get_folder_info()
            self.logger.info(f"当前账号文件夹数量 - 下载: {folder_info['total_download_folders']}, 合并: {folder_info['total_merged_folders']}")
            
            # 显示未合并的视频数量
            unmerged = self.logger.get_unmerged_downloads()
            if unmerged:
                self.logger.warning(f"待合并视频: {len(unmerged)} 个")
                self.logger.info("运行合并命令可以合并所有未合并的视频")
            
            return [DownloadResult(
                success=True,
                posts=posts,
                message=f"成功下载 {downloaded_count} 个帖子，跳过 {skipped_count} 个，失败 {failed_count} 个"
            )]
            
        except Exception as e:
            self.logger.error(f"下载过程出错: {e}")
            return [DownloadResult(success=False, posts=[], error=str(e))]

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
