"""
B站评论监控 + 垃圾评论清理。
合并了原 features/comment_monitor.py 和 features/spam_cleaner.py。
"""
import os, re, sys, time, json, threading, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from platforms.bilibili import monitor as bili_monitor
from bot import tg_client as tg
from bot import interaction_queue as iq

# ── 垃圾关键词 ────────────────────────────────────────────────────────────────

SPAM_KEYWORDS = [
    "原片出处", "原片在", "完整版在", "高清原版", "完整资源",
    "我动态有", "动态里有", "动态已分享", "看看我动态", "看我动态",
    "主页有", "点主页", "进主页", "看我主页", "点我头像",
    "关注有福利", "关注我有", "关注拿",
    "看完别打", "看完你别打", "看完记得别打", "忍住", "胆小勿入", "不敢看", "不敢点",
    "你懂的", "懂的都懂", "不解释", "自己悟",
    "羡慕吗", "心动了吗", "眼熟吗",
    "福利视频", "福利资源", "涩涩", "18+",
    "不删除", "限时分享", "今天删", "马上删", "即将删除",
    "免费领", "白嫖", "自取", "资源合集", "打包发",
    "私信我", "发我私信", "私聊我", "私我",
    "加微信", "加vx", "加wx", "加V", "威信", "微♥信",
    "加好友", "加我好友",
    "bili2233", "bilibili2", "b站福利",
    "自补后", "自补前", "自己补",
    "动态已分享", "已转发", "已收藏求回关",
    "看完关注", "资源私发", "原视频私发",
    "aauc", "当作点就欧克", "合集有",
    "浏览记录",
    "补上三个小尾巴", "补上尾巴", "加上三个字", "补全链接", "自行补全",
    "后面加", "后面补", "结尾加", "结尾补",
]

URL_RE    = re.compile(r'https?://\S+|b23\.tv/\S*|BV[a-zA-Z0-9]{10}', re.IGNORECASE)
_B23_RE   = re.compile(r'b23\.tv/', re.IGNORECASE)
_IMG_RE = re.compile(r'\[[^\[\]]{3,}\]')

# ── 文件路径 ──────────────────────────────────────────────────────────────────

PROJECT_DIR        = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOKIE_FILE        = os.path.join(PROJECT_DIR, "temp", "bili_cookies_ai_vanvan.json")
CUSTOM_KW_FILE     = os.path.join(PROJECT_DIR, "config", "spam_keywords_custom.json")
REPLY_TARGETS_FILE = os.path.join(PROJECT_DIR, "temp", "reply_targets.json")
PENDING_FILE       = os.path.join(PROJECT_DIR, "temp", "pending_comments.json")
DELETE_SKIP_FILE   = os.path.join(PROJECT_DIR, "temp", "delete_skip.json")

ACCOUNT_NAME  = "ai_vanvan"
MAX_VIDEOS    = 3
INTERVAL      = 30
SCAN_INTERVAL = 7200  # 全量扫描间隔（秒），2小时
SCAN_VIDEOS   = 5     # 每次扫最近几个视频
MAX_REPLY_TARGETS = 200

# ── 自定义关键词 ──────────────────────────────────────────────────────────────

def _load_custom_keywords() -> list:
    if os.path.exists(CUSTOM_KW_FILE):
        try:
            return json.load(open(CUSTOM_KW_FILE))
        except Exception:
            pass
    return []

def add_keyword(kw: str):
    kws = _load_custom_keywords()
    if kw not in kws:
        kws.append(kw)
        with open(CUSTOM_KW_FILE, "w") as f:
            json.dump(kws, f, ensure_ascii=False, indent=2)
    return kws

# ── Reply 目标存储 ─────────────────────────────────────────────────────────────

def _load_reply_targets() -> dict:
    try:
        if os.path.exists(REPLY_TARGETS_FILE):
            data = json.load(open(REPLY_TARGETS_FILE))
            return {int(k): v for k, v in data.items()}
    except Exception:
        pass
    return {}

def _save_reply_targets(targets: dict):
    try:
        with open(REPLY_TARGETS_FILE, "w") as f:
            json.dump(targets, f, ensure_ascii=False)
    except Exception as e:
        print(f"[bilibili_comments] 保存 reply_targets 失败: {e}", flush=True)

_reply_targets: dict = _load_reply_targets()

