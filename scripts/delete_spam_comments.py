"""
B站垃圾评论批量删除工具
用法:
  python3 delete_spam_comments.py           # 预览模式（不真实删除）
  python3 delete_spam_comments.py --delete  # 真实删除
"""
import os, sys, time, json, re, requests

ACCOUNT_NAME = "ai_vanvan"

# ── Telegram ───────────────────────────────────────────────────────────────────
TG_TOKEN   = "8783329976:AAHtpcx-FXEARHNHAE859MeNhE7f97SoTPY"
TG_CHAT_ID = "6930861685"
TG_BASE    = f"https://api.telegram.org/bot{TG_TOKEN}"
_tg_offset = None  # 全局 update offset

def tg_send(text):
    try:
        requests.post(f"{TG_BASE}/sendMessage", json={
            "chat_id": TG_CHAT_ID, "text": text
        }, timeout=10)
    except Exception as e:
        print(f"[TG] 发送失败: {e}")

RESPONSE_FILE = "/tmp/spam_response"

def tg_ask(text):
    """发送消息到 TG，等待 bot.py 写入回复文件，返回 True/False"""
    # 清掉上一次的回复
    if os.path.exists(RESPONSE_FILE):
        os.remove(RESPONSE_FILE)

    tg_send(text)

    # 轮询临时文件，bot.py 收到回复后会写入
    while True:
        if os.path.exists(RESPONSE_FILE):
            with open(RESPONSE_FILE) as f:
                ans = f.read().strip().lower()
            os.remove(RESPONSE_FILE)
            if ans in ("1", "y"):
                tg_send("✅ 已确认，执行删除")
                return True
            else:
                tg_send("⏭ 已跳过")
                return False
        time.sleep(0.5)
MAX_VIDEOS = 30  # 只扫最近N个视频

SPAM_KEYWORDS = [
    # 引流话术 — 指向动态/主页
    "原片出处", "原片在", "完整版在", "高清原版", "完整资源",
    "我动态有", "动态里有", "动态已分享", "看看我动态", "看我动态",
    "主页有", "点主页", "进主页", "看我主页", "点我头像",
    "关注有福利", "关注我有", "关注拿",
    # 引流话术 — 诱导点击/观看
    "看完别打", "忍住", "胆小勿入", "不敢看", "不敢点",
    "你懂的", "懂的都懂", "不解释", "自己悟",
    "羡慕吗", "心动了吗", "眼熟吗",
    # 内容描述 — 暗示付费/成人内容
    "福利视频", "福利资源", "涩涩", "18+",
    "不删除", "限时分享", "今天删", "马上删", "即将删除",
    "免费领", "白嫖", "自取", "资源合集", "打包发",
    # 私信/联系引导
    "私信我", "发我私信", "私聊我", "私我",
    "加微信", "加vx", "加wx", "加V", "威信", "微♥信",
    "加好友", "加我好友",
    # 外链特征（bili2233域名单独列，其他链接统一用URL正则检测）
    "bili2233", "bilibili2", "b站福利",
    # 隐晦引流码（给半个码让人自行补全）
    "自补后", "自补前", "自己补",
    # 账号刷量特征（一句话多次出现的空洞互动）
    "动态已分享", "已转发", "已收藏求回关",
    # 常见色情引流句式
    "看完关注", "资源私发", "原视频私发",
]

# ── Chrome driver ──────────────────────────────────────────────────────────────

def make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    profile_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
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

# ── API helpers（全在浏览器内执行，自动携带 cookie）──────────────────────────

def api_get(driver, url):
    return driver.execute_async_script("""
        const [url, cb] = arguments;
        fetch(url, {credentials: 'include'})
            .then(r => r.json()).then(cb)
            .catch(e => cb({error: e.toString()}));
    """, url)

def api_post(driver, url, data):
    return driver.execute_async_script("""
        const [url, data, cb] = arguments;
        fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams(data).toString()
        }).then(r => r.json()).then(cb)
          .catch(e => cb({error: e.toString()}));
    """, url, data)

