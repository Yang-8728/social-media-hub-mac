"""
粉丝视频分享：下载IG视频 → 打包zip → 上传夸克 → 生成分享链接 → 回复B站评论。
"""
import os, sys, json, time, zipfile, requests, shutil, threading, re, difflib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import tg_client as tg
from platforms.quark.api import QuarkClient

_ctx = threading.local()

def _send(text, **kwargs):
    tid = getattr(_ctx, "thread_id", tg.TOPIC_SYSTEM)
    tg.send_topic(tid, text, **kwargs)

PROJECT_DIR   = Path(__file__).resolve().parents[1]
COOKIE_FILE   = PROJECT_DIR / "temp" / "bili_cookies_ai_vanvan.json"
PENDING_FILE  = PROJECT_DIR / "temp" / "pending_comments.json"
DOWNLOAD_DIR  = PROJECT_DIR / "videos" / "quark"
SESSION_FILE  = str(PROJECT_DIR / "temp" / "ai_vanvan_session")
SHARE_LOG     = PROJECT_DIR / "logs" / "quark_shares.jsonl"

SIZE_LIMIT = 200 * 1024 * 1024  # 200 MB


def _get_known_igs() -> list[str]:
    """从分享日志和章节记录获取所有已知 IG 账号名"""
    known: set[str] = set()
    # 分享日志
    if SHARE_LOG.exists():
        with open(SHARE_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("ig") and r.get("status") == "ok":
                        known.add(r["ig"])
                except Exception:
                    pass
    # 章节记录（涵盖所有上传过的视频）
    _CHAPTER_PAT = re.compile(r'^\d{1,2}:\d{2}[^\S\r\n]+(\S+)', re.MULTILINE)
    for merge_file in (PROJECT_DIR / "logs" / "merges").glob("*_merged_record.json"):
        try:
            with open(merge_file, encoding="utf-8") as f:
                data = json.load(f)
            for r in data.get("merged_videos", []):
                for m in _CHAPTER_PAT.finditer(r.get("chapter_list", "")):
                    known.add(m.group(1))
        except Exception:
            pass
    return sorted(known)


def _fuzzy_match_ig(raw: str) -> str | None:
    """将 raw 模糊匹配到已知 IG 账号，返回最佳匹配或 None（完全没有近似时）"""
    known = _get_known_igs()
    if not known:
        return None
    if raw in known:
        return raw

    def norm(s: str) -> str:
        return re.sub(r'[_.]', '', s.lower())

    raw_n = norm(raw)
    norm_map = {norm(k): k for k in known}

    if raw_n in norm_map:
        return norm_map[raw_n]

    matches = difflib.get_close_matches(raw_n, list(norm_map.keys()), n=1, cutoff=0.8)
    return norm_map[matches[0]] if matches else None


def _fan_msg(ig_username: str, share_url: str) -> str:
    return (
        f"兄弟！这是 @{ig_username} 的视频合集，复制下面链接，"
        f"再粘贴到浏览器中就能打开夸克网盘了：\n{share_url}\n然后在夸克网盘中转存哦，方便以后再看"
    )


def _write_log(ig_username: str, fan_uname: str, fan_uid: str,
               video_count: int, share_url: str, status: str):
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fan": fan_uname,
        "fan_uid": fan_uid,
        "ig": ig_username,
        "videos": video_count,
        "url": share_url,
        "status": status,
    }
    SHARE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SHARE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Instagram 下载 ────────────────────────────────────────────────────────────

def _get_ig_loader():
    import instaloader
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
    return loader


def _download_ig_profile(ig_username: str, size_limit: int = SIZE_LIMIT) -> list:
    from instaloader import Profile

    out_dir = DOWNLOAD_DIR / ig_username
    out_dir.mkdir(parents=True, exist_ok=True)

    loader = _get_ig_loader()

    print(f"[quark_share] 正在获取 @{ig_username} 的视频列表，下载中...", flush=True)
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
                break
            time.sleep(1)
        except Exception as e:
            _send(f"⚠️ 下载 {post.shortcode} 失败: {e}")

    if not video_paths:
        raise RuntimeError(f"@{ig_username} 没有可下载的视频")

    return video_paths


# ── 码率扩容 ──────────────────────────────────────────────────────────────────