def register_reply_target(msg_id: int, oid, rpid, uname: str):
    _reply_targets[msg_id] = {"type": "comment", "oid": oid, "rpid": rpid, "uname": uname}
    if len(_reply_targets) > MAX_REPLY_TARGETS:
        del _reply_targets[next(iter(_reply_targets))]
    _save_reply_targets(_reply_targets)

def register_dm_target(msg_id: int, uid, uname: str, ig_username: str = None):
    _reply_targets[msg_id] = {"type": "dm", "uid": uid, "uname": uname, "ig": ig_username}
    if len(_reply_targets) > MAX_REPLY_TARGETS:
        del _reply_targets[next(iter(_reply_targets))]
    _save_reply_targets(_reply_targets)

def lookup_reply_target(msg_id: int):
    if msg_id in _reply_targets:
        return _reply_targets[msg_id]
    # 外部脚本可能写入了文件但未更新内存，重新加载一次
    fresh = _load_reply_targets()
    if msg_id in fresh:
        _reply_targets.update(fresh)
        return _reply_targets[msg_id]
    return None

# ── 待回复上下文存储 ──────────────────────────────────────────────────────────

def _save_pending(item: dict):
    rpid = str(item.get("rpid", ""))
    if not rpid or rpid == "0":
        return
    try:
        data = {}
        if os.path.exists(PENDING_FILE):
            try:
                data = json.load(open(PENDING_FILE))
            except Exception:
                pass
        data[rpid] = {
            "oid":   item.get("oid"),
            "rpid":  item.get("rpid"),
            "uid":   item.get("uid"),
            "uname": item.get("uname"),
            "bvid":  item.get("bvid"),
            "ts":    time.time(),
        }
        sorted_items = sorted(data.items(), key=lambda x: x[1].get("ts", 0), reverse=True)
        data = dict(sorted_items[:20])
        with open(PENDING_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[bilibili_comments] _save_pending 失败: {e}", flush=True)

# ── 垃圾检测 ──────────────────────────────────────────────────────────────────

_NORMALIZE_RE = re.compile(r'[!！@#$%^&*()【】\[\]{}<>|\\/:;\'",.\s]')

def _normalize(text: str) -> str:
    """去除常见插字符，防止「我动态!有」之类的标点拆词绕过。"""
    return _NORMALIZE_RE.sub("", text)

def _is_spam(text: str) -> str | None:
    if _B23_RE.search(text):
        return "含b23.tv链接"
    normalized = _normalize(text)
    for kw in SPAM_KEYWORDS + _load_custom_keywords():
        if kw in text or kw in normalized:
            return f"关键词: {kw}"
    return None

def _is_uncertain(text: str) -> str | None:
    if URL_RE.search(text):
        return "含链接"
    if _IMG_RE.search(text):
        return "含图片"
    return None

# ── B站 session（requests，无需 Selenium）────────────────────────────────────

def _get_session():
    if not os.path.exists(COOKIE_FILE):
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

def _get_my_uid() -> str:
    try:
        cookies = json.load(open(COOKIE_FILE))
        return str(cookies.get("DedeUserID", ""))
    except Exception:
        return ""


def _scan_sub_replies(oid, rpid) -> str | None:
    """检查某条评论的子回复，自动删除垃圾，返回通知文本（无垃圾则返回 None）"""
    session, _ = _get_session()
    if not session:
        return None
    try:
        subs = bili_monitor.fetch_sub_replies(session, oid, rpid)
    except Exception:
        return None
    if not subs:
        return None

    my_uid = _get_my_uid()
    deleted, failed = [], []
    for sub in subs:
        if str(sub["uid"]) == my_uid:
            continue
        reason = _is_spam(sub["content"])
        if not reason:
            continue
        ok = _delete_comment(oid, sub["rpid"])
        _blacklist_user(sub["uid"]) if ok and sub["uid"] else None
        if ok:
            deleted.append(f"👤 {tg.esc(sub['uname'])}：{tg.esc(sub['content'][:50])}")
        else:
            failed.append(sub["uname"])

    if not deleted and not failed:
        return None
    lines = [f"🧹 楼中楼清理：删除 {len(deleted)} 条" + (f"，失败 {len(failed)} 条" if failed else "")]
    lines.extend(deleted)
    return "\n".join(lines)


def _get_scan_oids() -> list[str]:
    """从 pending_comments.json 收集近期活跃视频的 OID，去重后返回。"""
    oids = []
    try:
        data = json.load(open(PENDING_FILE))
        seen = set()
        for item in data.values():
            oid = str(item.get("oid", ""))
            if oid and oid not in seen:
                seen.add(oid)
                oids.append(oid)
    except Exception:
        pass
    return oids[:SCAN_VIDEOS]


def _full_scan(label="定期"):
    """主动扫描近期活跃视频的所有评论+楼中楼，自动删除垃圾，TG 汇报统计。"""
    session, _ = _get_session()
    if not session:
        return
    my_uid = _get_my_uid()

    oids = _get_scan_oids()
    if not oids:
        print(f"[bilibili_comments] {label}扫描：无活跃视频 OID，跳过", flush=True)
        return

    deleted = failed = 0
    for aid in oids:
        if not aid:
            continue
        pn = 1
        while True:
            try:
                r = session.get(
                    "https://api.bilibili.com/x/v2/reply",
                    params={"oid": aid, "type": 1, "pn": pn, "ps": 20, "sort": 0},
                    timeout=10,
                )
                data  = r.json().get("data") or {}
                replies = data.get("replies") or []
            except Exception:
                break
            if not replies:
                break

            for reply in replies:
                member = reply.get("member") or {}
                uid    = str(member.get("mid", ""))
                rpid   = reply.get("rpid", 0)
                text   = (reply.get("content") or {}).get("message", "")
                if uid != my_uid and _is_spam(text):
                    ok = _delete_comment(aid, rpid)
                    if ok is True:
                        _blacklist_user(uid) if uid else None
                        deleted += 1
                    elif ok is False:
                        failed += 1

                if reply.get("rcount", 0) > 0:
                    try:
                        subs = bili_monitor.fetch_sub_replies(session, aid, rpid)
                        for sub in subs:
                            if str(sub["uid"]) == my_uid:
                                continue
                            if _is_spam(sub["content"]):
                                ok = _delete_comment(aid, sub["rpid"])
                                if ok is True:
                                    _blacklist_user(sub["uid"]) if sub["uid"] else None
                                    deleted += 1
                                elif ok is False:
                                    failed += 1
                    except Exception:
                        pass
                time.sleep(0.1)

            page = data.get("page") or {}
            if pn * 20 >= page.get("count", 0):
                break
            pn += 1
            time.sleep(0.3)

    summary = f"🔍 {label}扫描完成：删除 {deleted} 条垃圾评论" + (f"，失败 {failed} 条" if failed else "")
    print(f"[bilibili_comments] {summary}", flush=True)
    if deleted:
        tg.send(summary)


def _load_delete_skip() -> set:
    try:
        if os.path.exists(DELETE_SKIP_FILE):
            return set(json.load(open(DELETE_SKIP_FILE)))
    except Exception:
        pass
    return set()

def _save_delete_skip(skip: set):
    try:
        with open(DELETE_SKIP_FILE, "w") as f:
            json.dump(list(skip), f)
    except Exception:
        pass

_delete_skip: set = _load_delete_skip()

def _delete_comment(oid, rpid):
    """返回 True=删成功，False=删失败，None=已跳过"""
    if str(rpid) in _delete_skip:
        return None
    session, csrf = _get_session()
    if not session or not csrf:
        return False
    try:
        r = session.post(
            "https://api.bilibili.com/x/v2/reply/del",
            data={"oid": str(oid), "type": "1", "rpid": str(rpid), "csrf": csrf},
            timeout=10
        )
        resp = r.json()
        code = resp.get("code")
        if code != 0:
            print(f"[bilibili_comments] 删除失败 oid={oid} rpid={rpid} code={code} msg={resp.get('message')}", flush=True)
            if code == -403:
                _delete_skip.add(str(rpid))
                _save_delete_skip(_delete_skip)
        return code == 0
    except Exception:
        return False

def _blacklist_user(uid) -> bool:
    session, csrf = _get_session()
    if not session or not csrf or not uid:
        return False
    try:
        r = session.post(
            "https://api.bilibili.com/x/relation/modify",
            data={"fid": str(uid), "act": "5", "re_src": "11", "csrf": csrf},
            timeout=10
        )
        return r.json().get("code") == 0
    except Exception:
        return False

# ── IG 账号识别 ───────────────────────────────────────────────────────────────

_CHAPTER_RE = re.compile(r'^\d{1,2}:\d{2}[ \t]+(\S+)', re.MULTILINE)
_IG_NAME_RE = re.compile(r'^([A-Za-z0-9._]{3,30})$', re.MULTILINE)
# 匹配两个单词组成的名字，如 "mckinley bethel"
_IG_FUZZY_RE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z0-9]{2,20})\s+([A-Za-z0-9]{2,20})(?![A-Za-z0-9])')

