"""
Instagram 安全策略和限制管理
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import json
import os

class InstagramSafety:
    """Instagram 安全策略管理"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.usage_log_file = f"logs/usage/{account_name}_usage.json"
        os.makedirs(os.path.dirname(self.usage_log_file), exist_ok=True)
    
    def check_rate_limit(self, config: Dict[str, Any]) -> bool:
        """检查是否超过速率限制"""
        safety_config = config.get('download_safety', {})
        max_posts_per_hour = safety_config.get('max_posts_per_hour', 30)
        max_posts_per_day = safety_config.get('max_posts_per_day', 200)
        
        usage_data = self._load_usage_data()
        now = datetime.now()
        
        # 检查过去1小时的请求
        hour_ago = now - timedelta(hours=1)
        recent_requests = [
            req for req in usage_data.get('requests', [])
            if datetime.fromisoformat(req['timestamp']) > hour_ago
        ]
        
        if len(recent_requests) >= max_posts_per_hour:
            return False
        
        # 检查今天的请求
        today = now.date()
        today_requests = [
            req for req in usage_data.get('requests', [])
            if datetime.fromisoformat(req['timestamp']).date() == today
        ]
        
        if len(today_requests) >= max_posts_per_day:
            return False
        
        return True
    
    def record_request(self, request_type: str = "download"):
        """记录请求"""
        usage_data = self._load_usage_data()
        
        if 'requests' not in usage_data:
            usage_data['requests'] = []
        
        usage_data['requests'].append({
            'timestamp': datetime.now().isoformat(),
            'type': request_type
        })
        
        # 只保留最近7天的记录
        cutoff = datetime.now() - timedelta(days=7)
        usage_data['requests'] = [
            req for req in usage_data['requests']
            if datetime.fromisoformat(req['timestamp']) > cutoff
        ]
        
        self._save_usage_data(usage_data)
    
    def get_recommended_delay(self, config: Dict[str, Any]) -> int:
        """获取推荐的请求延迟"""
        safety_config = config.get('download_safety', {})
        base_delay = safety_config.get('request_delay', 2)
        
        usage_data = self._load_usage_data()
        recent_count = len([
            req for req in usage_data.get('requests', [])
            if datetime.fromisoformat(req['timestamp']) > datetime.now() - timedelta(minutes=10)
        ])
        
        # 如果最近请求很多，增加延迟
        if recent_count > 10:
            return base_delay * 2
        elif recent_count > 5:
            return int(base_delay * 1.5)
        
        return base_delay
    
    def _load_usage_data(self) -> Dict[str, Any]:
        """加载使用数据"""
        try:
            with open(self.usage_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'requests': []}
    
    def _save_usage_data(self, data: Dict[str, Any]):
        """保存使用数据"""
        with open(self.usage_log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
