"""
文件夹管理器
根据不同账号的策略创建和管理下载文件夹
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict
from .path_utils import clean_unicode_path, ensure_valid_windows_path


class FolderManager:
    """文件夹管理器"""
    
    def __init__(self, account_name: str, config: Dict):
        self.account_name = account_name
        self.config = config
        self.base_download_dir = config.get("download_dir", f"videos/downloads/{account_name}")
        self.base_merged_dir = config.get("merged_dir", f"videos/merged/{account_name}")
        self.folder_strategy = config.get("folder_strategy", "simple")
        self.folder_pattern = config.get("folder_pattern", "{date}")
    
    def get_current_date_string(self) -> str:
        """获取当前日期字符串 YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def extract_blogger_name(self, post_owner: str) -> str:
        """从帖子所有者信息提取博主名字"""
        if post_owner:
            # 只替换文件系统不支持的字符，保持其他字符原样
            import re
            # Windows 文件系统不支持的字符: \ / : * ? " < > |
            invalid_chars = r'[\\/:*?"<>|]'
            clean_name = re.sub(invalid_chars, '-', post_owner)
            return clean_name[:30]  # 适当增加长度限制
        return "unknown_blogger"
    
    def get_download_folder(self, post_owner: str = None) -> str:
        """
        根据策略获取下载文件夹路径
        
        ⚠️ 重要：返回前必须清理Unicode路径字符！
        防止文件被保存到错误的Unicode路径位置
        """
        date_str = self.get_current_date_string()
        
        if self.folder_strategy == "daily":
            # ai_vanvan: 每天一个文件夹，按日期命名
            folder_name = date_str
            full_path = os.path.join(self.base_download_dir, folder_name)
            
        elif self.folder_strategy == "blogger_daily":
            # 现有策略: 博主名+日期 (用空格分隔)
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            folder_name = f"{blogger_name} {date_str}"
            full_path = os.path.join(self.base_download_dir, folder_name)
            
        elif self.folder_strategy == "date_blogger":
            # aigf8728: 日期_博主ID (用下划线分隔)
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            folder_name = f"{date_str}_{blogger_name}"
            full_path = os.path.join(self.base_download_dir, folder_name)
            
        else:
            # 默认策略：直接使用基础目录
            full_path = self.base_download_dir
        
        # **关键修复：先清理路径中的Unicode字符，再创建目录**
        cleaned_path = clean_unicode_path(full_path)
        
        # 确保目录存在
        os.makedirs(cleaned_path, exist_ok=True)
        
        return cleaned_path
    
    def get_merged_folder(self, post_owner: str = None) -> str:
        """获取合并文件夹路径"""
        date_str = self.get_current_date_string()
        
        if self.folder_strategy == "daily":
            folder_name = date_str
            full_path = os.path.join(self.base_merged_dir, folder_name)
            
        elif self.folder_strategy == "blogger_daily":
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            folder_name = f"{blogger_name} {date_str}"
            full_path = os.path.join(self.base_merged_dir, folder_name)
            
        elif self.folder_strategy == "date_blogger":
            # aigf8728: 日期_博主ID (用下划线分隔)
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            folder_name = f"{date_str}_{blogger_name}"
            full_path = os.path.join(self.base_merged_dir, folder_name)
            
        else:
            full_path = self.base_merged_dir
        
        # **关键修复：先清理路径中的Unicode字符，再创建目录**
        cleaned_path = clean_unicode_path(full_path)
        
        os.makedirs(cleaned_path, exist_ok=True)
        return cleaned_path
    
    def list_download_folders(self) -> list:
        """列出所有下载文件夹"""
        if not os.path.exists(self.base_download_dir):
            return []
        
        folders = []
        for item in os.listdir(self.base_download_dir):
            item_path = os.path.join(self.base_download_dir, item)
            if os.path.isdir(item_path):
                folders.append({
                    "name": item,
                    "path": item_path,
                    "created": datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S"),
                    "files_count": len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                })
        
        # 按创建时间倒序排列
        folders.sort(key=lambda x: x["created"], reverse=True)
        return folders
    
    def list_merged_folders(self) -> list:
        """列出所有合并文件夹"""
        if not os.path.exists(self.base_merged_dir):
            return []
        
        folders = []
        for item in os.listdir(self.base_merged_dir):
            item_path = os.path.join(self.base_merged_dir, item)
            if os.path.isdir(item_path):
                folders.append({
                    "name": item,
                    "path": item_path,
                    "created": datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S"),
                    "files_count": len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                })
        
        folders.sort(key=lambda x: x["created"], reverse=True)
        return folders
    
    def get_folder_info(self) -> Dict:
        """获取文件夹信息汇总"""
        download_folders = self.list_download_folders()
        merged_folders = self.list_merged_folders()
        
        return {
            "account": self.account_name,
            "strategy": self.folder_strategy,
            "base_download_dir": self.base_download_dir,
            "base_merged_dir": self.base_merged_dir,
            "download_folders": download_folders,
            "merged_folders": merged_folders,
            "total_download_folders": len(download_folders),
            "total_merged_folders": len(merged_folders)
        }
    
    def search_blogger_folders(self, blogger_name: str) -> list:
        """搜索包含特定博主名字的文件夹"""
        folders = self.list_download_folders()
        merged = self.list_merged_folders()
        
        # 合并所有文件夹
        all_folders = []
        for folder in folders:
            folder["type"] = "download"
            all_folders.append(folder)
        for folder in merged:
            folder["type"] = "merged"
            all_folders.append(folder)
        
        # 搜索匹配的文件夹
        matches = []
        for folder in all_folders:
            if blogger_name.lower() in folder["name"].lower():
                matches.append(folder)
        
        return matches
    
    def cleanup_empty_folders(self):
        """清理空文件夹"""
        cleaned = []
        
        for base_dir in [self.base_download_dir, self.base_merged_dir]:
            if not os.path.exists(base_dir):
                continue
                
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    # 检查文件夹是否为空
                    if not os.listdir(item_path):
                        try:
                            os.rmdir(item_path)
                            cleaned.append(item_path)
                        except OSError:
                            pass  # 可能有权限问题，忽略
        
        return cleaned