def _resolve_ig_username(raw: str) -> str | None:
    """把可能带空格的名字尝试各种连接符，返回第一个存在的 IG 用户名，找不到返回 None。"""
    parts = raw.strip().lower().split()
    if len(parts) == 1:
        return raw.strip()
    candidates = [
        ".".join(parts),
        "_".join(parts),
        "".join(parts),
    ]
    try:
        from instaloader import Instaloader, Profile, exceptions as il_ex
        from pipelines.quark_share import _get_ig_loader
        loader = _get_ig_loader()
        for c in candidates:
            try:
                Profile.from_username(loader.context, c)
                return c
            except il_ex.ProfileNotExistsException:
                continue
            except Exception:
                break
    except Exception:
        pass
    return candidates[0]  # 找不到就用点连接兜底

def _extract_ig_from_history(history: list) -> list:
    """从私信历史里提取 IG 账号名（章节格式优先，兜底用裸账号正则，再兜底模糊两词匹配）"""
    names = []
    for h in history:
        if h.get("from_me"):
            continue
        for m in _CHAPTER_RE.finditer(h.get("text", "")):
            name = m.group(1)
            if name not in names:
                names.append(name)
    if not names:
        for h in history:
            if h.get("from_me"):
                continue
            for m in _IG_NAME_RE.finditer(h.get("text", "").strip()):
                name = m.group(1)
                if name not in names:
                    names.append(name)
    if not names:
        for h in history:
            if h.get("from_me"):
                continue
            for m in _IG_FUZZY_RE.finditer(h.get("text", "")):
                raw = m.group(0)
                resolved = _resolve_ig_username(raw)
                if resolved and resolved not in names:
                    names.append(resolved)
    return names


