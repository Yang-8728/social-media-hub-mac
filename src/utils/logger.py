"""
日志工具
统一的日志记录和管理
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class Logger:
    """日志记录器"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # 应用程序日志文件按日期命名，存储在app子目录
        today = datetime.now().strftime("%Y-%m-%d")
        app_logs_dir = self.logs_dir / "app"
        app_logs_dir.mkdir(exist_ok=True)
        self.log_file = app_logs_dir / f"{today}-{account_name}.log"
        
        # 下载记录文件 - 统一到logs目录
        self.download_log_file = Path("logs") / "downloads" / f"{account_name}_downloads.json"
        self.download_log_file.parent.mkdir(parents=True, exist_ok=True)
        
    def log(self, level: str, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        # 打印到控制台
        print(log_entry)
        
        # 写入日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def info(self, message: str):
        """信息日志"""
        self.log("INFO", message)
    
    def success(self, message: str):
        """成功日志"""
        self.log("SUCCESS", message)
    
    def warning(self, message: str):
        """警告日志"""
        self.log("WARNING", message)
    
    def error(self, message: str):
        """错误日志"""
        self.log("ERROR", message)
    
    def load_download_log(self) -> Dict[str, Any]:
        """加载下载记录"""
        if self.download_log_file.exists():
            with open(self.download_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "account": self.account_name,
            "downloads": [],
            "merged_sessions": []
        }
    
    def save_download_log(self, log_data: Dict[str, Any]):
        """保存下载记录"""
        with open(self.download_log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
    
    def record_download(self, shortcode: str, status: str, file_path: str = "", error: str = "", folder: str = "", blogger: str = ""):
        """记录下载信息"""
        log_data = self.load_download_log()
        
        download_record = {
            "shortcode": shortcode,
            "download_time": datetime.now().isoformat(),
            "status": status,  # "success", "failed", "skipped"
            "file_path": file_path,
            "error": error,
            "merged": False,  # 是否已合并
            "download_folder": folder,  # 下载文件夹
            "blogger_name": blogger  # 博主名字
        }
        
        # 检查是否已存在，避免重复记录
        existing = next((d for d in log_data["downloads"] if d["shortcode"] == shortcode), None)
        if existing:
            existing.update(download_record)
        else:
            log_data["downloads"].append(download_record)
        
        self.save_download_log(log_data)
        
        # 移除自动打印下载记录信息，由调用者决定是否显示
        # if status == "success":
        #     self.success(f"下载记录: {shortcode} -> {file_path}")
        # elif status == "failed":
        #     self.error(f"下载失败: {shortcode} - {error}")
        # else:
        #     self.warning(f"下载跳过: {shortcode}")
        
        # 移除文件夹和博主信息的自动打印
        # if folder:
        #     self.info(f"文件夹: {folder}")
        # if blogger:
        #     self.info(f"博主: {blogger}")
    
    def get_unmerged_downloads(self) -> List[dict]:
        """获取未合并的下载记录，按下载时间倒序排列（最新的在前）"""
        log_data = self.load_download_log()
        unmerged = [d for d in log_data["downloads"] if d["status"] == "success" and not d.get("merged", False)]
        
        # 按下载时间排序，最新的在前
        unmerged.sort(key=lambda x: x.get("download_time", ""), reverse=True)
        
        # 返回完整记录
        return unmerged
    
    def mark_as_merged(self, shortcode: str, merged_file_path: str):
        """标记单个视频为已合并"""
        log_data = self.load_download_log()
        
        # 更新下载记录
        for download in log_data["downloads"]:
            if download["shortcode"] == shortcode:
                download["merged"] = True
                break
        
        # 记录合并会话
        merge_session = {
            "merge_time": datetime.now().isoformat(),
            "shortcode": shortcode,
            "merged_file": merged_file_path
        }
        log_data["merged_sessions"].append(merge_session)
        
        self.save_download_log(log_data)
        self.success(f"标记为已合并: {shortcode} -> {merged_file_path}")
    
    def mark_as_merged_by_filename(self, filename: str, merged_file_path: str):
        """根据文件名标记视频为已合并"""
        log_data = self.load_download_log()
        
        # 更新下载记录 - 查找匹配的文件名
        updated = False
        for download in log_data["downloads"]:
            # 检查filename字段或从file_path构建的文件名
            download_filename = download.get("filename")
            if not download_filename and download.get("file_path"):
                # 如果没有filename，尝试从路径和时间构建文件名
                # 这种情况下我们只能尝试通过其他信息匹配
                pass
            
            if download_filename == filename:
                download["merged"] = True
                updated = True
                
                # 记录合并会话
                merge_session = {
                    "merge_time": datetime.now().isoformat(),
                    "shortcode": download.get("shortcode", "unknown"),
                    "filename": filename,
                    "merged_file": merged_file_path
                }
                log_data["merged_sessions"].append(merge_session)
                break
        
        if updated:
            self.save_download_log(log_data)
            self.info(f"根据文件名标记为已合并: {filename}")
        else:
            # 如果没找到匹配的记录，这是正常的，不需要记录日志
            pass
            
        return updated
    
    def mark_batch_as_merged(self, shortcodes: List[str], merged_file_path: str):
        """标记多个视频为已合并（批量合并时使用）"""
        log_data = self.load_download_log()
        
        # 更新下载记录
        for download in log_data["downloads"]:
            if download["shortcode"] in shortcodes:
                download["merged"] = True
        
        # 记录合并会话
        merge_session = {
            "merge_time": datetime.now().isoformat(),
            "shortcodes": shortcodes,
            "merged_file": merged_file_path,
            "video_count": len(shortcodes)
        }
        log_data["merged_sessions"].append(merge_session)
        
        self.save_download_log(log_data)
        self.success(f"批量合并完成: {len(shortcodes)} 个视频 -> {merged_file_path}")
    
    def get_download_summary(self) -> dict:
        """获取下载汇总信息"""
        log_data = self.load_download_log()
        downloads = log_data["downloads"]
        
        total = len(downloads)
        success = len([d for d in downloads if d["status"] == "success"])
        failed = len([d for d in downloads if d["status"] == "failed"])
        skipped = len([d for d in downloads if d["status"] == "skipped"])
        merged = len([d for d in downloads if d.get("merged", False)])
        unmerged = success - merged
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "merged": merged,
            "unmerged": unmerged
        }
    
    def is_downloaded(self, shortcode: str) -> bool:
        """检查指定shortcode是否已下载（检查日志记录+实际文件存在）"""
        log_data = self.load_download_log()
        downloads = log_data["downloads"]
        
        # 首先检查是否存在成功下载的记录
        if any(d["shortcode"] == shortcode and d["status"] == "success" for d in downloads):
            return True
        
        # 如果日志中没有记录，检查文件是否实际存在
        # 这可以捕获到那些文件存在但日志丢失的情况
        return self._check_file_exists_by_shortcode(shortcode)
    
    def _check_file_exists_by_shortcode(self, shortcode: str) -> bool:
        """通过检查文件系统确认shortcode对应的文件是否存在（优化版）"""
        import os
        from pathlib import Path
        from datetime import datetime, timedelta
        
        # 检查所有可能的下载目录，但优先检查最近的文件夹
        base_dir = Path(f"videos/downloads/{self.account_name}")
        
        if not base_dir.exists():
            return False
        
        # 获取所有日期文件夹，按日期倒序排列（最新的优先）
        date_folders = []
        for folder in base_dir.iterdir():
            if folder.is_dir():
                try:
                    # 尝试解析日期，新的文件夹优先检查
                    folder_date = datetime.strptime(folder.name, "%Y-%m-%d")
                    date_folders.append((folder_date, folder))
                except ValueError:
                    # 非日期格式的文件夹放在最后
                    date_folders.append((datetime.min, folder))
        
        # 按日期倒序排列
        date_folders.sort(key=lambda x: x[0], reverse=True)
        
        # 优先检查最近30天的文件夹
        recent_limit = datetime.now() - timedelta(days=30)
        
        # 先检查最近的文件夹
        for folder_date, folder in date_folders:
            if folder_date >= recent_limit:
                if self._check_shortcode_in_folder(folder, shortcode):
                    return True
        
        # 如果最近30天没找到，再检查其他文件夹
        for folder_date, folder in date_folders:
            if folder_date < recent_limit:
                if self._check_shortcode_in_folder(folder, shortcode):
                    return True
        
        return False
    
    def _check_shortcode_in_folder(self, folder: Path, shortcode: str) -> bool:
        """在指定文件夹中检查shortcode"""
        import lzma
        import json
        
        # 查找json.xz文件
        for json_file in folder.glob("*.json.xz"):
            try:
                with open(json_file, 'rb') as f:
                    content = lzma.decompress(f.read()).decode('utf-8')
                    data = json.loads(content)
                    
                    # instaloader的数据结构：shortcode在node层级
                    node = data.get('node', {})
                    if node.get('shortcode') == shortcode:
                        return True
            except Exception:
                continue
        
        return False
    
    def sync_missing_downloads(self, force_full_scan: bool = False) -> int:
        """智能同步缺失的下载记录，返回补充的记录数量"""
        import os
        import lzma
        import json
        from pathlib import Path
        from datetime import datetime, timedelta
        
        # 检查是否需要完整扫描
        cache_file = Path(f"logs/cache/.sync_cache_{self.account_name}.json")
        
        # 如果不是强制完整扫描，使用增量同步
        if not force_full_scan and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    last_sync = datetime.fromisoformat(cache_data.get('last_sync', '2000-01-01'))
                    
                    # 如果上次同步在24小时内，且没有新的日期文件夹，跳过同步
                    if datetime.now() - last_sync < timedelta(hours=24):
                        return self._quick_sync_recent_only()
            except:
                pass  # 缓存文件损坏，执行完整同步
        
        # 执行完整同步
        return self._full_sync_downloads()
    
    def _quick_sync_recent_only(self) -> int:
        """快速同步：只检查最近3天的文件夹"""
        import os
        import lzma
        import json
        from pathlib import Path
        from datetime import datetime, timedelta
        
        log_data = self.load_download_log()
        existing_shortcodes = {d["shortcode"] for d in log_data["downloads"] if d["status"] == "success"}
        
        base_dir = Path(f"videos/downloads/{self.account_name}")
        added_count = 0
        
        if not base_dir.exists():
            return 0
        
        # 只检查最近3天的日期文件夹
        recent_days = []
        for i in range(3):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            recent_days.append(date_str)
        
        for date_folder in base_dir.iterdir():
            if date_folder.is_dir() and date_folder.name in recent_days:
                added_count += self._sync_folder(date_folder, existing_shortcodes, log_data)
        
        if added_count > 0:
            self.save_download_log(log_data)
            self.info(f"快速同步了 {added_count} 条缺失记录（仅检查最近3天）")
        
        return added_count
    
    def _full_sync_downloads(self) -> int:
        """完整同步：扫描所有文件夹"""
        import os
        import lzma
        import json
        from pathlib import Path
        from datetime import datetime
        
        log_data = self.load_download_log()
        existing_shortcodes = {d["shortcode"] for d in log_data["downloads"] if d["status"] == "success"}
        
        base_dir = Path(f"videos/downloads/{self.account_name}")
        added_count = 0
        
        if not base_dir.exists():
            return 0
        
        # 扫描所有日期目录
        for date_folder in base_dir.iterdir():
            if date_folder.is_dir():
                added_count += self._sync_folder(date_folder, existing_shortcodes, log_data)
        
        if added_count > 0:
            self.save_download_log(log_data)
            self.info(f"完整同步了 {added_count} 条缺失记录")
        
        # 更新缓存
        self._update_sync_cache()
        
        return added_count
    
    def _sync_folder(self, date_folder: Path, existing_shortcodes: set, log_data: dict) -> int:
        """同步单个文件夹"""
        import lzma
        import json
        from datetime import datetime
        
        added_count = 0
        
        # 查找json.xz文件
        for json_file in date_folder.glob("*.json.xz"):
            try:
                with open(json_file, 'rb') as f:
                    content = lzma.decompress(f.read()).decode('utf-8')
                    data = json.loads(content)
                    
                    # instaloader的数据结构：shortcode在node层级
                    node = data.get('node', {})
                    shortcode = node.get('shortcode')
                    
                    if shortcode and shortcode not in existing_shortcodes:
                        # 提取博主信息
                        owner_info = node.get('owner', {})
                        owner = owner_info.get('username', 'unknown')
                        
                        # 添加缺失的记录
                        download_record = {
                            "shortcode": shortcode,
                            "download_time": datetime.now().isoformat(),
                            "status": "success",
                            "file_path": str(date_folder),
                            "error": "",
                            "merged": False,
                            "download_folder": str(date_folder),
                            "blogger_name": owner,
                            "sync_added": True  # 标记为同步添加
                        }
                        
                        log_data["downloads"].append(download_record)
                        existing_shortcodes.add(shortcode)
                        added_count += 1
                        
            except Exception as e:
                continue
        
        return added_count
    
    def _update_sync_cache(self):
        """更新同步缓存"""
        import json
        from pathlib import Path
        from datetime import datetime
        
        cache_file = Path(f"logs/cache/.sync_cache_{self.account_name}.json")
        cache_data = {
            "last_sync": datetime.now().isoformat(),
            "account": self.account_name
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
