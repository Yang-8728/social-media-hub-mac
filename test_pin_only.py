"""
只做置顶：hover 评论 → 点「...」→ 点「设为置顶」
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ACCOUNT_NAME = "ai_vanvan"
VIDEO_URL = "https://www.bilibili.com/video/BV1jzQ4BAEWd/"

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

chrome_options = Options()
profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tools", "profiles", f"chrome_profile_{ACCOUNT_NAME}")
chrome_options.add_argument(f"--user-data-dir={profile_path}")
chrome_options.add_argument("--profile-directory=Default")
chrome_options.add_argument("--window-size=1400,900")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--no-first-run")
chrome_options.add_argument("--no-default-browser-check")
chrome_options.add_argument("--disable-sync")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

# 清理 singleton lock
for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
    lpath = os.path.join(profile_path, lock_file)
    if os.path.exists(lpath):
        os.remove(lpath)
        print(f"🧹 清理: {lock_file}")

driver = webdriver.Chrome(options=chrome_options)
print(f"✅ Chrome启动: {VIDEO_URL}")
driver.get(VIDEO_URL)
time.sleep(10)

# 分步滚动触发评论区懒加载
print("📜 滚动到评论区...")
for scroll_pos in [400, 800, 1200, 1800, 2500, 3000]:
    driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
    time.sleep(1)
time.sleep(5)

# 用 ActionChains 物理滚动到 bili-comments 元素（触发 intersection observer）
bili_comments = driver.execute_script("return document.querySelector('bili-comments')")
if bili_comments:
    print("🖱️  ActionChains 滚动到评论区...")
    ActionChains(driver).scroll_to_element(bili_comments).perform()
    time.sleep(3)

# 递归找 bili-text-button 并用坐标点击触发评论列表加载
print("🖱️  递归查找排序按钮并点击...")
btn_rect = driver.execute_script("""
    function findDeep(root, depth) {
        if (depth > 8) return null;
        var els = root.querySelectorAll('*');
        for (var el of els) {
            var tag = (el.tagName || '').toLowerCase();
            var txt = el.textContent.trim();
            if ((tag === 'bili-text-button' || tag === 'button') &&
                (txt === '最热' || txt === '热门' || txt === '最新')) {
                var rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    return {x: rect.x, y: rect.y, w: rect.width, h: rect.height, txt: txt, tag: tag};
                }
            }
            if (el.shadowRoot) {
                var found = findDeep(el.shadowRoot, depth + 1);
                if (found) return found;
            }
        }
        return null;
    }
    return findDeep(document, 0);
""")
print(f"  排序按钮: {btn_rect}")
if btn_rect:
    cx = int(btn_rect['x'] + btn_rect['w'] / 2)
    cy = int(btn_rect['y'] + btn_rect['h'] / 2)
    print(f"  W3C 点击排序按钮 @({cx},{cy})...")
    act = ActionChains(driver)
    act.w3c_actions.pointer_action.move_to_location(cx, cy)
    act.w3c_actions.pointer_action.click()
    act.perform()
    print("  ✅ 点击完成")
else:
    print("  ⚠️  找不到排序按钮，尝试 JS 直接调用 API 滚动...")
    driver.execute_script("window.scrollBy(0, 200);")
time.sleep(5)

# 检查渲染情况
renderer_count = driver.execute_script("""
    function count(root) {
        var n = root.querySelectorAll('bili-comment-renderer').length;
        root.querySelectorAll('*').forEach(function(el) {
            if (el.shadowRoot) n += count(el.shadowRoot);
        });
        return n;
    }
    return count(document);
""")
print(f"📌 bili-comment-renderer 数量: {renderer_count}")

if renderer_count == 0:
    print("⚠️  评论区还未加载，再等 10 秒...")
    time.sleep(10)
    renderer_count = driver.execute_script("""
        function count(root) {
            var n = root.querySelectorAll('bili-comment-renderer').length;
            root.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) n += count(el.shadowRoot);
            });
            return n;
        }
        return count(document);
    """)
    print(f"📌 重试后 bili-comment-renderer 数量: {renderer_count}")

if renderer_count == 0:
    print("❌ 评论区仍未加载，浏览器保持打开")
    try:
        while True: time.sleep(5)
    except KeyboardInterrupt:
        driver.quit()
    sys.exit(1)

# 找第一个 BILI-COMMENT-RENDERER
print("🖱️  hover 评论内容区域...")
target = driver.execute_script("""
    function findRenderer(root) {
        var el = root.querySelector('bili-comment-renderer');
        if (el) return el;
        var all = root.querySelectorAll('*');
        for (var item of all) {
            if (item.shadowRoot) { var f = findRenderer(item.shadowRoot); if (f) return f; }
        }
        return null;
    }
    var renderer = findRenderer(document);
    if (!renderer) return null;
    if (!renderer.shadowRoot) return renderer;
    var best = null, bestArea = 0;
    renderer.shadowRoot.querySelectorAll('div').forEach(function(el) {
        var rect = el.getBoundingClientRect();
        var area = rect.width * rect.height;
        if (rect.width > 700 && rect.height > 100 && area < 897*600 && area > bestArea) {
            bestArea = area; best = el;
        }
    });
    return best || renderer;