# ── 消息格式化 ────────────────────────────────────────────────────────────────

def _format_fan(item: dict) -> str | None:
    t     = item.get("type")
    uname = tg.esc(item.get("uname", "?"))

    if t == "reply":
        content = tg.esc(item.get("content", "")[:120])
        title   = tg.esc(item.get("video_title", "")[:40])
        bvid    = item.get("bvid", "")
        rpid    = item.get("rpid", "")
        comment_url = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
        msg = f"💬 *{uname}* 评论了你的视频\n"
        if title:
            msg += f"🎬 《{title}》\n"
        msg += f"📝 {content}"
        if comment_url:
            msg += f"\n🔗 {tg.link('查看评论', comment_url)}"
        return msg

    elif t == "at":
        content = tg.esc(item.get("content", "")[:120])
        title   = tg.esc(item.get("video_title", "")[:40])
        bvid    = item.get("bvid", "")
        rpid    = item.get("rpid", "")
        comment_url = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
        msg = f"📣 *{uname}* @了你\n"
        if title:
            msg += f"🎬 《{title}》\n"
        msg += f"📝 {content}"
        if comment_url:
            msg += f"\n🔗 {tg.link('查看评论', comment_url)}"
        return msg

    elif t == "dm":
        uid     = item.get("uid", "")
        unread  = item.get("unread", 1)
        history = item.get("history", [])
        msg = f"✉️ *{uname}*（UID: {uid}）发来私信"
        if unread > 1:
            msg += f"（{unread}条未读）"
        if history:
            msg += "\n\n*历史消息：*"
            for h in history[-10:]:
                who = "➡️ 我" if h["from_me"] else f"👤 {uname}"
                msg += f"\n{who}：{tg.esc(h['text'][:80])}"
        # 检测历史消息里是否含章节格式（时间戳 + IG账号名）
        ig_names = _extract_ig_from_history(history)
        if ig_names:
            msg += f"\n\n🔍 检测到 IG 账号：`{tg.esc(ig_names[0])}`\n"
            msg += f"👉 回复此消息发送 `/share`"
        return msg

    elif t == "error":
        return f"⚠️ B站监控错误：{tg.esc(item.get('content', ''))}"

    return None