def get_csrf(driver):
    return driver.execute_script("""
        for (const c of document.cookie.split(';')) {
            const [k, v] = c.trim().split('=');
            if (k === 'bili_jct') return v;
        }
        return null;
    """)

# ── B站 API 调用 ───────────────────────────────────────────────────────────────

def get_my_uid(driver):
    r = api_get(driver, "https://api.bilibili.com/x/web-interface/nav")
    if r and r.get("code") == 0:
        return str(r["data"]["mid"])
    return None

def get_recent_videos(driver, uid, limit=30):
    """从空间页面 DOM 抓视频列表，返回 [(bvid, title), ...]"""
    print("🌐 打开个人空间页...")
    driver.get(f"https://space.bilibili.com/{uid}/video")
    time.sleep(5)
    videos = driver.execute_script("""
        const links = document.querySelectorAll('a[href*="/video/BV"]');
        const seen = new Set();
        const result = [];
        for (const a of links) {
            const m = a.href.match(/\\/video\\/(BV\\w+)/);
            if (!m) continue;
            if (seen.has(m[1])) continue;
            seen.add(m[1]);
            result.push({bvid: m[1], title: a.title || a.textContent.trim()});
        }
        return result;
    """)
    return [(v["bvid"], v["title"]) for v in (videos or [])[:limit]]

