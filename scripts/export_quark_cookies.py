"""
导出夸克网盘 Cookie 并保存到 config/quark.json。
首次运行时需要在浏览器里点击确认登录，之后登录状态会保留在 Chrome profile 里，
无需再次登录。

用法：python3 export_quark_cookies.py
"""
import json, os, time
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

PROJECT_DIR   = os.path.dirname(os.path.abspath(__file__))
QUARK_CONFIG  = os.path.join(PROJECT_DIR, "config", "quark.json")
QUARK_PROFILE = os.path.join(PROJECT_DIR, "tools", "profiles", "chrome_profile_quark")


def export_quark_cookies():
    options = Options()
    options.add_argument(f"--user-data-dir={QUARK_PROFILE}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    print("🚀 启动 Chrome（夸克专用 profile）...")
    driver = webdriver.Chrome(service=Service(), options=options)

    try:
        driver.get("https://pan.quark.cn")
        time.sleep(4)

        # 如果出现确认登录按钮就点
        btns = driver.find_elements("xpath", '//div[text()="确认登录"]')
        if btns:
            print("📱 检测到确认登录弹窗，自动点击...")
            driver.execute_script("arguments[0].click();", btns[0])
            # 等待跳转
            for _ in range(20):
                time.sleep(1)
                if "list" in driver.current_url:
                    break

        if "list" not in driver.current_url:
            print("⚠️  未检测到登录状态，请在打开的浏览器中完成登录后按 Enter...")
            input()
            time.sleep(2)

        # 获取 pan.quark.cn 域的 cookie
        cookies = driver.get_cookies()
        quark_cookies = {
            c["name"]: unquote(c["value"])
            for c in cookies
            if "quark" in c.get("domain", "")
        }
        if not quark_cookies:
            quark_cookies = {c["name"]: unquote(c["value"]) for c in cookies}

        cookie_str = "; ".join(f"{k}={v}" for k, v in quark_cookies.items())

        config = {}
        if os.path.exists(QUARK_CONFIG):
            with open(QUARK_CONFIG) as f:
                config = json.load(f)
        config["cookie"] = cookie_str

        with open(QUARK_CONFIG, "w") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        print(f"✅ 已保存 {len(quark_cookies)} 个 Cookie 到 config/quark.json")
        auth = {"__pus", "__puus"} & set(quark_cookies.keys())
        if auth:
            print(f"   ✅ 包含 auth cookie: {auth}")
        else:
            print("   ⚠️  未发现 __pus/__puus，可能未完全登录")

    finally:
        driver.quit()


if __name__ == "__main__":
    export_quark_cookies()
