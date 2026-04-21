"""
粉丝定制订单脚本
用法: python fan_order.py <粉丝bilibili_id> <instagram_id>
流程: 下载 Instagram 视频 → zip 打包 → 上传夸克网盘 → 生成分享链接
"""
import os
import sys
import json
import shutil
import zipfile
import random
import string
import time
from datetime import date
from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect

MAX_SIZE_BYTES = 200 * 1024 * 1024  # 200MB


def load_quark_config() -> dict:
    path = "config/quark.json"
    if not os.path.exists(path):
        print(f"❌ 夸克配置文件不存在: {path}")
        print("请先创建 config/quark.json，参考项目 README")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_instagram_login_account() -> dict:
    with open("config/accounts.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("ai_vanvan", {})


def get_firefox_cookiefile(firefox_profile: str) -> str | None:
    if system() == "Darwin":
        firefox_dir = os.path.join(expanduser("~"), "Library", "Application Support", "Firefox", "Profiles")
    else:
        firefox_dir = os.path.join(expanduser("~"), ".mozilla", "firefox")

    if firefox_profile:
        candidate = os.path.join(firefox_dir, firefox_profile, "cookies.sqlite")
        if os.path.exists(candidate):
            return candidate

    for p in glob(os.path.join(firefox_dir, "*")):
        candidate = os.path.join(p, "cookies.sqlite")
        if os.path.exists(candidate):
            return candidate
    return None


def download_instagram_videos(instagram_id: str, output_dir: str) -> list[str]:
    """下载指定 Instagram 账号的视频，累计超过 200MB 立即停止。返回下载的文件路径列表。"""
    import requests
    from instaloader import Instaloader, Profile

    account = load_instagram_login_account()
    username = account.get("username", "ai_vanvan")
    firefox_profile = account.get("firefox_profile", "")
    request_delay = account.get("download_safety", {}).get("request_delay", 45)

    loader = Instaloader(
        max_connection_attempts=3,
        request_timeout=30,
        quiet=True,
        save_metadata=False,
        compress_json=False,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        sleep=True,
    )

    # 优先加载已有 session 文件
    session_dir = os.path.join(os.getcwd(), "temp")
    os.makedirs(session_dir, exist_ok=True)
    session_file = os.path.join(session_dir, f"{username}_session")

    if os.path.exists(session_file):
        print(f"🔑 从 session 文件登录 Instagram（账号: {username}）...")
        loader.load_session_from_file(username, session_file)
        loader.context.username = username
    else:
        cookiefile = get_firefox_cookiefile(firefox_profile)
        if not cookiefile:
            print("❌ 找不到 Firefox cookies，请先用 Firefox 登录 Instagram")
            sys.exit(1)

        print(f"🔑 从 Firefox cookies 登录 Instagram（账号: {username}）...")
        conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
        try:
            cookie_data = conn.execute("SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'")
        except OperationalError:
            cookie_data = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'")
        loader.context._session.cookies.update(cookie_data)
        loader.context.username = username
        loader.save_session_to_file(session_file)
        print(f"  ✅ session 已保存，下次直接复用")

    print(f"🔍 获取 @{instagram_id} 的帖子...")
    profile = Profile.from_username(loader.context, instagram_id)

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []
    total_size = 0

    print(f"📥 开始下载视频（上限 200MB）...")
    for post in profile.get_posts():
        if not post.is_video:
            continue

        out_path = os.path.join(output_dir, f"{post.shortcode}.mp4")
        if os.path.exists(out_path):
            continue

        try:
            r = requests.get(post.video_url, stream=True, timeout=60)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)

            file_size = os.path.getsize(out_path)
            total_size += file_size
            downloaded.append(out_path)
            print(f"  ✅ {post.shortcode}.mp4  {file_size/1024/1024:.1f}MB  累计 {total_size/1024/1024:.1f}MB")

            if total_size > MAX_SIZE_BYTES:
                print(f"🛑 累计已超过 200MB（{total_size/1024/1024:.1f}MB），停止下载")
                break

            time.sleep(request_delay)

        except Exception as e:
            print(f"  ⚠️  {post.shortcode} 下载失败: {e}")
            if os.path.exists(out_path):
                os.remove(out_path)

    print(f"📊 共下载 {len(downloaded)} 个视频，总大小 {total_size/1024/1024:.1f}MB")
    return downloaded


def create_zip(files: list[str], zip_path: str) -> None:
    print(f"📦 打包压缩包: {os.path.basename(zip_path)}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for f in files:
            zf.write(f, os.path.basename(f))
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"  ✅ 压缩包大小: {size_mb:.1f}MB")


