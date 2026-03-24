"""
数据模型定义
定义账号、视频、帖子等核心数据结构
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Account:
    """账号信息"""
    name: str                    # 账号名称，如 "ai_vanvan"
    platform: str               # 平台名称，如 "instagram"
    username: str = ""           # 用户名
    password: str = ""           # 密码
    cookies_file: str = ""       # Cookie文件路径
    profile_path: str = ""       # 浏览器配置文件路径
    firefox_profile: str = ""    # Firefox profile 名称
    

@dataclass
class Post:
    """帖子信息"""
    shortcode: str               # 短码，Instagram的唯一标识
    url: str                     # 帖子URL
    caption: str = ""            # 描述文字
    date: Optional[datetime] = None   # 发布时间
    media_urls: List[str] = None      # 媒体文件URL列表
    
    def __post_init__(self):
        if self.media_urls is None:
            self.media_urls = []


@dataclass
class Video:
    """视频信息"""
    file_path: str               # 视频文件路径
    title: str = ""              # 视频标题
    description: str = ""        # 视频描述
    size: int = 0                # 文件大小（字节）
    duration: float = 0.0        # 视频时长（秒）
    

@dataclass
class DownloadResult:
    """下载结果"""
    success: bool                # 是否成功
    posts: List[Post]            # 下载的帖子列表
    message: str = ""            # 消息
    error: str = ""              # 错误信息


@dataclass
class UploadResult:
    """上传结果"""
    success: bool                # 是否成功
    video_id: str = ""           # 上传后的视频ID
    url: str = ""                # 上传后的视频URL
    message: str = ""            # 消息
    error: str = ""              # 错误信息
