"""
Instagram 下载日志记录器。
跟踪下载记录、合并状态，存储于 logs/downloads/{account}_downloads.json。
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class Logger:

    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        app_logs_dir = self.logs_dir / "app"
        app_logs_dir.mkdir(exist_ok=True)
        self.log_file = app_logs_dir / f"{today}-{account_name}.log"

        self.download_log_file = Path("logs") / "downloads" / f"{account_name}_downloads.json"
        self.download_log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')

    def info(self, message: str):    self.log("INFO", message)
    def success(self, message: str): self.log("SUCCESS", message)
    def warning(self, message: str): self.log("WARNING", message)
    def error(self, message: str):   self.log("ERROR", message)

    def load_download_log(self) -> Dict[str, Any]:
        if self.download_log_file.exists():
            with open(self.download_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"account": self.account_name, "downloads": [], "merged_sessions": []}

    def save_download_log(self, log_data: Dict[str, Any]):
        with open(self.download_log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)

    def record_download(self, shortcode: str, status: str, file_path: str = "", error: str = "", folder: str = "", blogger: str = ""):
        log_data = self.load_download_log()
        download_record = {
            "shortcode": shortcode,
            "download_time": datetime.now().isoformat(),
            "status": status,
            "file_path": file_path,
            "error": error,
            "merged": False,
            "download_folder": folder,
            "blogger_name": blogger
        }
        existing = next((d for d in log_data["downloads"] if d["shortcode"] == shortcode), None)
        if existing:
            existing.update(download_record)
        else:
            log_data["downloads"].append(download_record)
        self.save_download_log(log_data)

    def get_unmerged_downloads(self) -> List[dict]:
        log_data = self.load_download_log()
        unmerged = [d for d in log_data["downloads"] if d["status"] == "success" and not d.get("merged", False)]
        unmerged.sort(key=lambda x: x.get("download_time", ""), reverse=True)
        return unmerged

    def mark_as_merged(self, shortcode: str, merged_file_path: str):
        log_data = self.load_download_log()
        for download in log_data["downloads"]:
            if download["shortcode"] == shortcode:
                download["merged"] = True
                break
        log_data["merged_sessions"].append({
            "merge_time": datetime.now().isoformat(),
            "shortcode": shortcode,
            "merged_file": merged_file_path
        })
        self.save_download_log(log_data)
        self.success(f"标记为已合并: {shortcode} -> {merged_file_path}")

    def mark_as_merged_by_filename(self, filename: str, merged_file_path: str):
        log_data = self.load_download_log()
        updated = False
        for download in log_data["downloads"]:
            download_filename = download.get("filename")
            if download_filename == filename:
                download["merged"] = True
                updated = True
                log_data["merged_sessions"].append({
                    "merge_time": datetime.now().isoformat(),
                    "shortcode": download.get("shortcode", "unknown"),
                    "filename": filename,
                    "merged_file": merged_file_path
                })
                break
        if updated:
            self.save_download_log(log_data)
        return updated

    def mark_batch_as_merged(self, shortcodes: List[str], merged_file_path: str):
        log_data = self.load_download_log()
        for download in log_data["downloads"]:
            if download["shortcode"] in shortcodes:
                download["merged"] = True
        log_data["merged_sessions"].append({
            "merge_time": datetime.now().isoformat(),
            "shortcodes": shortcodes,
            "merged_file": merged_file_path,
            "video_count": len(shortcodes)
        })
        self.save_download_log(log_data)
        self.success(f"批量合并完成: {len(shortcodes)} 个视频 -> {merged_file_path}")

    def get_download_summary(self) -> dict:
        log_data = self.load_download_log()
        downloads = log_data["downloads"]
        total   = len(downloads)
        success = len([d for d in downloads if d["status"] == "success"])
        failed  = len([d for d in downloads if d["status"] == "failed"])
        skipped = len([d for d in downloads if d["status"] == "skipped"])
        merged  = len([d for d in downloads if d.get("merged", False)])
        return {"total": total, "success": success, "failed": failed, "skipped": skipped, "merged": merged, "unmerged": success - merged}

    def is_downloaded(self, shortcode: str) -> bool:
        log_data = self.load_download_log()
        if any(d["shortcode"] == shortcode and d["status"] == "success" for d in log_data["downloads"]):
            return True
        return self._check_file_exists_by_shortcode(shortcode)

    def _check_file_exists_by_shortcode(self, shortcode: str) -> bool:
        import lzma
        from datetime import timedelta
        base_dir = Path(f"videos/downloads/{self.account_name}")
        if not base_dir.exists():
            return False
        date_folders = []
        for folder in base_dir.iterdir():
            if folder.is_dir():
                try:
                    folder_date = datetime.strptime(folder.name, "%Y-%m-%d")
                    date_folders.append((folder_date, folder))
                except ValueError:
                    date_folders.append((datetime.min, folder))
        date_folders.sort(key=lambda x: x[0], reverse=True)
        recent_limit = datetime.now() - timedelta(days=30)
        for folder_date, folder in date_folders:
            if folder_date >= recent_limit and self._check_shortcode_in_folder(folder, shortcode):
                return True
        for folder_date, folder in date_folders:
            if folder_date < recent_limit and self._check_shortcode_in_folder(folder, shortcode):
                return True
        return False

    def _check_shortcode_in_folder(self, folder: Path, shortcode: str) -> bool:
        import lzma
        for json_file in folder.glob("*.json.xz"):
            try:
                with open(json_file, 'rb') as f:
                    content = lzma.decompress(f.read()).decode('utf-8')
                    data = json.loads(content)
                    if data.get('node', {}).get('shortcode') == shortcode:
                        return True
            except Exception:
                continue
        return False

    def sync_missing_downloads(self, force_full_scan: bool = False) -> int:
        from datetime import timedelta
        cache_file = Path(f"logs/cache/.sync_cache_{self.account_name}.json")
        if not force_full_scan and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    last_sync = datetime.fromisoformat(cache_data.get('last_sync', '2000-01-01'))
                    if datetime.now() - last_sync < timedelta(hours=24):
                        return self._quick_sync_recent_only()
            except Exception:
                pass
        return self._full_sync_downloads()

    def _quick_sync_recent_only(self) -> int:
        from datetime import timedelta
        log_data = self.load_download_log()
        existing = {d["shortcode"] for d in log_data["downloads"] if d["status"] == "success"}
        base_dir = Path(f"videos/downloads/{self.account_name}")
        added_count = 0
        if not base_dir.exists():
            return 0
        recent_days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
        for date_folder in base_dir.iterdir():
            if date_folder.is_dir() and date_folder.name in recent_days:
                added_count += self._sync_folder(date_folder, existing, log_data)
        if added_count > 0:
            self.save_download_log(log_data)
        return added_count

    def _full_sync_downloads(self) -> int:
        log_data = self.load_download_log()
        existing = {d["shortcode"] for d in log_data["downloads"] if d["status"] == "success"}
        base_dir = Path(f"videos/downloads/{self.account_name}")
        added_count = 0
        if not base_dir.exists():
            return 0
        for date_folder in base_dir.iterdir():
            if date_folder.is_dir():
                added_count += self._sync_folder(date_folder, existing, log_data)
        if added_count > 0:
            self.save_download_log(log_data)
        self._update_sync_cache()
        return added_count

    def _sync_folder(self, date_folder: Path, existing_shortcodes: set, log_data: dict) -> int:
        import lzma
        added_count = 0
        for json_file in date_folder.glob("*.json.xz"):
            try:
                with open(json_file, 'rb') as f:
                    content = lzma.decompress(f.read()).decode('utf-8')
                    data = json.loads(content)
                    node = data.get('node', {})
                    shortcode = node.get('shortcode')
                    if shortcode and shortcode not in existing_shortcodes:
                        owner = node.get('owner', {}).get('username', 'unknown')
                        log_data["downloads"].append({
                            "shortcode": shortcode,
                            "download_time": datetime.now().isoformat(),
                            "status": "success",
                            "file_path": str(date_folder),
                            "error": "",
                            "merged": False,
                            "download_folder": str(date_folder),
                            "blogger_name": owner,
                            "sync_added": True
                        })
                        existing_shortcodes.add(shortcode)
                        added_count += 1
            except Exception:
                continue
        return added_count

    def _update_sync_cache(self):
        cache_file = Path(f"logs/cache/.sync_cache_{self.account_name}.json")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({"last_sync": datetime.now().isoformat(), "account": self.account_name}, f)