def get_or_create_quark_folder(client, folder_name: str) -> str:
    """找到或创建夸克根目录下的文件夹，返回 fid。"""
    resp = client.list_files(folder_id="0", size=100)
    items = resp.get("data", {}).get("list", [])
    for item in items:
        if item.get("file_name") == folder_name and item.get("file_type") == 0:
            print(f"  ✅ 找到现有文件夹 /{folder_name}/  (fid={item['fid']})")
            return item["fid"]

    result = client.create_folder(folder_name, parent_id="0")
    fid = result.get("data", {}).get("fid") or result.get("fid", "")
    print(f"  ✅ 已创建文件夹 /{folder_name}/  (fid={fid})")
    return fid


def upload_to_quark(zip_path: str, quark_config: dict) -> tuple[str, str]:
    """上传 zip 到夸克网盘，返回 (share_url, password)。"""
    from quark_client import QuarkClient

    cookie = quark_config.get("cookie", "")
    upload_folder = quark_config.get("upload_folder", "粉丝定制")
    expire_days = int(quark_config.get("share_expire_days", 7))

    if not cookie:
        print("❌ config/quark.json 中 cookie 为空，请填写夸克网盘 Cookie")
        sys.exit(1)

    print(f"☁️  连接夸克网盘...")
    with QuarkClient(cookies=cookie) as client:
        folder_id = get_or_create_quark_folder(client, upload_folder)

        zip_name = os.path.basename(zip_path)
        print(f"⬆️  上传 {zip_name} 到 /{upload_folder}/...")

        def progress(pct, msg):
            print(f"  [{pct:3d}%] {msg}", end="\r", flush=True)

        upload_result = client.upload_file(zip_path, parent_folder_id=folder_id, progress_callback=progress)
        print()

        # 上传完成后按文件名搜索 fid（upload 返回值不含 fid）
        resp = client.list_files(folder_id=folder_id, size=50, sort_field="updated_at", sort_order="desc")
        items = resp.get("data", {}).get("list", [])
        file_id = next((item["fid"] for item in items if item.get("file_name") == zip_name), None)
        if not file_id:
            print(f"❌ 上传后找不到文件 {zip_name}，请检查夸克网盘 /{upload_folder}/ 文件夹")
            sys.exit(1)
        print(f"  ✅ 上传成功 (fid={file_id})")

        password = "".join(random.choices(string.digits, k=4))
        share = client.create_share(
            file_ids=[file_id],
            title=zip_name,
            expire_days=expire_days,
            password=password,
        )

        share_url = share.get("share_url") or share.get("url") or share.get("link")
        if not share_url:
            print(f"❌ 创建分享链接失败，响应: {share}")
            sys.exit(1)

        return share_url, password


def main():
    if len(sys.argv) != 3:
        print("用法: python fan_order.py <粉丝bilibili_id> <instagram_id>")
        print("示例: python fan_order.py 粉丝123 ai_vanvan")
        sys.exit(1)

    fan_bilibili_id = sys.argv[1]
    instagram_id = sys.argv[2]
    today = date.today().strftime("%Y-%m-%d")

    print("=" * 60)
    print("🎯 粉丝定制订单")
    print(f"   粉丝 Bilibili ID : {fan_bilibili_id}")
    print(f"   Instagram 账号  : @{instagram_id}")
    print(f"   日期            : {today}")
    print("=" * 60)

    orders_dir = os.path.join("temp", "fan_orders")
    download_dir = os.path.join(orders_dir, f"{instagram_id}_{today}")
    zip_name = f"{fan_bilibili_id}_{instagram_id}_{today}.zip"
    zip_path = os.path.join(orders_dir, zip_name)
    os.makedirs(orders_dir, exist_ok=True)

    quark_config = load_quark_config()

    # 步骤 1: 下载视频
    print("\n📥 步骤 1/3: 下载 Instagram 视频")
    print("-" * 40)
    video_files = download_instagram_videos(instagram_id, download_dir)
    if not video_files:
        print("❌ 没有下载到任何视频")
        sys.exit(1)

    # 步骤 2: 打包 zip
    print("\n📦 步骤 2/3: 打包压缩包")
    print("-" * 40)
    create_zip(video_files, zip_path)

    # 步骤 3: 上传夸克 + 生成分享链接
    print("\n☁️  步骤 3/3: 上传夸克网盘并生成分享链接")
    print("-" * 40)
    share_url, password = upload_to_quark(zip_path, quark_config)

    # 清理本地文件
    print("\n🗑️  清理本地临时文件...")
    shutil.rmtree(download_dir, ignore_errors=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print("  ✅ 已清理")

    # 最终结果
    print()
    print("=" * 60)
    print("🎉 订单完成！请将以下信息发给粉丝：")
    print("=" * 60)
    print(f"链接：{share_url}")
    print(f"提取码：{password}")
    print("=" * 60)


if __name__ == "__main__":
    main()
