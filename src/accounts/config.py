"""
账号配置管理模块
Account Configuration Management
"""
import os
import json
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AccountConfig:
    """账号配置数据类"""
    name: str
    platform: str 
    title_prefix: str
    serial_number_file: str
    chrome_profile_path: str
    download_folder: str
    merged_folder: str
    firefox_profile: str = ""  # Firefox profile 名称
    
    def get_next_serial(self) -> int:
        """获取下一个序列号"""
        if os.path.exists(self.serial_number_file):
            with open(self.serial_number_file, 'r') as f:
                return int(f.read().strip())
        return 20  # 默认起始序列号
    
    def save_serial(self, serial: int):
        """保存序列号"""
        os.makedirs(os.path.dirname(self.serial_number_file), exist_ok=True)
        with open(self.serial_number_file, 'w') as f:
            f.write(str(serial))
    
    def generate_title(self, serial: int) -> str:
        """生成视频标题"""
        return f"{self.title_prefix}{serial}"


class AccountManager:
    """账号管理器"""
    
    def __init__(self, config_file: str = None):
        if config_file is None:
            # 默认配置文件路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_file = os.path.join(project_root, "config", "accounts.json")
        
        self.config_file = config_file
        self._accounts = self._load_accounts()
    
    def _load_accounts(self) -> Dict[str, AccountConfig]:
        """加载账号配置"""
        if not os.path.exists(self.config_file):
            return self._create_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            accounts = {}
            for name, config in data.items():
                accounts[name] = AccountConfig(**config)
            
            return accounts
        except Exception as e:
            print(f"加载账号配置失败: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, AccountConfig]:
        """创建默认账号配置"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        default_accounts = {
            "ai_vanvan": AccountConfig(
                name="ai_vanvan",
                platform="bilibili",
                title_prefix="海外离大谱#",
                serial_number_file=os.path.join(project_root, "data", "serial_numbers", "ai_vanvan.txt"),
                chrome_profile_path=os.path.join(project_root, "tools", "profiles", "chrome_profile_ai_vanvan"),
                download_folder=os.path.join(project_root, "data", "downloads", "ai_vanvan"),
                merged_folder=os.path.join(project_root, "data", "merged", "ai_vanvan")
            ),
            "aigf8728": AccountConfig(
                name="aigf8728", 
                platform="bilibili",
                title_prefix="AIGF#",
                serial_number_file=os.path.join(project_root, "data", "serial_numbers", "aigf8728.txt"),
                chrome_profile_path=os.path.join(project_root, "tools", "profiles", "chrome_profile_aigf8728"),
                download_folder=os.path.join(project_root, "data", "downloads", "aigf8728"),
                merged_folder=os.path.join(project_root, "data", "merged", "aigf8728")
            )
        }
        
        # 保存默认配置
        self._save_config(default_accounts)
        return default_accounts
    
    def _save_config(self, accounts: Dict[str, AccountConfig]):
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # 转换为字典格式保存
        data = {}
        for name, config in accounts.items():
            data[name] = {
                'name': config.name,
                'platform': config.platform,
                'title_prefix': config.title_prefix,
                'serial_number_file': config.serial_number_file,
                'chrome_profile_path': config.chrome_profile_path,
                'download_folder': config.download_folder,
                'merged_folder': config.merged_folder
            }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_account_config(self, account_name: str) -> AccountConfig:
        """获取账号配置"""
        if account_name not in self._accounts:
            raise ValueError(f"账号 '{account_name}' 不存在")
        return self._accounts[account_name]
    
    def list_accounts(self) -> list:
        """列出所有账号"""
        return list(self._accounts.keys())
    
    def add_account(self, account_config: AccountConfig):
        """添加账号配置"""
        self._accounts[account_config.name] = account_config
        self._save_config(self._accounts)
    
    def update_account(self, account_name: str, **kwargs):
        """更新账号配置"""
        if account_name not in self._accounts:
            raise ValueError(f"账号 '{account_name}' 不存在")
        
        config = self._accounts[account_name]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self._save_config(self._accounts)
