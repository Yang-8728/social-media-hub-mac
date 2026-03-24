"""
核心接口定义
定义了社交媒体聚合系统的核心抽象接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
from enum import Enum

class PostType(Enum):
    """帖子类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    POLL = "poll"
    STORY = "story"

class PlatformType(Enum):
    """平台类型枚举"""
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    WEIBO = "weibo"
    WECHAT = "wechat"

class IPlatformConnector(ABC):
    """平台连接器接口"""
    
    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """返回平台类型"""
        pass
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        平台认证
        
        Args:
            credentials: 认证凭据字典
            
        Returns:
            bool: 认证是否成功
        """
        pass
    
    @abstractmethod
    async def fetch_posts(self, 
                         account_id: str, 
                         limit: int = 20,
                         since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        获取帖子
        
        Args:
            account_id: 账户ID
            limit: 获取数量限制
            since: 起始时间
            
        Returns:
            List[Dict]: 帖子数据列表
        """
        pass
    
    @abstractmethod
    async def publish_post(self, 
                          account_id: str, 
                          content: Dict[str, Any]) -> Dict[str, Any]:
        """
        发布帖子
        
        Args:
            account_id: 账户ID
            content: 帖子内容
            
        Returns:
            Dict: 发布结果
        """
        pass
    
    @abstractmethod
    async def get_account_info(self, account_id: str) -> Dict[str, Any]:
        """
        获取账户信息
        
        Args:
            account_id: 账户ID
            
        Returns:
            Dict: 账户信息
        """
        pass
    
    @abstractmethod
    async def get_analytics(self, 
                           account_id: str, 
                           start_date: datetime, 
                           end_date: datetime) -> Dict[str, Any]:
        """
        获取分析数据
        
        Args:
            account_id: 账户ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict: 分析数据
        """
        pass

class IDataProcessor(ABC):
    """数据处理器接口"""
    
    @abstractmethod
    async def process_post(self, raw_post: Dict[str, Any], platform: PlatformType) -> Dict[str, Any]:
        """
        处理单个帖子数据
        
        Args:
            raw_post: 原始帖子数据
            platform: 平台类型
            
        Returns:
            Dict: 标准化后的帖子数据
        """
        pass
    
    @abstractmethod
    async def batch_process(self, raw_posts: List[Dict[str, Any]], platform: PlatformType) -> List[Dict[str, Any]]:
        """
        批量处理帖子数据
        
        Args:
            raw_posts: 原始帖子数据列表
            platform: 平台类型
            
        Returns:
            List[Dict]: 标准化后的帖子数据列表
        """
        pass

class IDataStorage(ABC):
    """数据存储接口"""
    
    @abstractmethod
    async def save_post(self, post_data: Dict[str, Any]) -> str:
        """
        保存帖子数据
        
        Args:
            post_data: 帖子数据
            
        Returns:
            str: 保存的帖子ID
        """
        pass
    
    @abstractmethod
    async def save_posts(self, posts_data: List[Dict[str, Any]]) -> List[str]:
        """
        批量保存帖子数据
        
        Args:
            posts_data: 帖子数据列表
            
        Returns:
            List[str]: 保存的帖子ID列表
        """
        pass
    
    @abstractmethod
    async def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        """
        获取帖子数据
        
        Args:
            post_id: 帖子ID
            
        Returns:
            Optional[Dict]: 帖子数据，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    async def search_posts(self, 
                          query: Dict[str, Any], 
                          limit: int = 20, 
                          offset: int = 0) -> List[Dict[str, Any]]:
        """
        搜索帖子
        
        Args:
            query: 搜索查询条件
            limit: 结果数量限制
            offset: 偏移量
            
        Returns:
            List[Dict]: 搜索结果
        """
        pass
    
    @abstractmethod
    async def delete_post(self, post_id: str) -> bool:
        """
        删除帖子
        
        Args:
            post_id: 帖子ID
            
        Returns:
            bool: 删除是否成功
        """
        pass

class IAnalytics(ABC):
    """分析接口"""
    
    @abstractmethod
    async def calculate_engagement_rate(self, posts: List[Dict[str, Any]]) -> float:
        """
        计算参与率
        
        Args:
            posts: 帖子数据列表
            
        Returns:
            float: 参与率
        """
        pass
    
    @abstractmethod
    async def get_trending_topics(self, 
                                 posts: List[Dict[str, Any]], 
                                 limit: int = 10) -> List[str]:
        """
        获取热门话题
        
        Args:
            posts: 帖子数据列表
            limit: 结果数量限制
            
        Returns:
            List[str]: 热门话题列表
        """
        pass
    
    @abstractmethod
    async def generate_report(self, 
                             account_id: str, 
                             start_date: datetime, 
                             end_date: datetime) -> Dict[str, Any]:
        """
        生成分析报告
        
        Args:
            account_id: 账户ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            Dict: 分析报告数据
        """
        pass

class IScheduler(ABC):
    """调度器接口"""
    
    @abstractmethod
    async def schedule_post(self, 
                           platform: PlatformType, 
                           account_id: str, 
                           content: Dict[str, Any], 
                           publish_time: datetime) -> str:
        """
        调度帖子发布
        
        Args:
            platform: 平台类型
            account_id: 账户ID
            content: 帖子内容
            publish_time: 发布时间
            
        Returns:
            str: 调度任务ID
        """
        pass
    
    @abstractmethod
    async def cancel_scheduled_post(self, task_id: str) -> bool:
        """
        取消调度的帖子
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 取消是否成功
        """
        pass
    
    @abstractmethod
    async def get_scheduled_posts(self, account_id: str) -> List[Dict[str, Any]]:
        """
        获取调度的帖子列表
        
        Args:
            account_id: 账户ID
            
        Returns:
            List[Dict]: 调度的帖子列表
        """
        pass

class INotificationService(ABC):
    """通知服务接口"""
    
    @abstractmethod
    async def send_notification(self, 
                               recipient: str, 
                               message: str, 
                               notification_type: str = "info") -> bool:
        """
        发送通知
        
        Args:
            recipient: 接收者
            message: 通知消息
            notification_type: 通知类型
            
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @abstractmethod
    async def subscribe_to_events(self, 
                                 event_types: List[str], 
                                 callback_url: str) -> str:
        """
        订阅事件
        
        Args:
            event_types: 事件类型列表
            callback_url: 回调URL
            
        Returns:
            str: 订阅ID
        """
        pass


class IDownloader(ABC):
    """下载器接口"""
    
    @abstractmethod
    def download_saved_posts(self, account_name: str, limit: int = None) -> List[Any]:
        """
        下载保存的帖子
        
        Args:
            account_name: 账户名
            limit: 下载限制数量
            
        Returns:
            List: 下载结果列表
        """
        pass
    
    @abstractmethod
    def setup_session(self, account_name: str) -> bool:
        """
        设置下载会话
        
        Args:
            account_name: 账户名
            
        Returns:
            bool: 设置是否成功
        """
        pass


class IUploader(ABC):
    """上传器接口"""
    
    @abstractmethod
    def login(self, account: Any) -> bool:
        """
        登录账号
        
        Args:
            account: 账户对象
            
        Returns:
            bool: 登录是否成功
        """
        pass
    
    @abstractmethod
    def upload_video(self, account: Any, video: Any) -> Any:
        """
        上传视频
        
        Args:
            account: 账户对象
            video: 视频对象
            
        Returns:
            Any: 上传结果
        """
        pass
