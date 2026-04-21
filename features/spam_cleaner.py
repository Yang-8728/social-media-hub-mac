"""
B站垃圾评论清理 feature。
业务逻辑全在这里，不直接发 TG 消息，通过 interaction_queue 与用户交互。
"""
import os, re, time, threading
from core import tg_client as tg
from core import interaction_queue as iq

ACCOUNT_NAME = "ai_vanvan"
MAX_VIDEOS   = 3

SPAM_KEYWORDS = [
    "原片出处", "原片在", "完整版在", "高清原版", "完整资源",
    "我动态有", "动态里有", "动态已分享", "看看我动态", "看我动态",
    "主页有", "点主页", "进主页", "看我主页", "点我头像",
    "关注有福利", "关注我有", "关注拿",
    "看完别打", "看完你别打", "忍住", "胆小勿入", "不敢看", "不敢点",
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
]

URL_RE = re.compile(r'https?://\S+|b23\.tv/\S*|BV[a-zA-Z0-9]{10}', re.IGNORECASE)


# ── Chrome driver ──────────────────────────────────────────────────────────────

def make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    profile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tools", "profiles", f"chrome_profile_{ACCOUNT_NAME}"
    )
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


# ── B站 API ────────────────────────────────────────────────────────────────────

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


# ── 垃圾检测 ──────────────────────────────────────────────────────────────────

def _is_spam(text):
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return f"关键词: {kw}"
    if URL_RE.search(text):
        return "含链接"
    return None


# ── 交互：通过队列询问用户 ─────────────────────────────────────────────────────

def _ask_delete(driver, aid, rpid, uid, uname, text, csrf, blacklisted, label, event):
    """把询问消息推入队列，等用户回复后执行删除或跳过"""
    reason  = _is_spam(text)
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
    event.wait()  # 等回调执行完再处理下一条
    event.clear()


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def _scan_and_delete(driver, uid, auto=False):
    """扫描所有视频评论，auto=True 时自动删除，False 时逐条询问"""
    csrf = _get_csrf(driver)
    if not csrf or not uid:
        tg.send("❌ 未检测到登录状态")
        return

    videos = _get_videos(driver, uid)
    print(f"[spam_cleaner] 找到 {len(videos)} 个视频: {[v[0] for v in videos[:5]]}", flush=True)
    tg.send(f"📋 共找到 {len(videos)} 个视频，开始{'自动' if auto else ''}扫描...")

    # 回到主站，确保 API fetch 有正确的 Cookie 上下文
    driver.get("https://www.bilibili.com")
    time.sleep(2)
    csrf = _get_csrf(driver)  # 重新获取 csrf

    deleted = skipped = failed = 0
    event = threading.Event()

    for bvid, title in videos:
        # 导航到视频页，确保 API 请求有正确上下文
        driver.get(f"https://www.bilibili.com/video/{bvid}")
        time.sleep(2)
        csrf = _get_csrf(driver)

        aid = _bv_to_aid(driver, bvid)
        if not aid:
            print(f"[spam_cleaner] {bvid} aid 获取失败，跳过", flush=True)
            continue

        blacklisted = set()
        pn = 1

        while True:
            data    = _api_get(driver, f"https://api.bilibili.com/x/v2/reply?oid={aid}&type=1&pn={pn}&ps=20&sort=0")
            inner   = (data.get("data") or {})
            replies = inner.get("replies") or []
            print(f"[spam_cleaner] {bvid} pn={pn} replies={len(replies)} code={data.get('code')}", flush=True)
            if not replies:
                break

            for reply in replies:
                rpid  = str(reply.get("rpid", ""))
                text  = (reply.get("content") or {}).get("message", "")
                r_uid = str((reply.get("member") or {}).get("mid", ""))
                uname = (reply.get("member") or {}).get("uname", "")

                is_own = (r_uid == uid)
                if not is_own and _is_spam(text):
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
                        if _is_spam(s_text):
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


def run():
    """逐条确认模式"""
    iq.set_interactive(True)
    tg.send("🚀 开始扫描垃圾评论（逐条确认）...")
    driver = make_driver()
    try:
        driver.get("https://www.bilibili.com")
        time.sleep(3)
        uid = _get_uid(driver)
        _scan_and_delete(driver, uid, auto=False)
    finally:
        driver.quit()
        iq.set_interactive(False)


def run_auto():
    """自动删除模式"""
    tg.send("🤖 开始自动清理垃圾评论...")
    driver = make_driver()
    try:
        driver.get("https://www.bilibili.com")
        time.sleep(3)
        uid = _get_uid(driver)
        _scan_and_delete(driver, uid, auto=True)
    finally:
        driver.quit()