TARGET_SIZE = 210 * 1024 * 1024  # 210MB，留 10MB 余量
FFPROBE = "/opt/homebrew/bin/ffprobe"
FFMPEG  = "/opt/homebrew/bin/ffmpeg"

def _upscale_bitrate(video_paths: list) -> list:
    """当视频总大小 < 200MB 时，重编码提升码率使总大小超过 210MB。"""
    import subprocess

    total_bytes = sum(os.path.getsize(p) for p in video_paths)
    if total_bytes >= 200 * 1024 * 1024:
        return video_paths

    # 算总时长（秒）
    total_duration = 0.0
    for p in video_paths:
        result = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            capture_output=True, text=True
        )
        try:
            total_duration += float(result.stdout.strip())
        except ValueError:
            pass

    if total_duration <= 0:
        return video_paths

    # 目标总码率（bps），audio 约 128kbps，其余全给视频
    target_total_bps = (TARGET_SIZE * 8) / total_duration
    video_bps = int(target_total_bps - 128_000)
    if video_bps <= 0:
        return video_paths

    print(f"[quark_share] 视频总大小 {total_bytes/1024/1024:.1f}MB < 200MB，正在升码率...", flush=True)

    new_paths = []
    for p in video_paths:
        out = p + ".upscaled.mp4"
        subprocess.run(
            [FFMPEG, "-y", "-i", p, "-c:v", "libx264",
             "-b:v", str(video_bps), "-minrate", str(video_bps),
             "-maxrate", str(video_bps), "-bufsize", str(video_bps),
             "-x264-params", "nal-hrd=cbr:force-cfr=1",
             "-c:a", "copy", out],
            capture_output=True
        )
        if os.path.exists(out) and os.path.getsize(out) > 0:
            os.remove(p)
            os.rename(out, p)
        new_paths.append(p)

    new_total = sum(os.path.getsize(p) for p in new_paths)
    print(f"[quark_share] 升码率完成：{new_total/1024/1024:.1f}MB", flush=True)
    return new_paths


# ── 打包 ──────────────────────────────────────────────────────────────────────

def _zip_videos(video_paths: list, ig_username: str, uid: str = None) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    name = f"{uid}_{ig_username}_{date_str}" if uid else f"{ig_username}_{date_str}"
    zip_path = str(PROJECT_DIR / "temp" / f"{name}.zip")
    print(f"[quark_share] 正在打包 {len(video_paths)} 个视频...", flush=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for vp in video_paths:
            zf.write(vp, os.path.basename(vp))
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"[quark_share] 打包完成：{size_mb:.1f}MB", flush=True)
    for vp in video_paths:
        try:
            os.remove(vp)
        except Exception:
            pass
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

def _send_dm_reply(uid: str, ig_username: str, share_url: str):
    """通过 B站私信把夸克链接发给粉丝"""
    from platforms.bilibili.monitor import send_dm, get_bilibili_session, get_csrf
    try:
        sess = get_bilibili_session()
        csrf = get_csrf(sess)
        msg = _fan_msg(ig_username, share_url)
        ok = send_dm(sess, csrf, int(uid), msg)
        if ok:
            _send(f"✅ 已通过私信发送链接给 UID {uid}")
        else:
            _send(f"⚠️ 私信发送失败（链接已生成）")
    except Exception as e:
        _send(f"⚠️ 私信发送出错：{e}（链接已生成）")


CACHE_DAYS = 7


