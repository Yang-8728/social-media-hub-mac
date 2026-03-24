"""
批量操作工具
"""
import os
import shutil
from glob import glob
from typing import List, Dict

class BatchOperations:
    """批量操作工具"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.download_base = f"videos/downloads/{account_name}"
        self.merged_base = f"videos/merged/{account_name}"
    
    def clean_empty_folders(self) -> Dict:
        """清理空文件夹"""
        cleaned = {"download": [], "merged": []}
        
        for base_type, base_path in [("download", self.download_base), ("merged", self.merged_base)]:
            if os.path.exists(base_path):
                for folder in os.listdir(base_path):
                    folder_path = os.path.join(base_path, folder)
                    if os.path.isdir(folder_path) and not os.listdir(folder_path):
                        try:
                            os.rmdir(folder_path)
                            cleaned[base_type].append(folder)
                        except OSError:
                            pass
        
        return cleaned
    
    def get_disk_usage(self) -> Dict:
        """获取磁盘使用情况"""
        stats = {"download": {}, "merged": {}}
        
        for base_type, base_path in [("download", self.download_base), ("merged", self.merged_base)]:
            if os.path.exists(base_path):
                total_size = 0
                file_count = 0
                
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path)
                            total_size += size
                            file_count += 1
                        except OSError:
                            pass
                
                stats[base_type] = {
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "file_count": file_count,
                    "folder_count": len([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))])
                }
        
        return stats
    
    def backup_logs(self, backup_dir: str = "backups") -> str:
        """备份日志文件"""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"logs_backup_{self.account_name}_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        
        # 备份日志文件
        log_files = glob(f"logs/*{self.account_name}*")
        download_logs = glob(f"logs/downloads/{self.account_name}*")
        
        for log_file in log_files + download_logs:
            if os.path.exists(log_file):
                shutil.copy2(log_file, backup_path)
        
        return backup_path