# ── 视频文件清理 ──────────────────────────────────────────────────────────────

VIDEO_LIMIT_BYTES = 10 * 1024 ** 3  # 10GB

def _cleanup_videos():
    dirs = [
        os.path.join(PROJECT_DIR, "videos", "downloads"),
        os.path.join(PROJECT_DIR, "videos", "merged"),
    ]
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, fnames in os.walk(d):
            for fn in fnames:
                fp = os.path.join(root, fn)
                try:
                    files.append((os.path.getmtime(fp), os.path.getsize(fp), fp))
                except Exception:
                    pass
    total = sum(s for _, s, _ in files)
    if total <= VIDEO_LIMIT_BYTES:
        return
    files.sort()  # 最旧的在前
    deleted_bytes = 0
    for mtime, size, fp in files:
        if total - deleted_bytes <= VIDEO_LIMIT_BYTES:
            break
        try:
            os.remove(fp)
            deleted_bytes += size
            print(f"[bilibili_comments] 清理旧视频: {fp}", flush=True)
        except Exception:
            pass
    if deleted_bytes:
        print(f"[bilibili_comments] 视频清理完成，释放 {deleted_bytes/1024**3:.1f}GB", flush=True)


# ── 主监控循环（后台线程）────────────────────────────────────────────────────

def run():
    print(f"[bilibili_comments] 启动监控，轮询间隔 {INTERVAL}s", flush=True)
    backlog = []
    while True:
        items = bili_monitor.poll()
        if not items:
            break
        backlog.extend(items)

    if backlog:
        print(f"[bilibili_comments] 发现 {len(backlog)} 条积压通知，开始处理", flush=True)
        _process_items(backlog, offline_prefix="[离线期间] ")

    threading.Thread(target=_cleanup_videos, daemon=True).start()
    # 启动时立即做一次全量扫描
    threading.Thread(target=_full_scan, args=("启动",), daemon=True).start()

    last_scan = time.time()
    while True:
        try:
            items = bili_monitor.poll()
            if items:
                if iq.is_interactive():
                    print(f"[bilibili_comments] 交互模式中，暂存 {len(items)} 条通知", flush=True)
                else:
                    _process_items(items)
        except Exception as e:
            print(f"[bilibili_comments] 异常: {e}", flush=True)

        if time.time() - last_scan >= SCAN_INTERVAL:
            last_scan = time.time()
            threading.Thread(target=_full_scan, args=("定期",), daemon=True).start()

        time.sleep(INTERVAL)


