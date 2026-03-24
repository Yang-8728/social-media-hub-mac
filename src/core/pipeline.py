"""
主要工作流程
协调下载、合并、上传的完整流程
"""
from typing import List
from ..core.interfaces import IDownloader, IUploader, IVideoProcessor
from ..core.models import Account, Video, DownloadResult, UploadResult


class Pipeline:
    """工作流程管道"""
    
    def __init__(self, downloader: IDownloader, uploader: IUploader, video_processor: IVideoProcessor = None):
        self.downloader = downloader
        self.uploader = uploader
        self.video_processor = video_processor
    
    def run_full_workflow(self, download_account: Account, upload_account: Account, download_count: int = 10) -> bool:
        """运行完整工作流程：下载 → 合并 → 上传"""
        
        print(f"=== 开始完整工作流程 ===")
        print(f"下载账号: {download_account.name}")
        print(f"上传账号: {upload_account.name}")
        
        # 1. 下载阶段
        print("\n[1/3] 开始下载...")
        if not self.downloader.login(download_account):
            print("❌ 下载账号登录失败")
            return False
        
        download_results = self.downloader.download_posts(download_account, download_count)
        if not download_results or not download_results[0].success:
            print("❌ 下载失败")
            return False
        
        downloaded_posts = download_results[0].posts
        print(f"✅ 下载完成，共 {len(downloaded_posts)} 个帖子")
        
        # 2. 合并阶段（如果有视频处理器）
        merged_video_path = None
        if self.video_processor and downloaded_posts:
            print("\n[2/3] 开始合并视频...")
            video_files = []
            for post in downloaded_posts:
                if post.media_urls:
                    video_files.extend(post.media_urls)
            
            if video_files:
                output_path = f"videos/merged/{download_account.name}/merged_video.mp4"
                merged_video_path = self.video_processor.merge_videos(video_files, output_path)
                print(f"✅ 视频合并完成: {merged_video_path}")
            else:
                print("⚠️ 没有找到可合并的视频文件")
        
        # 3. 上传阶段
        print("\n[3/3] 开始上传...")
        if not self.uploader.login(upload_account):
            print("❌ 上传账号登录失败")
            return False
        
        # 创建视频对象
        if merged_video_path:
            video = Video(
                file_path=merged_video_path,
                title=f"Instagram 精选合集 - {download_account.name}",
                description=f"来自 {download_account.name} 的精彩内容合集"
            )
        else:
            # 如果没有合并视频，上传第一个下载的视频
            if downloaded_posts and downloaded_posts[0].media_urls:
                video = Video(
                    file_path=downloaded_posts[0].media_urls[0],
                    title=f"Instagram 内容 - {downloaded_posts[0].shortcode}",
                    description=downloaded_posts[0].caption
                )
            else:
                print("❌ 没有可上传的视频")
                return False
        
        upload_result = self.uploader.upload_video(video, upload_account)
        if upload_result.success:
            print(f"✅ 上传成功: {upload_result.url}")
            return True
        else:
            print(f"❌ 上传失败: {upload_result.error}")
            return False
