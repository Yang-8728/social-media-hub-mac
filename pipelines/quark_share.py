"""
粉丝视频分享：下载IG视频 → 打包zip → 上传夸克 → 生成分享链接 → 回复B站评论。
"""
import os, sys, json, time, zipfile, requests, shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import tg_client as tg
from platforms.quark.api import QuarkClient

PROJECT_DIR   = Path(__file__).resolve().parents[1]
COOKIE_FILE   = PROJECT_DIR / "temp" / "bili_cookies_ai_vanvan.json"
PENDING_FILE  = PROJECT_DIR / "temp" / "pending_comments.json"
DOWNLOAD_DIR  = PROJECT_DIR / "temp" / "quark_downloads"
SESSION_FILE  = str(PROJECT_DIR / "temp" / "ai_vanvan_session")

SIZE_LIMIT = 200 * 1024 * 1024  # 200 MB


# ── Instagram 下载 ────────────────────────────────────────────────────────────

def _download_ig_profile(ig_username: str, size_limit: int = SIZE_LIMIT) -> list:
    import instaloader
    from instaloader import Profile

    out_dir = DOWNLOAD_DIR / ig_username
    out_dir.mkdir(parents=True, exist_ok=True)

    loader = instaloader.Instaloader(
        quiet=True,
        save_metadata=False,
        compress_json=False,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    if os.path.exists(SESSION_FILE):
        loader.load_session_from_file("ai_vanvan", SESSION_FILE)
    else:
        raise RuntimeError(f"Instaloader session 文件不存在: {SESSION_FILE}")

    tg.send(f"📥 正在获取 @{ig_username} 的视频列表...")
    profile = Profile.from_username(loader.context, ig_username)

    video_paths = []
    total_bytes = 0
    count = 0

    for post in profile.get_posts():
        if not post.is_video:
            continue
        try:
            out_path = out_dir / f"{post.shortcode}.mp4"
            if out_path.exists():
                size = out_path.stat().st_size
                video_paths.append(str(out_path))
                total_bytes += size
            else:
                tg.send(f"⬇️ 下载第 {count+1} 个视频 ({total_bytes/1024/1024:.1f}MB 已累计)...")
                r = requests.get(post.video_url, stream=True, timeout=60)
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                size = out_path.stat().st_size
                video_paths.append(str(out_path))
                total_bytes += size

            count += 1
            if total_bytes >= size_limit:
                tg.send(f"✅ 已达 {total_bytes/1024/1024:.1f}MB，停止下载（共 {count} 个视频）")
                break
            time.sleep(1)
        except Exception as e:
            tg.send(f"⚠️ 下载 {post.shortcode} 失败: {e}")

    if not video_paths:
        raise RuntimeError(f"@{ig_username} 没有可下载的视频")

    return video_paths


# ── 打包 ──────────────────────────────────────────────────────────────────────

def _zip_videos(video_paths: list, ig_username: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    zip_path = str(PROJECT_DIR / "temp" / f"{ig_username}_{date_str}.zip")
    tg.send(f"📦 正在打包 {len(video_paths)} 个视频...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for vp in video_paths:
            zf.write(vp, os.path.basename(vp))
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    tg.send(f"📦 打包完成：{size_mb:.1f}MB")
    return zip_path


# ── B站回复 ───────────────────────────────────────────────────────────────────

def _get_bili_session():
    if not COOKIE_FILE.exists():
        return None, None
    cookies = json.load(open(COOKIE_FILE))
    session = requests.Session()
    for k, v in cookies.items():
        session.cookies.set(k, v, domain=".bilibili.com")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    })
    csrf = cookies.get("bili_jct", "")
    return session, csrf


def _reply_bilibili(oid: int, rpid: int, message: str) -> bool:
    session, csrf = _get_bili_session()
    if not session or not csrf:
        return False
    try:
        r = session.post(
            "https://api.bilibili.com/x/v2/reply/add",
            data={
                "oid": str(oid),
                "type": "1",
                "root": str(rpid),
                "parent": str(rpid),
                "message": message,
                "csrf": csrf,
            },
            timeout=10,
        )
        return r.json().get("code") == 0
    except Exception:
        return False


def _lookup_pending(rpid: str) -> dict:
    if not PENDING_FILE.exists():
        return {}
    data = json.load(open(PENDING_FILE))
    return data.get(str(rpid), {})


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run(ig_username: str, rpid: str = None):
    tg.send(f"🚀 开始处理 @{ig_username} 的合集分享请求...")

    try:
        video_paths = _download_ig_profile(ig_username)
    except PermissionError as e:
        tg.send(f"❌ Instagram session 问题：{e}")
        return
    except RuntimeError as e:
        tg.send(f"❌ 下载失败：{e}")
        return
    except Exception as e:
        tg.send(f"❌ 下载出错：{e}")
        return

    try:
        zip_path = _zip_videos(video_paths, ig_username)
    except Exception as e:
        tg.send(f"❌ 打包失败：{e}")
        return

    try:
        tg.send(f"☁️ 正在上传到夸克网盘「{QuarkClient().upload_folder}」...")
        client = QuarkClient()
        folder_fid = client.get_or_create_folder(client.upload_folder)
        fid, fid_token = client.upload(zip_path, folder_fid)
    except PermissionError as e:
        tg.send(f"❌ 夸克Cookie已过期：{e}\n请更新 config/quark.json 中的 cookie")
        return
    except Exception as e:
        tg.send(f"❌ 上传夸克失败：{e}")
        return

    try:
        share_url = client.create_share(fid, fid_token, title=f"{ig_username}合集")
    except Exception as e:
        tg.send(f"❌ 创建分享链接失败：{e}")
        return

    bili_reply_ok = False
    if rpid:
        context = _lookup_pending(rpid)
        oid = context.get("oid")
        if oid:
            reply_msg = f"你好！这是 @{ig_username} 的视频合集（7天有效）：{share_url}"
            bili_reply_ok = _reply_bilibili(int(oid), int(rpid), reply_msg)
            if bili_reply_ok:
                fan_uname = context.get("uname", "粉丝")
                tg.send(f"✅ 已在 B站回复 {fan_uname}")
            else:
                tg.send("⚠️ B站回复失败（继续，链接已生成）")
        else:
            tg.send(f"⚠️ 未找到 rpid={rpid} 的评论上下文，跳过 B站回复")

    tg.send(
        f"✅ 分享完成！\n"
        f"📦 @{ig_username} 合集（{len(video_paths)} 个视频）\n"
        f"🔗 {share_url}"
    )

    try:
        os.remove(zip_path)
    except Exception:
        pass