def _process_items(items, offline_prefix=""):
    seen_rpids = set()
    for item in items:
        if item.get("type") not in ("reply", "at", "dm", "error"):
            continue

        dedup_key = item.get("rpid") or (f"dm_{item.get('uid')}" if item.get("type") == "dm" else None)
        if dedup_key and dedup_key in seen_rpids:
            continue
        if dedup_key:
            seen_rpids.add(dedup_key)

        content = item.get("content", "")
        if item.get("type") in ("reply", "at"):
            _save_pending(item)

        is_comment = item.get("type") in ("reply", "at")
        spam_reason      = _is_spam(content)     if is_comment else None
        uncertain_reason = _is_uncertain(content) if is_comment and not spam_reason else None

        if is_comment and not spam_reason and not uncertain_reason:
            try:
                sess, _ = _get_session()
                if sess and bili_monitor.fetch_comment_has_images(
                        sess, item.get("oid"), item.get("rpid")):
                    uncertain_reason = "含图片"
            except Exception:
                pass

        if spam_reason:
            oid   = item.get("oid")
            rpid  = item.get("rpid")
            uid   = item.get("uid") or item.get("mid")
            uname = item.get("uname", "?")
            bvid  = item.get("bvid", "")
            ok    = _delete_comment(oid, rpid) if oid and rpid else False
            bl    = _blacklist_user(uid) if ok and uid else False
            status = "已删除" + ("＋已拉黑" if bl else "") if ok else "删除失败"
            comment_url = f"https://www.bilibili.com/video/{bvid}?comment_root_id={rpid}" if bvid and rpid else ""
            msg = (
                f"🗑️ 自动删除垃圾评论\n"
                f"👤 {tg.esc(uname)}\n"
                f"🏷️ {tg.esc(spam_reason)}\n"
                f"📝 {tg.esc(content[:80])}\n"
                f"{'✅' if ok else '❌'} {status}"
            )
            if comment_url:
                msg += f"\n🔗 {tg.link('查看评论', comment_url)}"
            tg.send_md(msg, no_preview=True)
            sub_msg = _scan_sub_replies(oid, rpid)
            if sub_msg:
                tg.send_md(sub_msg)

        elif uncertain_reason and is_comment and not offline_prefix:
            oid2        = item.get("oid")
            rpid2       = item.get("rpid")
            uid2        = item.get("uid")
            raw_uname   = item.get("uname", "?")
            raw_title   = item.get("video_title", "")[:40]
            raw_content = item.get("content", "")[:120]
            bvid2       = item.get("bvid", "")
            comment_url2 = (f"https://www.bilibili.com/video/{bvid2}?comment_root_id={rpid2}"
                            if bvid2 and rpid2 else "")
            plain = f"💬 {raw_uname} 评论了你的视频"
            if raw_title:
                plain += f"\n🎬 《{raw_title}》"
            plain += f"\n📝 {raw_content}"
            if comment_url2:
                plain += f"\n🔗 {comment_url2}"
            ask_msg = (plain + f"\n\n⚠️ {uncertain_reason}，判断不了"
                       f"\n❓ 垃圾？1 删除+拉黑+加词库，0 跳过，Reply 直接回复")
            ev = threading.Event()
            def _unc_cb(ans, _oid=oid2, _rpid=rpid2, _uid=uid2, _content=content, _ev=ev):
                ans = ans.strip()
                if ans in ("y", "1"):
                    ok = _delete_comment(_oid, _rpid)
                    _blacklist_user(_uid) if ok and _uid else None
                    if ok:
                        add_keyword(_content)
                        tg.send(f"✅ 已删除+已拉黑，关键词「{_content[:50]}」已加入词库")
                    else:
                        tg.send("❌ 删除失败")
                else:
                    tg.send("⏭ 已跳过")
                _ev.set()
            _oid2, _rpid2, _uname2 = oid2, rpid2, item.get("uname", "")
            def _on_sent(mid, _o=_oid2, _r=_rpid2, _u=_uname2):
                register_reply_target(mid, _o, _r, _u)
            iq.push(ask_msg, _unc_cb, on_sent=_on_sent, no_preview=True)
            ev.wait()
            ev.clear()
            sub_msg = _scan_sub_replies(oid2, rpid2)
            if sub_msg:
                tg.send_md(sub_msg)

        else:
            msg = _format_fan(item)
            if not msg:
                continue
            prefix_md = f"_{tg.esc(offline_prefix.strip())}_\n" if offline_prefix else ""

            if is_comment and not offline_prefix:
                oid2  = item.get("oid")
                rpid2 = item.get("rpid")
                mid = tg.send_md(prefix_md + msg, no_preview=True)
                if mid and oid2 and rpid2:
                    register_reply_target(mid, oid2, rpid2, item.get("uname", ""))
                sub_msg = _scan_sub_replies(oid2, rpid2)
                if sub_msg:
                    tg.send_md(sub_msg, no_preview=True)

            elif item.get("type") == "dm" and not offline_prefix:
                dm_uid   = item.get("uid")
                dm_uname = item.get("uname", str(dm_uid))
                ig_names = _extract_ig_from_history(item.get("history", []))
                ig_detected = ig_names[0] if ig_names else None
                mid = tg.send_md(msg + "\n\n_💬 直接回复此消息即可发送私信_", no_preview=True)
                if mid and dm_uid:
                    register_dm_target(mid, dm_uid, dm_uname, ig_username=ig_detected)

            else:
                tg.send_md(prefix_md + msg, no_preview=True)

        time.sleep(0.3)

# ── Selenium 驱动（垃圾评论清理用）──────────────────────────────────────────

def _make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    profile_path = os.path.join(PROJECT_DIR, "tools", "profiles", f"chrome_profile_{ACCOUNT_NAME}")
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        p = os.path.join(profile_path, lock)
        if os.path.exists(p):
            os.remove(p)

    opts = Options()
    opts.add_argument(f"--user-data-dir={profile_path}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--window-size=1200,800")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

    driver = webdriver.Chrome(options=opts)
    driver.set_script_timeout(30)
    return driver