def _lookup_cached_url(ig_username: str) -> str | None:
    """查 quark_shares.jsonl，7天内有成功记录则返回链接，否则 None。"""
    if not SHARE_LOG.exists():
        return None
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=CACHE_DAYS)
    best = None
    with open(SHARE_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ig") != ig_username or r.get("status") != "ok":
                continue
            try:
                t = datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if t >= cutoff:
                best = r
    return best["url"] if best else None


def run(ig_username: str, target: str = None, thread_id: int = None):
    """
    target 格式：
      dm:<uid>  → 回复 B站私信
      <rpid>    → 回复 B站评论
      None      → 不自动回复
    """
    if thread_id is None:
        thread_id = tg.TOPIC_DM if (target and target.startswith("dm:")) else tg.TOPIC_COMMENT
    _ctx.thread_id = thread_id

    fan_label = None
    uid_val = None
    if target and target.startswith("dm:"):
        parts = target[3:].split(":", 1)
        uid_val = parts[0]
        fan_label = parts[1].replace("_", " ") if len(parts) > 1 else uid_val

    matched = _fuzzy_match_ig(ig_username)
    if matched and matched != ig_username:
        _send(f"ℹ️ @{ig_username} 未找到，自动匹配为 @{matched}")
        ig_username = matched

    cached_url = _lookup_cached_url(ig_username)
    if cached_url:
        print(f"[quark_share] @{ig_username} 7天内已上传过，复用现有链接", flush=True)
        if target:
            if target.startswith("dm:"):
                _send_dm_reply(uid_val, ig_username, cached_url)
            else:
                rpid = target
                context = _lookup_pending(rpid)
                oid = context.get("oid")
                if oid:
                    reply_msg = _fan_msg(ig_username, cached_url)
                    ok = _reply_bilibili(int(oid), int(rpid), reply_msg)
                    fan_label = context.get("uname", "粉丝")
                    if not ok:
                        _send(f"⚠️ B站回复失败（链接已生成）")
        recipient = fan_label or "（无指定接收人）"
        fan_text = _fan_msg(ig_username, cached_url)
        done_msg = (
            f"✅ 分享完成（缓存）！\n"
            f"👤 分享给：{recipient}\n"
            f"📦 @{ig_username} 合集\n"
            f"🔗 {cached_url}\n\n"
            f"— 发给粉丝的消息 —\n{fan_text}"
        )
        _send(done_msg, no_preview=True)
        return

    print(f"[quark_share] 开始处理 @{ig_username} 的合集分享请求", flush=True)

    try:
        video_paths = _download_ig_profile(ig_username)
    except PermissionError as e:
        _send(f"❌ Instagram session 问题：{e}")
        return
    except RuntimeError as e:
        _send(f"❌ 下载失败：{e}")
        return
    except Exception as e:
        _send(f"❌ 下载出错：{e}")
        return

    try:
        video_paths = _upscale_bitrate(video_paths)
        zip_path = _zip_videos(video_paths, ig_username, uid=fan_label)
    except Exception as e:
        _send(f"❌ 打包失败：{e}")
        return

    try:
        print(f"[quark_share] 正在上传到夸克网盘...", flush=True)
        client = QuarkClient()
        folder_fid = client.get_or_create_folder(client.upload_folder)
        fid, fid_token = client.upload(zip_path, folder_fid)
    except PermissionError as e:
        _send(f"❌ 夸克Cookie已过期：{e}\n请更新 config/quark.json 中的 cookie")
        return
    except Exception as e:
        _send(f"❌ 上传夸克失败：{e}")
        return

    try:
        share_url = client.create_share(fid, fid_token, title=f"{ig_username}合集")
    except Exception as e:
        _send(f"❌ 创建分享链接失败：{e}")
        return

    if target:
        if target.startswith("dm:"):
            _send_dm_reply(uid_val, ig_username, share_url)
        else:
            rpid = target
            context = _lookup_pending(rpid)
            oid = context.get("oid")
            if oid:
                reply_msg = _fan_msg(ig_username, share_url)
                ok = _reply_bilibili(int(oid), int(rpid), reply_msg)
                fan_uname = context.get("uname", "粉丝")
                fan_label = fan_uname
                if not ok:
                    _send(f"⚠️ B站回复失败（链接已生成）")
            else:
                print(f"[quark_share] 未找到 rpid={rpid} 的评论上下文，跳过回复", flush=True)

    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    recipient = fan_label if fan_label else "（无指定接收人）"
    fan_text = _fan_msg(ig_username, share_url)
    done_msg = (
        f"✅ 分享完成！\n"
        f"👤 分享给：{recipient}\n"
        f"📦 @{ig_username} 合集（{len(video_paths)} 个视频）\n"
        f"🕐 时间：{now_str}\n"
        f"🔗 {share_url}\n\n"
        f"— 发给粉丝的消息 —\n{fan_text}"
    )
    _send(done_msg, no_preview=True)

    _write_log(
        ig_username=ig_username,
        fan_uname=fan_label or "",
        fan_uid=uid_val if target and target.startswith("dm:") else "",
        video_count=len(video_paths),
        share_url=share_url,
        status="ok",
    )

    try:
        os.remove(zip_path)
    except Exception:
        pass
