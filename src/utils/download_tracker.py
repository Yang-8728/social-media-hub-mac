"""
Instagram下载功能优化 - 重复检测改进
"""
import os
import json
from datetime import datetime
from typing import Set

class DownloadTracker:
    """改进的下载追踪器"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.log_file = f"logs/downloads/{account_name}_downloads.json"
        
    def is_downloaded_by_metadata(self, shortcode: str) -> bool:
        """通过元数据文件检测是否已下载"""
        # 检查所有可能的下载目录中是否存在对应的json.xz文件
        base_dir = f"videos/downloads/{self.account_name}"
        
        if not os.path.exists(base_dir):
            return False
            
        # 遍历所有日期目录
        for date_folder in os.listdir(base_dir):
            date_path = os.path.join(base_dir, date_folder)
            if os.path.isdir(date_path):
                # 查找shortcode对应的json.xz文件
                for filename in os.listdir(date_path):
                    if filename.endswith('.json.xz'):
                        try:
                            # 从元数据中提取shortcode
                            json_path = os.path.join(date_path, filename)
                            with open(json_path, 'rb') as f:
                                import lzma
                                content = lzma.decompress(f.read()).decode('utf-8')
                                metadata = json.loads(content)
                                if metadata.get('shortcode') == shortcode:
                                    return True
                        except Exception:
                            continue
        return False
    
    def get_downloaded_shortcodes(self) -> Set[str]:
        """获取所有已下载的shortcode集合"""
        downloaded = set()
        
        # 从下载日志获取
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry in data.get('downloads', []):
                        if entry.get('status') == 'success':
                            downloaded.add(entry.get('shortcode'))
            except Exception:
                pass
        
        # 从实际文件系统获取
        base_dir = f"videos/downloads/{self.account_name}"
        if os.path.exists(base_dir):
            for date_folder in os.listdir(base_dir):
                date_path = os.path.join(base_dir, date_folder)
                if os.path.isdir(date_path):
                    for filename in os.listdir(date_path):
                        if filename.endswith('.json.xz'):
                            try:
                                json_path = os.path.join(date_path, filename)
                                with open(json_path, 'rb') as f:
                                    import lzma
                                    content = lzma.decompress(f.read()).decode('utf-8')
                                    metadata = json.loads(content)
                                    shortcode = metadata.get('shortcode')
                                    if shortcode:
                                        downloaded.add(shortcode)
                            except Exception:
                                continue
        
        return downloaded