def bv_to_aid(driver, bvid):
    r = api_get(driver, f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    if r and r.get("code") == 0:
        return str(r["data"]["aid"])
    return None

def get_comments_page(driver, oid, cursor=0):
    """懒加载模式，按时间倒序（最新在前）"""
    url = f"https://api.bilibili.com/x/v2/reply/main?oid={oid}&type=1&mode=2&next={cursor}&ps=20"
    return api_get(driver, url)

def delete_comment(driver, oid, rpid, csrf):
    return api_post(driver, "https://api.bilibili.com/x/v2/reply/del", {
        "oid": oid, "type": "1", "rpid": rpid, "csrf": csrf
    })

def blacklist_user(driver, uid, csrf):
    return api_post(driver, "https://api.bilibili.com/x/relation/modify", {
        "fid": uid, "act": "5", "re_src": "11", "csrf": csrf
    })

# ── 垃圾检测 ──────────────────────────────────────────────────────────────────

URL_RE = re.compile(r'https?://\S+|b23\.tv/\S*', re.IGNORECASE)

def is_spam(text):
    for kw in SPAM_KEYWORDS:
        if kw in text:
            return f"关键词: {kw}"
    if URL_RE.search(text):
        return "含链接"
    return None

# ── 处理单个视频 ──────────────────────────────────────────────────────────────

def ask_delete(uname, text, reason, label=""):
    """发现垃圾评论，通过 TG 询问是否删除，返回 True/False"""
    preview = text[:80].replace("\n", " ")
    print(f"\n  ⚠️  发现垃圾评论 {label}")
    print(f"     👤 {uname}  原因: {reason}")
    print(f"     💬 {preview}")
    msg = (
        f"⚠️ 发现垃圾评论 {label}\n"
        f"👤 {uname}\n"
        f"🏷️ 原因: {reason}\n"
        f"💬 {preview}\n\n"
        f"删除？回复 1/y 删除，0/n 跳过"
    )
    return tg_ask(msg)


def process_reply(driver, aid, rpid, uid, uname, text, csrf, blacklisted, label=""):
    """检测 → 询问 → 删除 → 拉黑，返回是否删除"""
    reason = is_spam(text)
    if not reason:
        return False

    if not ask_delete(uname, text, reason, label):
        return False

    r = delete_comment(driver, aid, rpid, csrf)
    if r and r.get("code") == 0:
        print(f"     ✅ 已删除")
        if uid and uid not in blacklisted:
            blacklist_user(driver, uid, csrf)
            blacklisted.add(uid)
            print(f"     🚫 已拉黑 UID {uid}")
    else:
        print(f"     ❌ 删除失败: {r}")
        return False
    time.sleep(0.4)
    return True


def fetch_sub_replies(driver, aid, rpid):
    """获取完整楼中楼列表"""
    subs = []
    pn = 1
    while True:
        url = f"https://api.bilibili.com/x/v2/reply/reply?oid={aid}&type=1&root={rpid}&ps=20&pn={pn}"
        data = api_get(driver, url)
        page_replies = ((data.get("data") or {}).get("replies")) or []
        if not page_replies:
            break
        subs.extend(page_replies)
        cursor = (data.get("data") or {}).get("cursor") or {}
        if cursor.get("is_end", True):
            break
        pn += 1
        time.sleep(0.3)
    return subs


def process_video(driver, bvid, title, csrf, my_uid):
    aid = bv_to_aid(driver, bvid)
    if not aid:
        print(f"  ⚠️  无法获取 AID，跳过")
        return 0

    deleted = 0
    blacklisted = set()
    cursor = 0
    page = 1

    while True:
        data = get_comments_page(driver, aid, cursor)
        if not data or data.get("code") != 0:
            print(f"  ⚠️  获取评论失败: {data}")
            break

        replies = (data.get("data") or {}).get("replies") or []
        if not replies:
            break

        print(f"  第{page}页 {len(replies)}条", flush=True)

        for reply in replies:
            rpid  = str(reply.get("rpid", ""))
            text  = (reply.get("content") or {}).get("message", "")
            uid   = str((reply.get("member") or {}).get("mid", ""))
            uname = (reply.get("member") or {}).get("uname", "")

            if uid == my_uid:
                continue

            if process_reply(driver, aid, rpid, uid, uname, text, csrf, blacklisted):
                deleted += 1

            # 完整楼中楼
            rcount = reply.get("rcount", 0)
            if rcount > 0:
                for sub in fetch_sub_replies(driver, aid, rpid):
                    sub_rpid  = str(sub.get("rpid", ""))
                    sub_text  = (sub.get("content") or {}).get("message", "")
                    sub_uid   = str((sub.get("member") or {}).get("mid", ""))
                    sub_uname = (sub.get("member") or {}).get("uname", "")
                    if sub_uid == my_uid:
                        continue
                    if process_reply(driver, aid, sub_rpid, sub_uid, sub_uname,
                                     sub_text, csrf, blacklisted, "（楼中楼）"):
                        deleted += 1

        cursor_info = (data.get("data") or {}).get("cursor") or {}
        if cursor_info.get("is_end", True):
            break
        cursor = cursor_info.get("next", 0)
        page += 1
        time.sleep(0.8)

    return deleted

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"B站垃圾评论清理工具  |  交互模式")
    print(f"{'='*50}\n")

    print("🚀 启动浏览器...")
    driver = make_driver()

    try:
        print("🌐 打开B站...")
        driver.get("https://www.bilibili.com")
        time.sleep(3)

        csrf = get_csrf(driver)
        if not csrf:
            print("❌ 未检测到登录状态，请先在浏览器中登录B站")
            return

        uid = get_my_uid(driver)
        if not uid:
            print("❌ 无法获取 UID")
            return

        print(f"✅ 已登录  UID: {uid}\n")

        print(f"📋 获取最近 {MAX_VIDEOS} 个视频...")
        videos = get_recent_videos(driver, uid, MAX_VIDEOS)
        print(f"  共找到 {len(videos)} 个视频\n")

        total = 0
        for i, (bvid, title) in enumerate(videos, 1):
            short_title = title[:30] + ("..." if len(title) > 30 else "")
            print(f"\n[{i}/{len(videos)}] {bvid}  {short_title}")
            n = process_video(driver, bvid, title, csrf, uid)
            total += n
            if n:
                print(f"  → 删除 {n} 条垃圾评论")
            time.sleep(1)

        print(f"\n{'='*50}")
        print(f"✅ 完成！共删除 {total} 条垃圾评论")
        print(f"{'='*50}\n")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