# ── Selenium B站 API ──────────────────────────────────────────────────────────

def _api_get(driver, url):
    return driver.execute_async_script("""
        const [url, cb] = arguments;
        fetch(url, {credentials: 'include'})
            .then(r => r.json()).then(cb)
            .catch(e => cb({error: e.toString()}));
    """, url)

def _api_post(driver, url, data):
    return driver.execute_async_script("""
        const [url, data, cb] = arguments;
        fetch(url, {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams(data).toString()
        }).then(r => r.json()).then(cb)
          .catch(e => cb({error: e.toString()}));
    """, url, data)

def _get_csrf(driver):
    return driver.execute_script("""
        for (const c of document.cookie.split(';')) {
            const [k, v] = c.trim().split('=');
            if (k === 'bili_jct') return v;
        }
        return null;
    """)

def _get_uid(driver):
    r = _api_get(driver, "https://api.bilibili.com/x/web-interface/nav")
    return str(r["data"]["mid"]) if r and r.get("code") == 0 else None

def _get_videos(driver, uid, limit=MAX_VIDEOS):
    driver.get(f"https://space.bilibili.com/{uid}/video")
    time.sleep(5)
    videos = driver.execute_script("""
        const links = document.querySelectorAll('a[href*="/video/BV"]');
        const seen = new Set(), result = [];
        for (const a of links) {
            const m = a.href.match(/\\/video\\/(BV\\w+)/);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);
            result.push({bvid: m[1], title: a.title || a.textContent.trim()});
        }
        return result;
    """)
    return [(v["bvid"], v["title"]) for v in (videos or [])[:limit]]

