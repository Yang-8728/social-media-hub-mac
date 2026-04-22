import os
import re
from datetime import datetime
from typing import Dict
from platforms.instagram.path_utils import clean_unicode_path


class FolderManager:

    def __init__(self, account_name: str, config: Dict):
        self.account_name = account_name
        self.config = config
        self.base_download_dir = config.get("download_dir", f"videos/downloads/{account_name}")
        self.base_merged_dir = config.get("merged_dir", f"videos/merged/{account_name}")
        self.folder_strategy = config.get("folder_strategy", "simple")
        self.folder_pattern = config.get("folder_pattern", "{date}")

    def get_current_date_string(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def extract_blogger_name(self, post_owner: str) -> str:
        if post_owner:
            invalid_chars = r'[\\/:*?"<>|]'
            clean_name = re.sub(invalid_chars, '-', post_owner)
            return clean_name[:30]
        return "unknown_blogger"

    def get_download_folder(self, post_owner: str = None) -> str:
        date_str = self.get_current_date_string()
        if self.folder_strategy == "daily":
            full_path = os.path.join(self.base_download_dir, date_str)
        elif self.folder_strategy == "blogger_daily":
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            full_path = os.path.join(self.base_download_dir, f"{blogger_name} {date_str}")
        elif self.folder_strategy == "date_blogger":
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            full_path = os.path.join(self.base_download_dir, f"{date_str}_{blogger_name}")
        else:
            full_path = self.base_download_dir
        cleaned_path = clean_unicode_path(full_path)
        os.makedirs(cleaned_path, exist_ok=True)
        return cleaned_path

    def get_merged_folder(self, post_owner: str = None) -> str:
        date_str = self.get_current_date_string()
        if self.folder_strategy == "daily":
            full_path = os.path.join(self.base_merged_dir, date_str)
        elif self.folder_strategy == "blogger_daily":
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            full_path = os.path.join(self.base_merged_dir, f"{blogger_name} {date_str}")
        elif self.folder_strategy == "date_blogger":
            blogger_name = self.extract_blogger_name(post_owner) if post_owner else "unknown"
            full_path = os.path.join(self.base_merged_dir, f"{date_str}_{blogger_name}")
        else:
            full_path = self.base_merged_dir
        cleaned_path = clean_unicode_path(full_path)
        os.makedirs(cleaned_path, exist_ok=True)
        return cleaned_path

    def list_download_folders(self) -> list:
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
        folders.sort(key=lambda x: x["created"], reverse=True)
        return folders

    def list_merged_folders(self) -> list:
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
        all_folders = []
        for folder in self.list_download_folders():
            folder["type"] = "download"
            all_folders.append(folder)
        for folder in self.list_merged_folders():
            folder["type"] = "merged"
            all_folders.append(folder)
        return [f for f in all_folders if blogger_name.lower() in f["name"].lower()]
