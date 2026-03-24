"""
配置管理工具
统一管理账号配置、下载设置等
"""
import json
import os
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config_file = "config/accounts.json"
        self.default_config = {
            "download_limit": 10,
            "auto_merge": True,
            "ffmpeg_quality": "high",
            "retry_count": 3,
            "timeout": 30
        }
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_account_config(self, account_name: str) -> Dict[str, Any]:
        """获取指定账号配置"""
        config = self.load_config()
        account_config = config.get(account_name, {})
        
        # 合并默认配置
        final_config = self.default_config.copy()
        final_config.update(account_config)
        
        return final_config
    
    def update_account_config(self, account_name: str, updates: Dict[str, Any]):
        """更新账号配置"""
        config = self.load_config()
        if account_name not in config:
            config[account_name] = {}
        
        config[account_name].update(updates)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