def _bv_to_aid(driver, bvid):
    r = _api_get(driver, f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    return str(r["data"]["aid"]) if r and r.get("code") == 0 else None

def _fetch_sub_replies(driver, aid, rpid):
    subs, pn = [], 1
    while True:
        data = _api_get(driver, f"https://api.bilibili.com/x/v2/reply/reply?oid={aid}&type=1&root={rpid}&ps=20&pn={pn}")
        page = ((data.get("data") or {}).get("replies")) or []
        if not page:
            break
        subs.extend(page)
        if ((data.get("data") or {}).get("cursor") or {}).get("is_end", True):
            break
        pn += 1
        time.sleep(0.3)
    return subs

def _is_spam_selenium(text):
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return f"关键词: {kw}"
    if URL_RE.search(text):
        return "含链接"
    return None

def _ask_delete(driver, aid, rpid, uid, uname, text, csrf, blacklisted, label, event):
    reason  = _is_spam_selenium(text)
    preview = text[:80].replace("\n", " ")
    msg = (
        f"🗑️ [垃圾评论]{label}\n"
        f"👤 {uname}\n"
        f"🏷️ 原因: {reason}\n"
        f"💬 {preview}\n\n"
        f"删除？1/y 删除，0/n 跳过"
    )
    def callback(answer):
        if answer.strip().lower() in ("1", "y"):
            r = _api_post(driver, "https://api.bilibili.com/x/v2/reply/del",
                          {"oid": aid, "type": "1", "rpid": rpid, "csrf": csrf})
            if r and r.get("code") == 0:
                tg.send("✅ 已删除")
                if uid and uid not in blacklisted:
                    _api_post(driver, "https://api.bilibili.com/x/relation/modify",
                              {"fid": uid, "act": "5", "re_src": "11", "csrf": csrf})
                    blacklisted.add(uid)
                    tg.send(f"🚫 已拉黑 UID {uid}")
            else:
                tg.send(f"❌ 删除失败: {r}")
        else:
            tg.send("⏭ 已跳过")
        event.set()
    iq.push(msg, callback)
    event.wait()
    event.clear()

def _scan_and_delete(driver, uid, auto=False):
    csrf = _get_csrf(driver)
    if not csrf or not uid:
        tg.send("❌ 未检测到登录状态")
        return

    videos = _get_videos(driver, uid)
    print(f"[bilibili_comments] 找到 {len(videos)} 个视频", flush=True)
    tg.send(f"📋 共找到 {len(videos)} 个视频，开始{'自动' if auto else ''}扫描...")

    driver.get("https://www.bilibili.com")
    time.sleep(2)
    csrf = _get_csrf(driver)

    deleted = skipped = failed = 0
    event = threading.Event()

    for bvid, title in videos:
        driver.get(f"https://www.bilibili.com/video/{bvid}")
        time.sleep(2)
        csrf = _get_csrf(driver)

        aid = _bv_to_aid(driver, bvid)
        if not aid:
            continue

        blacklisted = set()
        pn = 1

        while True:
            data    = _api_get(driver, f"https://api.bilibili.com/x/v2/reply?oid={aid}&type=1&pn={pn}&ps=20&sort=0")
            inner   = (data.get("data") or {})
            replies = inner.get("replies") or []
            if not replies:
                break

            for reply in replies:
                rpid  = str(reply.get("rpid", ""))
                text  = (reply.get("content") or {}).get("message", "")
                r_uid = str((reply.get("member") or {}).get("mid", ""))
                uname = (reply.get("member") or {}).get("uname", "")

                if r_uid != uid and _is_spam_selenium(text):
                    if auto:
                        r = _api_post(driver, "https://api.bilibili.com/x/v2/reply/del",
                                      {"oid": aid, "type": "1", "rpid": rpid, "csrf": csrf})
                        if r and r.get("code") == 0:
                            deleted += 1
                            if r_uid and r_uid not in blacklisted:
                                _api_post(driver, "https://api.bilibili.com/x/relation/modify",
                                          {"fid": r_uid, "act": "5", "re_src": "11", "csrf": csrf})
                                blacklisted.add(r_uid)
                        else:
                            failed += 1
                        time.sleep(0.3)
                    else:
                        _ask_delete(driver, aid, rpid, r_uid, uname, text, csrf, blacklisted, "", event)

                if reply.get("rcount", 0) > 0:
                    for sub in _fetch_sub_replies(driver, aid, rpid):
                        s_rpid  = str(sub.get("rpid", ""))
                        s_text  = (sub.get("content") or {}).get("message", "")
                        s_uid   = str((sub.get("member") or {}).get("mid", ""))
                        s_uname = (sub.get("member") or {}).get("uname", "")
                        if s_uid == uid:
                            continue
                        if _is_spam_selenium(s_text):
                            if auto:
                                r = _api_post(driver, "https://api.bilibili.com/x/v2/reply/del",
                                              {"oid": aid, "type": "1", "rpid": s_rpid, "csrf": csrf})
                                if r and r.get("code") == 0:
                                    deleted += 1
                                    if s_uid and s_uid not in blacklisted:
                                        _api_post(driver, "https://api.bilibili.com/x/relation/modify",
                                                  {"fid": s_uid, "act": "5", "re_src": "11", "csrf": csrf})
                                        blacklisted.add(s_uid)
                                else:
                                    failed += 1
                                time.sleep(0.3)
                            else:
                                _ask_delete(driver, aid, s_rpid, s_uid, s_uname,
                                            s_text, csrf, blacklisted, "（楼中楼）", event)

            page_info = inner.get("page") or {}
            total = page_info.get("count", 0)
            if pn * 20 >= total:
                break
            pn += 1
            time.sleep(0.5)

    if auto:
        tg.send(f"✅ 自动清理完成\n🗑️ 已删除：{deleted} 条\n❌ 失败：{failed} 条")
    else:
        tg.send(f"✅ 扫描完成，共处理 {deleted + skipped} 条垃圾评论")

# ── 对外命令入口 ──────────────────────────────────────────────────────────────

def run_clean():
    """逐条确认模式（/clean_comments）"""
    iq.set_interactive(True)
    tg.send("🚀 开始扫描垃圾评论（逐条确认）...")
    driver = _make_driver()
    try:
        driver.get("https://www.bilibili.com")
        time.sleep(3)
        uid = _get_uid(driver)
        _scan_and_delete(driver, uid, auto=False)
    finally:
        driver.quit()
        iq.set_interactive(False)

def run_auto_clean():
    """自动删除模式（/auto_clean）"""
    tg.send("🤖 开始自动清理垃圾评论...")
    driver = _make_driver()
    try:
        driver.get("https://www.bilibili.com")
        time.sleep(3)
        uid = _get_uid(driver)
        _scan_and_delete(driver, uid, auto=True)
    finally:
        driver.quit()