""")

if not target:
    print("❌ 找不到评论元素，浏览器保持打开")
    try:
        while True: time.sleep(5)
    except KeyboardInterrupt:
        driver.quit()
    sys.exit(1)

# 滚到视口中央，往上偏 150px 给下拉菜单留空间
driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
time.sleep(0.5)
driver.execute_script("window.scrollBy(0, 150);")
time.sleep(0.5)
ActionChains(driver).move_to_element(target).perform()
print("✅ hover 成功")
time.sleep(1.5)

# 找最右边的小型无文字元素（「...」按钮）
print("🔍 查找「...」按钮...")
more_btn = driver.execute_script("""
    function findRenderer(root) {
        var el = root.querySelector('bili-comment-renderer');
        if (el) return el;
        var all = root.querySelectorAll('*');
        for (var item of all) {
            if (item.shadowRoot) { var f = findRenderer(item.shadowRoot); if (f) return f; }
        }
        return null;
    }
    function findAllSmall(root, depth, results) {
        if (depth > 5) return;
        root.querySelectorAll('*').forEach(function(el) {
            var tag = (el.tagName || '').toLowerCase();
            var rect = el.getBoundingClientRect();
            var txt = el.textContent.trim();
            if (rect.width > 0 && rect.width < 40 && rect.height > 0 && rect.height < 40 && txt === '') {
                if (tag === 'button' || tag === 'div' || tag === 'span') {
                    results.push({el: el, x: rect.x});
                }
            }
            if (el.shadowRoot) findAllSmall(el.shadowRoot, depth + 1, results);
        });
    }
    var renderer = findRenderer(document);
    if (!renderer || !renderer.shadowRoot) return null;
    var items = [];
    findAllSmall(renderer.shadowRoot, 0, items);
    if (!items.length) return null;
    items.sort(function(a, b) { return b.x - a.x; });
    return items[0].el;
""")

if not more_btn:
    print("❌ 找不到「...」按钮，浏览器保持打开")
    try:
        while True: time.sleep(5)
    except KeyboardInterrupt:
        driver.quit()
    sys.exit(1)

rect = driver.execute_script("return arguments[0].getBoundingClientRect()", more_btn)
cx = int(rect['x'] + rect['width'] / 2)
cy = int(rect['y'] + rect['height'] / 2)
print(f"✅ 找到「...」按钮 @({cx},{cy})，W3C 点击...")

actions = ActionChains(driver)
actions.w3c_actions.pointer_action.move_to_location(cx, cy)
actions.w3c_actions.pointer_action.click()
actions.perform()
time.sleep(2)

# 精确找「设为置顶」（最小面积的含"置顶"可见元素）
print("🔍 查找「设为置顶」...")
pin_btn = driver.execute_script("""
    var best = null, bestArea = Infinity;
    function search(root) {
        root.querySelectorAll('*').forEach(function(el) {
            var txt = el.textContent.trim();
            if (txt === '设为置顶' || txt === '置顶') {
                var rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    var area = rect.width * rect.height;
                    if (area < bestArea) { bestArea = area; best = el; }
                }
            }
            if (el.shadowRoot) search(el.shadowRoot);
        });
    }
    search(document);
    return best;
""")

if not pin_btn:
    print("❌ 找不到「设为置顶」，浏览器保持打开")
    try:
        while True: time.sleep(5)
    except KeyboardInterrupt:
        driver.quit()
    sys.exit(1)

pin_rect = driver.execute_script("return arguments[0].getBoundingClientRect()", pin_btn)
px = int(pin_rect['x'] + pin_rect['width'] / 2)
py = int(pin_rect['y'] + pin_rect['height'] / 2)
print(f"✅ 找到「设为置顶」@({px},{py})，点击...")

try:
    pin_actions = ActionChains(driver)
    pin_actions.w3c_actions.pointer_action.move_to_location(px, py)
    pin_actions.w3c_actions.pointer_action.click()
    pin_actions.perform()
except Exception as e:
    print(f"  W3C 失败({e})，改用 JS click...")
    driver.execute_script("arguments[0].click()", pin_btn)

time.sleep(1)
print("🎉 置顶完成！")

print("\n浏览器保持打开，Ctrl+C 退出")
try:
    while True:
        time.sleep(5)
except KeyboardInterrupt:
    driver.quit()
