"""
用 Selenium 打开已登录的 Chrome Profile，导出 B站 Cookie 到 JSON。
运行一次即可，之后 bili_monitor 直接读文件。

用法: python3 export_bili_cookies.py
"""
import os, json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

ACCOUNT_NAME = "ai_vanvan"
PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "tools", "profiles", f"chrome_profile_{ACCOUNT_NAME}"
)
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      f"bili_cookies_{ACCOUNT_NAME}.json")

opts = Options()
opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
opts.add_argument("--profile-directory=Default")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")

print("🚀 启动 Chrome，读取 B站 Cookie...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

try:
    driver.get("https://www.bilibili.com")
    import time; time.sleep(3)

    cookies = driver.get_cookies()
    bili_cookies = {c["name"]: c["value"] for c in cookies if "bilibili" in c.get("domain", "")}

    needed = {"SESSDATA", "bili_jct", "DedeUserID"}
    missing = needed - bili_cookies.keys()
    if missing:
        print(f"⚠️  缺少 Cookie（可能未登录）: {missing}")
    else:
        print(f"✅ 找到所有必要 Cookie")

    with open(OUTPUT, "w") as f:
        json.dump(bili_cookies, f, indent=2)
    print(f"✅ 已保存到: {OUTPUT}（共 {len(bili_cookies)} 条）")
finally:
    driver.quit()
