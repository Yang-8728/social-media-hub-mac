"""
视频合并器：标准化 Instagram 下载的视频并合并为单一 mp4，用于 B 站上传。
"""
import os
import subprocess
import glob
import json
from datetime import datetime
from typing import Dict, List

from platforms.instagram.folder_manager import FolderManager
from platforms.instagram.logger import Logger


class VideoMerger:

    def __init__(self, account_name: str = None):
        self.account_name = account_name
        self.logger = Logger(account_name) if account_name else Logger("video_merger")

        if account_name:
            logs_dir = os.path.join("logs", "merges")
            os.makedirs(logs_dir, exist_ok=True)
            self.merged_record_file = os.path.join(logs_dir, f"{account_name}_merged_record.json")
        else:
            self.merged_record_file = None

        if account_name:
            try:
                from main import load_account_config
                account_configs = load_account_config()
                config = account_configs.get(account_name, {})
                self.folder_manager = FolderManager(account_name, config)
            except Exception:
                self.folder_manager = None
        else:
            self.folder_manager = None

    def load_merged_record(self) -> Dict:
        if not self.merged_record_file or not os.path.exists(self.merged_record_file):
            return {"merged_videos": []}
        try:
            with open(self.merged_record_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"merged_videos": []}

    def save_merged_record(self, record: Dict):
        if not self.merged_record_file:
            return
        with open(self.merged_record_file, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

    def add_merged_videos(self, video_paths: List[str], output_path: str, chapter_list: str = ""):
        record = self.load_merged_record()
        record["merged_videos"].append({
            "timestamp": datetime.now().isoformat(),
            "output_file": output_path,
            "input_videos": [os.path.abspath(v) for v in video_paths],
            "input_count": len(video_paths),
            "chapter_list": chapter_list
        })
        self.save_merged_record(record)
        self.logger.info(f"记录已合并视频: {len(video_paths)} 个文件 -> {os.path.basename(output_path)}")

        download_logger = Logger(self.account_name)
        for video_path in video_paths:
            filename = os.path.basename(video_path)
            try:
                download_logger.mark_as_merged_by_filename(filename, output_path)
            except Exception:
                pass

    def is_video_merged(self, video_path: str) -> bool:
        record = self.load_merged_record()
        video_abs_path = os.path.abspath(video_path)
        for merge_info in record["merged_videos"]:
            if video_abs_path in merge_info.get("input_videos", []):
                return True
        return False

    def _generate_title_filename(self, video_paths: List[str]) -> str:
        try:
            episode_number = self._get_current_episode_number()
            blogger_id = self._extract_blogger_id_from_videos(video_paths)
            if self.account_name == "aigf8728":
                title = f"ins你的海外第{episode_number}个女友_{blogger_id}"
            else:
                title = f"ins海外离大谱#{episode_number}"
            title = self._clean_filename(title)
            return f"{title}.mp4"
        except Exception:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            return f"{timestamp}.mp4"

    def _get_current_episode_number(self) -> int:
        sequence_file = f"logs/episodes/{self.account_name}_episode.txt"
        if os.path.exists(sequence_file):
            with open(sequence_file, 'r', encoding='utf-8') as f:
                return int(f.read().strip())
        try:
            from main import load_account_config
            accounts_config = load_account_config()
            if self.account_name in accounts_config:
                account_config = accounts_config[self.account_name]
                if 'upload' in account_config and 'next_number' in account_config['upload']:
                    return account_config['upload']['next_number']
        except Exception:
            pass
        default_numbers = {'ai_vanvan': 84, 'aigf8728': 6}
        return default_numbers.get(self.account_name, 1)

    def _extract_blogger_id_from_videos(self, video_paths: List[str]) -> str:
        try:
            for video_path in video_paths:
                path_parts = os.path.normpath(video_path).split(os.sep)
                for part in path_parts:
                    if '_' in part and len(part.split('_')[0]) == 10:
                        date_blogger = part.split('_', 1)
                        if len(date_blogger) > 1 and date_blogger[1] != "unknown":
                            return date_blogger[1]
            return "blogger"
        except Exception:
            return "blogger"

    def _clean_filename(self, filename: str) -> str:
        for char in '<>:"/\\|?*':
            filename = filename.replace(char, '_')
        return filename

    def get_video_duration(self, video_path: str) -> float:
        try:
            cmd = ["/opt/homebrew/bin/ffprobe", "-v", "quiet",
                   "-show_entries", "format=duration", "-of", "csv=p=0", video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def get_video_resolution(self, video_path: str) -> tuple:
        try:
            cmd = ["/opt/homebrew/bin/ffprobe", "-v", "quiet",
                   "-select_streams", "v:0", "-show_entries", "stream=width,height",
                   "-of", "csv=p=0", video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            w, h = result.stdout.strip().split(',')
            return int(w), int(h)
        except Exception:
            return None, None

    def find_target_resolution(self, video_files: List[str]) -> tuple:
        resolutions = {}
        for video in video_files:
            w, h = self.get_video_resolution(video)
            if w and h:
                target = (720, 1280) if h > w and w >= 720 else \
                         (540, 960) if h > w else \
                         (1280, 720) if w >= 1280 else (960, 540)
                resolutions[target] = resolutions.get(target, 0) + 1
        if not resolutions:
            return 720, 1280
        target = max(resolutions.items(), key=lambda x: x[1])[0]
        self.logger.info(f"检测到目标分辨率: {target[0]}x{target[1]}")
        return target

    def get_author_id_for_video(self, video_path: str) -> str:
        try:
            filename = os.path.basename(video_path)
            shortcode = os.path.splitext(filename)[0]
            download_log_file = os.path.join("logs", "downloads", f"{self.account_name}_downloads.json")
            if not os.path.exists(download_log_file):
                return "unknown"
            with open(download_log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            for record in log_data.get("downloads", []):
                if record.get("shortcode") == shortcode:
                    return record.get("blogger_name") or "unknown"
            return "unknown"
        except Exception:
            return "unknown"

    def build_chapter_list(self, video_files: List[str]) -> str:
        lines = []
        cumulative_seconds = 0.0
        for video_path in video_files:
            total_secs = round(cumulative_seconds)
            h, m, s = total_secs // 3600, (total_secs % 3600) // 60, total_secs % 60
            timestamp = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            author_id = self.get_author_id_for_video(video_path)
            lines.append(f"{timestamp}  {author_id}")
            cumulative_seconds += self.get_video_duration(video_path)
        return "\n".join(lines)

    def ultimate_video_standardization(self, input_path: str, output_path: str, target_width: int, target_height: int) -> bool:
        try:
            cmd = [
                "/opt/homebrew/bin/ffmpeg",
                "-i", input_path,
                "-avoid_negative_ts", "make_zero",
                "-fflags", "+genpts",
                "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-sample_fmt", "fltp",
                "-max_muxing_queue_size", "1024", "-vsync", "1", "-async", "1",
                "-y", output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            self.logger.error(f"标准化失败: {result.stderr[:200]}")
            return False
        except Exception as e:
            self.logger.error(f"标准化出错: {e}")
            return False

    def merge_videos_with_standardization(self, video_files: List[str], output_path: str) -> bool:
        if not video_files:
            return False
        target_width, target_height = self.find_target_resolution(video_files)
        temp_dir = "temp/ultimate_standardized"
        os.makedirs(temp_dir, exist_ok=True)
        standardized_files = []
        try:
            for i, video in enumerate(video_files):
                temp_output = os.path.join(temp_dir, f"ultimate_{i:03d}.mp4")
                if self.ultimate_video_standardization(video, temp_output, target_width, target_height):
                    standardized_files.append(temp_output)
                else:
                    self.logger.warning(f"跳过标准化失败的视频: {video}")
            if not standardized_files:
                return False
            return self.merge_videos_with_ffmpeg(standardized_files, output_path)
        finally:
            for temp_file in standardized_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except Exception:
                    pass

    def merge_videos_with_ffmpeg(self, video_files: List[str], output_path: str) -> bool:
        if not video_files:
            return False
        filelist_path = "temp_filelist.txt"
        try:
            with open(filelist_path, 'w', encoding='utf-8') as f:
                for video in video_files:
                    abs_path = os.path.abspath(video).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            cmd = ["/opt/homebrew/bin/ffmpeg", "-f", "concat", "-safe", "0",
                   "-i", filelist_path, "-c", "copy", "-y", output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.success(f"合并成功! 输出文件: {output_path}")
                return True
            self.logger.error(f"FFmpeg合并失败: {result.stderr[:200]}")
            return False
        except Exception as e:
            self.logger.error(f"合并过程出错: {e}")
            return False
        finally:
            if os.path.exists(filelist_path):
                os.remove(filelist_path)

    def merge_unmerged_videos(self, limit: int = None) -> Dict:
        if not self.account_name:
            return {"merged": 0, "skipped": 0, "failed": 1}

        downloads_base = os.path.join("videos", "downloads", self.account_name)
        if not os.path.exists(downloads_base):
            self.logger.warning(f"下载目录不存在: {downloads_base}")
            return {"merged": 0, "skipped": 0, "failed": 0}

        today = datetime.now().strftime("%Y-%m-%d")
        all_today_videos = []

        try:
            from main import load_account_config
            account_configs = load_account_config()
            account_config = account_configs.get(self.account_name, {})
            folder_strategy = account_config.get("folder_strategy", "daily")
        except Exception:
            folder_strategy = "daily"

        if folder_strategy == "date_blogger":
            pattern = os.path.join(downloads_base, f"{today}_*")
            for folder in glob.glob(pattern):
                if os.path.isdir(folder):
                    all_today_videos.extend(glob.glob(os.path.join(folder, "*.mp4")))
        else:
            today_path = os.path.join(downloads_base, today)
            if os.path.exists(today_path):
                all_today_videos.extend(glob.glob(os.path.join(today_path, "*.mp4")))

        if not all_today_videos:
            self.logger.info("没有找到今天新下载的视频文件")
            return {"merged": 0, "skipped": 0, "failed": 0}

        unmerged_videos = []
        skipped_count = 0
        for video in all_today_videos:
            if self.is_video_merged(video):
                skipped_count += 1
            else:
                unmerged_videos.append(video)

        if not unmerged_videos:
            self.logger.info("今天所有视频都已经合并过了")
            return {"merged": 0, "skipped": skipped_count, "failed": 0}

        unmerged_videos.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        if limit:
            merge_videos = unmerged_videos[:limit]
        else:
            merge_videos = unmerged_videos

        merge_dir = os.path.join("videos", "merged", self.account_name)
        os.makedirs(merge_dir, exist_ok=True)

        output_filename = self._generate_title_filename(merge_videos)
        output_path = os.path.join(merge_dir, output_filename)

        self.logger.info("🎯 使用终极标准化合并模式")
        chapter_list = self.build_chapter_list(merge_videos)
        if chapter_list:
            self.logger.info(f"章节列表:\n{chapter_list}")

        success = self.merge_videos_with_standardization(merge_videos, output_path)

        if success:
            self.add_merged_videos(merge_videos, output_path, chapter_list)
            return {"merged": 1, "skipped": skipped_count, "failed": 0}
        else:
            return {"merged": 0, "skipped": skipped_count, "failed": 1}
