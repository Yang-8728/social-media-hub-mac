"""
捞取最新一期视频的全部评论，打印出来供检查
用法: python3 fetch_latest_comments.py
"""
import os, sys, time

ACCOUNT_NAME = "ai_vanvan"

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

def api_get(driver, url):
    return driver.execute_async_script("""
        const [url, cb] = arguments;
        fetch(url, {credentials: 'include'})
            .then(r => r.json()).then(cb)
            .catch(e => cb({error: e.toString()}));
    """, url)

def main():
    driver = make_driver()
    try:
        import traceback
        print("🌐 打开创作中心...", flush=True)
        driver.get("https://member.bilibili.com/platform/home")
        time.sleep(4)

        nav = api_get(driver, "https://api.bilibili.com/x/web-interface/nav")
        if not nav or not (nav.get("data") or {}).get("isLogin"):
            print("⚠️  未登录，请在浏览器里扫码登录B站，脚本自动等待...", flush=True)
            while True:
                time.sleep(3)
                nav = api_get(driver, "https://api.bilibili.com/x/web-interface/nav")
                if nav and (nav.get("data") or {}).get("isLogin"):
                    print("✅ 登录成功！", flush=True)
                    break
                print("   等待登录中...", flush=True)
        uid = str(nav["data"]["mid"])
        print(f"✅ UID: {uid}")

        # 获取最新一期视频
        print(f"🌐 打开个人空间...", flush=True)
        driver.get(f"https://space.bilibili.com/{uid}/video")
        time.sleep(6)

        # 从页面 DOM 直接抓第一个视频的 bvid 和标题
        result = driver.execute_script("""
            const cards = document.querySelectorAll('.bili-video-card__info--tit, [href*="/video/BV"]');
            const links = document.querySelectorAll('a[href*="/video/BV"]');
            if (!links.length) return null;
            const href = links[0].getAttribute('href');
            const bvid = href.match(/BV\\w+/)?.[0];
            const title = links[0].getAttribute('title') || links[0].textContent.trim();
            return {bvid, title};
        """)
        print(f"  DOM抓取结果: {result}", flush=True)
        if not result or not result.get("bvid"):
            print("❌ 找不到视频"); return

        bvid  = result["bvid"]
        title = result["title"]
        print(f"🎬 最新视频: {bvid} 《{title}》\n")

        # BV → AID
        view = api_get(driver, f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
        aid  = str(view["data"]["aid"])

        # 捞全部评论
        cursor = 0
        page   = 1
        total  = 0

        while True:
            url  = f"https://api.bilibili.com/x/v2/reply/main?oid={aid}&type=1&mode=2&next={cursor}&ps=20"
            data = api_get(driver, url)

            if not data or data.get("code") != 0:
                print(f"⚠️ 获取失败: {data}"); break

            # 第一页先处理置顶评论
            if cursor == 0:
                for r in ((data.get("data") or {}).get("top_replies") or []):
                    total += 1
                    uname  = (r.get("member") or {}).get("uname", "?")
                    mid    = (r.get("member") or {}).get("mid", "?")
                    text   = (r.get("content") or {}).get("message", "")
                    likes  = r.get("like", 0)
                    rpid   = r.get("rpid", "")
                    display = text.replace("\n", " ")
                    if len(display) > 80:
                        display = display[:80] + "..."
                    print(f"[置顶] 👤 {uname} (uid:{mid})  ❤️{likes}  rpid:{rpid}")
                    print(f"      {display}")
                    rcount = r.get("rcount", 0)
                    if rcount > 0:
                        sub_pn = 1
                        while True:
                            sub_url  = f"https://api.bilibili.com/x/v2/reply/reply?oid={aid}&type=1&root={rpid}&ps=20&pn={sub_pn}"
                            sub_data = api_get(driver, sub_url)
                            sub_replies = ((sub_data.get("data") or {}).get("replies")) or []
                            if not sub_replies:
                                break
                            for sub in sub_replies:
                                sub_uname = (sub.get("member") or {}).get("uname", "?")
                                sub_mid   = (sub.get("member") or {}).get("mid", "?")
                                sub_text  = (sub.get("content") or {}).get("message", "").replace("\n", " ")
                                sub_rpid  = sub.get("rpid", "")
                                if len(sub_text) > 70:
                                    sub_text = sub_text[:70] + "..."
                                print(f"       ↳ {sub_uname} (uid:{sub_mid})  rpid:{sub_rpid}")
                                print(f"         {sub_text}")
                            sub_cursor = (sub_data.get("data") or {}).get("cursor") or {}
                            if sub_cursor.get("is_end", True):
                                break
                            sub_pn += 1
                            time.sleep(0.3)

            replies = (data.get("data") or {}).get("replies") or []
            if not replies:
                break

            for r in replies:
                total += 1
                uname   = (r.get("member") or {}).get("uname", "?")
                mid     = (r.get("member") or {}).get("mid", "?")
                text    = (r.get("content") or {}).get("message", "")
                likes   = r.get("like", 0)
                ctime   = r.get("ctime", 0)
                rpid    = r.get("rpid", "")

                # 截断长文本方便阅读
                display = text.replace("\n", " ")
                if len(display) > 80:
                    display = display[:80] + "..."

                print(f"[{total:03d}] 👤 {uname} (uid:{mid})  ❤️{likes}  rpid:{rpid}")
                print(f"      {display}")

                # 楼中楼：调子评论接口拿完整列表
                rcount = r.get("rcount", 0)
                if rcount > 0:
                    sub_pn = 1
                    while True:
                        sub_url  = f"https://api.bilibili.com/x/v2/reply/reply?oid={aid}&type=1&root={rpid}&ps=20&pn={sub_pn}"
                        sub_data = api_get(driver, sub_url)
                        sub_replies = ((sub_data.get("data") or {}).get("replies")) or []
                        if not sub_replies:
                            break
                        for sub in sub_replies:
                            sub_uname = (sub.get("member") or {}).get("uname", "?")
                            sub_mid   = (sub.get("member") or {}).get("mid", "?")
                            sub_text  = (sub.get("content") or {}).get("message", "").replace("\n", " ")
                            sub_rpid  = sub.get("rpid", "")
                            if len(sub_text) > 70:
                                sub_text = sub_text[:70] + "..."
                            print(f"       ↳ {sub_uname} (uid:{sub_mid})  rpid:{sub_rpid}")
                            print(f"         {sub_text}")
                        sub_cursor = (sub_data.get("data") or {}).get("cursor") or {}
                        if sub_cursor.get("is_end", True):
                            break
                        sub_pn += 1
                        time.sleep(0.3)

            cursor_info = (data.get("data") or {}).get("cursor") or {}
            if cursor_info.get("is_end", True):
                break
            cursor = cursor_info.get("next", 0)
            page  += 1
            time.sleep(0.5)

        print(f"\n共 {total} 条评论")

    except Exception as e:
        print(f"\n❌ 出错了: {e}")
        traceback.print_exc()
        time.sleep(5)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
