"""
Social Media Hub - 主程序
企业级社交媒体内容管理系统
"""
import argparse
import os
import json
import time

from platforms.instagram.downloader import InstagramDownloader
from platforms.bilibili.uploader import BilibiliUploader
from platforms.instagram.logger import Logger
from platforms.bilibili.merger import VideoMerger
from platforms.instagram.folder_manager import FolderManager


class Account:
    def __init__(self, name: str, platform: str, username: str):
        self.name = name
        self.platform = platform
        self.username = username
        self.config = {}


def load_environment_config():
    """加载环境配置"""
    env_config_file = "config/environments.json"
    current_env_file = "config/current_environment.json"
    
    # 默认配置
    default_env = {
        "name": "production",
        "base_paths": {
            "videos": "videos",
            "logs": "logs", 
            "temp": "temp"
        },
        "features": {
            "auto_upload": True,
            "real_download": True,
            "mock_operations": False
        }
    }
    
    # 获取当前环境
    current_env = "production"
    if os.path.exists(current_env_file):
        try:
            with open(current_env_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_env = data.get("current_environment", "production")
        except:
            pass
    
    # 加载环境配置
    if os.path.exists(env_config_file):
        try:
            with open(env_config_file, 'r', encoding='utf-8') as f:
                envs = json.load(f)
                if current_env in envs:
                    env_config = envs[current_env]
                    print(f"🌍 当前环境: {current_env} ({env_config.get('name', current_env)})")
                    return current_env, env_config
        except Exception as e:
            print(f"⚠️ 环境配置加载失败: {e}")
    
    print(f"🌍 使用默认环境: production")
    return current_env, default_env


def load_account_config(environment="production") -> dict:
    """加载账号配置"""
    # 根据环境选择配置文件
    if environment == "development":
        config_file = "config/accounts_test.json"
        fallback_file = "config/accounts.json"
    else:
        config_file = "config/accounts.json"
        fallback_file = None
    
    # 尝试加载主配置文件
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                print(f"✅ 加载配置: {config_file}")
                return config_data
        except Exception as e:
            print(f"⚠️ 配置文件解析失败: {e}")
    
    # 尝试fallback文件
    if fallback_file and os.path.exists(fallback_file):
        try:
            with open(fallback_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                print(f"⚠️ 使用备用配置: {fallback_file}")
                return config_data
        except Exception as e:
            print(f"❌ 备用配置文件也解析失败: {e}")
    
    print(f"❌ 配置文件不存在或无法读取")
    return {}


def create_account_from_config(account_name: str, config: dict) -> Account:
    """从配置创建账号对象"""
    account_config = config.get(account_name, {})
    
    # 支持新旧格式
    if "instagram" in account_config:
        username = account_config["instagram"].get("username", "")
    else:
        username = account_config.get("username", "")
    
    account = Account(
        name=account_name,
        platform="instagram",
        username=username
    )
    
    # 添加完整配置到账号对象
    account.config = account_config
    
    return account


def test_login(account_name: str):
    """测试登录功能"""
    print(f"🔑 测试登录: {account_name}")
    print("-" * 40)
    
    # 加载配置
    config = load_account_config()
    if not config:
        return False
    
    # 创建账号
    account = create_account_from_config(account_name, config)
    if not account.username:
        print(f"❌ 账号配置不完整: {account_name}")
        return False
    
    print(f"📱 账号: {account.name}")
    print(f"👤 用户名: {account.username}")
    print(f"🌐 平台: {account.platform}")
    
    # 显示Firefox配置文件信息
    firefox_profile = account.config.get('firefox_profile', '')
    if firefox_profile:
        print(f"🦊 Firefox配置文件: {firefox_profile}")
    
    # 初始化下载器
    downloader = InstagramDownloader()
    
    # 尝试登录
    print(f"\n🔐 开始登录测试...")
    success = downloader.login(account)
    
    if success:
        print(f"✅ 登录成功: {account.username}")
        print(f"💾 Session已保存")
        return True
    else:
        print(f"❌ 登录失败: {account.username}")
        print(f"💡 建议:")
        print(f"   1. 检查Firefox配置文件是否正确")
        print(f"   2. 删除旧session文件: del temp\\{account_name}_session*")
        print(f"   3. 等待几分钟后重试")
        print(f"   4. 检查网络连接")
        return False


def run_download(account_name: str, limit: int):
    """运行下载任务"""
    # 不在这里显示开始信息，让下载器自己处理
    
    # 加载配置
    config = load_account_config()
    if not config:
        return False
    
    # 创建账号
    account = create_account_from_config(account_name, config)
    if not account.username:
        print(f"❌ 账号配置不完整: {account_name}")
        return False
    
    # 初始化下载器
    downloader = InstagramDownloader()
    
    # 登录
    if not downloader.login(account):
        print(f"❌ 登录失败: {account.username}")
        return False
    
    # 下载内容
    results = downloader.download_posts(account, limit)
    
    # 判断是否成功：至少有一个成功，或者没有任何下载任务时也视为成功
    if len(results) == 0:
        print("ℹ️ 没有新内容需要下载")
        return True
    
    success_count = 0
    total_count = len(results)
    has_actual_downloads = False
    has_detailed_message = False
    
    for result in results:
        if result.success:
            print(f"✅ 下载成功: {result.message}")
            success_count += 1
            # 检查是否是实际的下载操作（不是"没有新视频"这种状态消息）
            if "没有新视频" not in result.message:
                has_actual_downloads = True
                # 检查是否已经包含详细信息（如"成功下载 X 个帖子"）
                if "成功下载" in result.message and "个帖子" in result.message:
                    has_detailed_message = True
        else:
            print(f"❌ 下载失败: {result.error}")
            has_actual_downloads = True  # 失败也算作实际的下载尝试
    
    success = success_count > 0
    # 只有在有实际下载操作且没有详细消息时才显示下载完成统计
    if total_count > 0 and has_actual_downloads and not has_detailed_message:
        print(f"📊 下载完成: {success_count}/{total_count} 成功")
    return success


def run_merge(account_name: str, limit: int = None):
    """运行视频合并任务 - 使用完整标准化流程"""
    print(f"�️ 开始完整标准化合并任务: {account_name}")
    print("📋 包含功能：加黑边统一分辨率 + 音频转AAC + 时间戳修复 + 完整参数标准化")
    if limit:
        print(f"� 处理限制: {limit} 个视频")
    
    # 初始化合并器
    merger = VideoMerger(account_name)
    
    # 使用终极标准化合并（包含所有功能）
    result = merger.merge_unmerged_videos(limit=limit)
    
    print(f"✅ 合并完成 - 成功: {result['merged']}, 跳过: {result['skipped']}, 失败: {result['failed']}")
    
    # 判断是否成功：有成功合并的视频，或者没有需要合并的视频时也视为成功
    success = result['merged'] > 0 or (result['merged'] == 0 and result['failed'] == 0)
    return success


def show_folders(account_name: str = None):
    """显示文件夹信息"""
    if account_name:
        accounts = [account_name]
    else:
        config = load_account_config()
        accounts = list(config.keys())
    
    print("📁 文件夹信息:")
    print("-" * 60)
    
    for acc in accounts:
        config = load_account_config()
        account_config = config.get(acc, {})
        
        folder_manager = FolderManager(acc, account_config)
        folder_info = folder_manager.get_folder_info()
        
        print(f"\n📱 账号: {acc}")
        print(f"   策略: {folder_info['strategy']}")
        print(f"   下载基础目录: {folder_info['base_download_dir']}")
        print(f"   合并基础目录: {folder_info['base_merged_dir']}")
        print(f"   下载文件夹数量: {folder_info['total_download_folders']}")
        print(f"   合并文件夹数量: {folder_info['total_merged_folders']}")
        
        # 显示最近的文件夹
        if folder_info['download_folders']:
            print(f"   最近的下载文件夹:")
            for folder in folder_info['download_folders'][:3]:
                print(f"     - {folder['name']} ({folder['files_count']} 文件)")
        
        if folder_info['merged_folders']:
            print(f"   最近的合并文件夹:")
            for folder in folder_info['merged_folders'][:3]:
                print(f"     - {folder['name']} ({folder['files_count']} 文件)")


def search_blogger(account_name: str, blogger_name: str):
    """搜索博主文件夹"""
    print(f"🔍 搜索博主: {blogger_name} (账号: {account_name})")
    print("-" * 50)
    
    config = load_account_config()
    account_config = config.get(account_name, {})
    
    folder_manager = FolderManager(account_name, account_config)
    matches = folder_manager.search_blogger_folders(blogger_name)
    
    if not matches:
        print(f"❌ 未找到包含 '{blogger_name}' 的文件夹")
        return
    
    print(f"✅ 找到 {len(matches)} 个匹配的文件夹:")
    
    for match in matches:
        print(f"📁 {match['name']} ({match['type']})")
        print(f"   路径: {match['path']}")
        print(f"   文件数: {match['files_count']}")
        print(f"   创建时间: {match['created']}")
        print()


def show_status(account_name: str = None):
    """显示状态信息"""
    if account_name:
        accounts = [account_name]
    else:
        config = load_account_config()
        accounts = list(config.keys())
    
    print("📊 系统状态:")
    print("-" * 50)
    
    for acc in accounts:
        logger = Logger(acc)
        summary = logger.get_download_summary()
        unmerged = logger.get_unmerged_downloads()
        
        print(f"\n📱 账号: {acc}")
        print(f"   总下载: {summary.get('total', 0)} 个")
        print(f"   成功: {summary.get('success', 0)} 个")
        print(f"   失败: {summary.get('failed', 0)} 个")
        print(f"   跳过: {summary.get('skipped', 0)} 个")
        print(f"   待合并: {len(unmerged)} 个")
        
        if unmerged:
            print(f"   未合并列表: {', '.join([u['shortcode'] for u in unmerged[:5]])}")
            if len(unmerged) > 5:
                print(f"                及其他 {len(unmerged) - 5} 个...")
        
        # 显示文件夹信息
        config = load_account_config()
        account_config = config.get(acc, {})
        folder_manager = FolderManager(acc, account_config)
        folder_info = folder_manager.get_folder_info()
        print(f"   下载文件夹: {folder_info['total_download_folders']} 个")
        print(f"   合并文件夹: {folder_info['total_merged_folders']} 个")


def run_upload(video_path: str, account_name: str, category: str = "小剧场",
               subcategory: str = "搞笑研究所", self_only: bool = False):
    """上传视频到Bilibili"""
    print(f"🚀 上传视频: {video_path}")
    print(f"📱 账号: {account_name}")
    print(f"🏷️ 分区: {category}" + (f" / {subcategory}" if subcategory else ""))
    if self_only:
        print("🔒 测试模式：仅自己可见")

    try:
        # 验证文件存在
        if not os.path.exists(video_path):
            print(f"❌ 视频文件不存在: {video_path}")
            return False

        # 创建上传器
        uploader = BilibiliUploader(account_name)

        # 执行上传
        result = uploader.upload(video_path, category, subcategory, self_only=self_only)
        
        # 显示结果
        if result:
            print(f"✅ 上传流程完成！")
            if account_name != "aigf8728":
                print("浏览器已自动关闭")
            return True
        else:
            if account_name == "aigf8728":
                print(f"🔒 上传流程需要手动操作，浏览器保持打开状态")
                print("💡 请在浏览器中完成登录和上传操作")
            else:
                print(f"⚠️ 上传流程未完成，请检查浏览器手动完成")
            return False
            
    except Exception as e:
        print(f"❌ 上传过程发生异常: {e}")
        return False


def run_full_pipeline(account_name: str, download_limit: int = 5, self_only: bool = False):
    """运行完整流程：下载 → 合并 → 上传"""
    print(f"🚀 开始执行完整流程: {account_name}")
    print("="*60)
    
    try:
        # 步骤1: 下载内容
        print("📥 步骤1/3: 下载最新内容...")
        print("-" * 40)
        success_download = run_download(account_name, download_limit)
        if not success_download:
            print("❌ 下载失败，停止流程")
            return False
        
        print("✅ 下载完成！")
        time.sleep(2)  # 短暂等待
        
        # 步骤2: 合并视频
        print("\n🔄 步骤2/3: 合并视频...")
        print("-" * 40)
        
        # 获取合并前的状态，检查是否有新合并
        merger = VideoMerger(account_name)
        merge_result = merger.merge_unmerged_videos(limit=None)
        
        if merge_result['merged'] == 0:
            print("✅ 视频检查完成！")
            print("ℹ️ 没有新的视频需要合并，无需上传，流程结束")
            print("\n" + "="*60)
            print(f"🎉 {account_name} 流程执行完成！")
            print("📥 下载 ✅ → 🔄 无新视频 ✅ → ℹ️ 跳过上传")
            print("="*60)
            return True
        
        print("✅ 视频合并完成！发现新合并视频，准备上传")
        time.sleep(2)  # 短暂等待
        
        # 步骤3: 获取最新合并的视频并上传
        print("\n📤 步骤3/3: 上传最新视频到B站...")
        print("-" * 40)
        
        # 查找最新合并的视频
        latest_video = find_latest_merged_video(account_name)
        if not latest_video:
            print("❌ 未找到可上传的视频文件")
            return False
            
        print(f"📹 找到最新视频: {os.path.basename(latest_video)}")
        
        # 上传视频
        success_upload = run_upload(latest_video, account_name, "小剧场", "搞笑研究所",
                                    self_only=self_only)
        if not success_upload:
            print("❌ 上传失败")
            return False
            
        print("✅ 上传完成！")
        
        # 完成
        print("\n" + "="*60)
        print(f"🎉 {account_name} 完整流程执行成功！")
        print("📥 下载 ✅ → 🔄 合并 ✅ → 📤 上传 ✅")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"❌ 完整流程执行失败: {e}")
        return False


def find_latest_merged_video(account_name: str) -> str:
    """查找最新合并的视频文件"""
    try:
        # 加载配置
        config = load_account_config()
        account_config = config.get(account_name, {})
        
        # 获取合并文件夹路径
        folder_manager = FolderManager(account_name, account_config)
        folder_info = folder_manager.get_folder_info()
        
        base_merged_dir = folder_info['base_merged_dir']
        
        # 查找所有视频文件
        video_files = []
        for root, dirs, files in os.walk(base_merged_dir):
            for file in files:
                if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    full_path = os.path.join(root, file)
                    video_files.append(full_path)
        
        if not video_files:
            return None
            
        # 按修改时间排序，返回最新的
        video_files.sort(key=os.path.getmtime, reverse=True)
        return video_files[0]
        
    except Exception as e:
        print(f"⚠️ 查找最新视频失败: {e}")
        return None


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="Social Media Hub - 企业级社交媒体内容管理")
    
    # 命令参数
    parser.add_argument("--login", action="store_true", help="测试登录功能")
    parser.add_argument("--download", action="store_true", help="下载内容")
    parser.add_argument("--merge", action="store_true", help="合并视频")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--folders", action="store_true", help="显示文件夹信息")
    parser.add_argument("--search", type=str, help="搜索博主文件夹")
    parser.add_argument("--stats", action="store_true", help="显示详细统计")
    parser.add_argument("--clean", action="store_true", help="清理空文件夹")
    parser.add_argument("--backup", action="store_true", help="备份日志文件")
    parser.add_argument("--upload", type=str, help="上传视频文件到Bilibili")
    parser.add_argument("--category", type=str, default="小剧场", help="B站分区类别（生活/娱乐/科技/游戏/小剧场等）")
    parser.add_argument("--subcategory", type=str, default="搞笑研究所", help="B站子分区（如：搞笑研究所）")
    
    # 账号参数
    parser.add_argument("--ai_vanvan", action="store_true", help="使用 ai_vanvan 账号 (搞笑)")
    parser.add_argument("--aigf8728", action="store_true", help="使用 aigf8728 账号")
    parser.add_argument("--account", type=str, help="指定账号名称")
    
    # 其他参数
    parser.add_argument("--test", action="store_true", help="测试模式：上传为仅自己可见")
    parser.add_argument("--limit", type=int, default=50, help="下载数量限制")
    parser.add_argument("--merge-limit", type=int, help="合并视频数量限制")
    parser.add_argument("--all", action="store_true", help="处理所有账号")
    
    args = parser.parse_args()
    
    # 加载环境配置
    current_env, env_config = load_environment_config()
    
    # 检查是否在测试环境
    if current_env == "development":
        print("🧪 警告: 当前处于测试环境")
        if env_config.get("features", {}).get("mock_operations", False):
            print("🎭 模拟操作模式已启用")
    
    # 确定账号（根据环境调整账号名称）
    account_name = None
    if args.ai_vanvan:
        account_name = "ai_vanvan" if current_env == "production" else "ai_vanvan_test"
    elif args.aigf8728:
        account_name = "aigf8728" if current_env == "production" else "aigf8728_test"
    elif args.account:
        account_name = args.account
    
    # 执行命令
    # 检查是否只指定了账号参数（全流程）
    has_action = any([args.login, args.download, args.merge, args.status, args.folders, 
                     args.search, args.stats, args.clean, args.backup, args.upload])
    
    if account_name and not has_action:
        # 只指定账号，执行全流程
        print(f"🎯 检测到纯账号参数，执行完整流程...")
        run_full_pipeline(account_name, args.limit, self_only=args.test)
        
    elif args.login:
        if account_name:
            test_login(account_name)
        else:
            print("❌ 请指定账号 (--ai_vanvan, --aigf8728, 或 --account <name>)")
        
    elif args.download:
        if account_name:
            run_download(account_name, args.limit)
        elif args.all:
            config = load_account_config(current_env)
            for acc in config.keys():
                run_download(acc, args.limit)
        else:
            print("❌ 请指定账号 (--ai_vanvan, --aigf8728, --account <name>, 或 --all)")
    
    elif args.merge:
        if account_name:
            run_merge(account_name, limit=args.merge_limit)
        elif args.all:
            config = load_account_config()
            for acc in config.keys():
                run_merge(acc, limit=args.merge_limit)
        else:
            print("❌ 请指定账号 (--ai_vanvan, --aigf8728, --account <name>, 或 --all)")
    
    elif args.status:
        show_status(account_name)
    
    elif args.folders:
        show_folders(account_name)
    
    elif args.search:
        if account_name:
            search_blogger(account_name, args.search)
        else:
            print("❌ 搜索博主时请指定账号 (--ai_vanvan, --aigf8728, 或 --account <name>)")
    
    elif args.upload:
        if account_name:
            run_upload(args.upload, account_name, args.category, args.subcategory)
        else:
            # 默认使用ai_vanvan账号
            run_upload(args.upload, "ai_vanvan", args.category, args.subcategory)
    
    else:
        # 默认显示帮助
        parser.print_help()
        print("\n💡 常用命令示例:")
        print("   python main.py --login --aigf8728                   # 测试 aigf8728 登录功能")
        print("   python main.py --ai_vanvan                          # 一键执行：下载→合并→上传 全流程")
        print("   python main.py --download --ai_vanvan --limit 5     # 下载 ai_vanvan 的 5 个内容")
        print("   python main.py --merge --ai_vanvan                  # 合并 ai_vanvan 的视频")
        print("   python main.py --upload video.mp4 --ai_vanvan      # 上传视频到Bilibili（默认：小剧场-搞笑研究所）")
        print("   python main.py --upload video.mp4 --ai_vanvan --category 娱乐  # 上传到娱乐分区")
        print("   python main.py --upload video.mp4 --ai_vanvan --category 小剧场 --subcategory 搞笑研究所  # 明确指定分区")
        print("   python main.py --status                          # 查看所有账号状态")
        print("   python main.py --folders --ai_vanvan                # 查看 ai_vanvan 文件夹")
        print("   python main.py --search 博主名 --aigf8728            # 搜索 aigf8728 中的博主文件夹")
        print("   python main.py --download --all --limit 3        # 下载所有账号各 3 个内容")


if __name__ == "__main__":
    main()
