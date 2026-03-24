"""
下载进度跟踪和统计
"""
from datetime import datetime, timedelta
from typing import Dict, List
import json

class DownloadStats:
    """下载统计工具"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.log_file = f"logs/downloads/{account_name}_downloads.json"
    
    def get_today_stats(self) -> Dict:
        """获取今天的下载统计"""
        today = datetime.now().date()
        return self.get_date_stats(today)
    
    def get_date_stats(self, date) -> Dict:
        """获取指定日期的下载统计"""
        data = self._load_data()
        date_str = date.strftime("%Y-%m-%d")
        
        today_downloads = [
            d for d in data.get("downloads", [])
            if d["download_time"].startswith(date_str)
        ]
        
        stats = {
            "date": date_str,
            "total": len(today_downloads),
            "success": len([d for d in today_downloads if d["status"] == "success"]),
            "failed": len([d for d in today_downloads if d["status"] == "failed"]),
            "skipped": len([d for d in today_downloads if d["status"] == "skipped"]),
            "merged": len([d for d in today_downloads if d.get("merged", False)]),
            "bloggers": list(set([d.get("blogger_name", "unknown") for d in today_downloads if d["status"] == "success"]))
        }
        
        return stats
    
    def get_weekly_stats(self) -> List[Dict]:
        """获取本周的下载统计"""
        stats = []
        today = datetime.now().date()
        
        for i in range(7):
            date = today - timedelta(days=i)
            day_stats = self.get_date_stats(date)
            day_stats["day_name"] = date.strftime("%A")
            stats.append(day_stats)
        
        return stats
    
    def get_top_bloggers(self, days=7) -> List[Dict]:
        """获取最活跃的博主"""
        data = self._load_data()
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        
        blogger_counts = {}
        for download in data.get("downloads", []):
            if download["status"] == "success":
                download_date = datetime.fromisoformat(download["download_time"]).date()
                if download_date >= cutoff_date:
                    blogger = download.get("blogger_name", "unknown")
                    blogger_counts[blogger] = blogger_counts.get(blogger, 0) + 1
        
        # 排序并返回前10名
        sorted_bloggers = sorted(blogger_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"blogger": name, "count": count} for name, count in sorted_bloggers[:10]]
    
    def _load_data(self) -> Dict:
        """加载下载数据"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"downloads": []}
