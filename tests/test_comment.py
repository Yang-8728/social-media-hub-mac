"""
测试：在已发布视频页找评论框、发评论、置顶
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ACCOUNT_NAME = "ai_vanvan"
VIDEO_URL = "https://www.bilibili.com/video/BV1jzQ4BAEWd/"

CHAPTER_LIST = """00:00  cartenknox
00:10  yzelle.lim
00:25  soul_form8
00:33  cartenknox
00:45  kirveylegor
00:58  rileymae
01:18  _leonela_quintana
01:33  danataranova
01:46  lio.yuanjie
01:53  hirixie
02:08  alexisaevans
02:17  _zxnai.m_
02:27  make_your_day_2026
02:34  alexis_talks19"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# 启动浏览器
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

driver = webdriver.Chrome(options=chrome_options)
print(f"✅ Chrome启动，打开视频页: {VIDEO_URL}")
driver.get(VIDEO_URL)
time.sleep(5)

# 滚动到评论区（分步滚动触发懒加载）
print("📜 滚动到评论区...")
for scroll_pos in [400, 800, 1200, 1800, 2500]:
    driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
    time.sleep(0.8)
time.sleep(3)

# 递归找 textarea 或 contenteditable（含嵌套 shadow DOM）
def find_input_in_shadow(root_js):
    return driver.execute_script(f"""
        function findDeep(root) {{
            var ta = root.querySelector('textarea');
            if (ta && ta.getBoundingClientRect().width > 0) return ta;
            var ce = root.querySelector('[contenteditable="true"]');
            if (ce && ce.getBoundingClientRect().width > 0) return ce;
            var all = root.querySelectorAll('*');
            for (var el of all) {{
                if (el.shadowRoot) {{
                    var found = findDeep(el.shadowRoot);
                    if (found) return found;
                }}
            }}
            return null;
        }}
        return findDeep({root_js});
    """)

# 找发送按钮（含 shadow DOM）
def find_send_btn():
    return driver.execute_script("""
        function findBtn(root) {
            var btns = root.querySelectorAll('button');
            for (var btn of btns) {
                var txt = btn.textContent.trim();
                if (txt === '发布' || txt === '发送') return btn;
            }
            var all = root.querySelectorAll('*');
            for (var el of all) {
                if (el.shadowRoot) {
                    var found = findBtn(el.shadowRoot);
                    if (found) return found;
                }
            }
            return null;
        }
        return findBtn(document);
    """)

# 找评论框
comment_box = find_input_in_shadow("document")
if not comment_box:
    print("❌ 找不到评论框，退出")
    driver.quit()
    sys.exit(1)

tag = driver.execute_script("return arguments[0].tagName", comment_box)
print(f"✅ 找到评论框: tag={tag}")

# 输入评论
print("\n💬 开始输入评论...")
driver.execute_script("arguments[0].scrollIntoView({block:'center'});", comment_box)
comment_box.click()
time.sleep(0.5)

lines = CHAPTER_LIST.split("\n")
for i, line in enumerate(lines):
    comment_box.send_keys(line)
    if i < len(lines) - 1:
        comment_box.send_keys(Keys.SHIFT + Keys.RETURN)

print("✅ 文字已输入，等3秒后发送...")
time.sleep(3)

# 找发送按钮
send_btn = find_send_btn()
if send_btn:
    print(f"✅ 找到发送按钮: '{driver.execute_script('return arguments[0].textContent.trim()', send_btn)}'")
    driver.execute_script("arguments[0].click()", send_btn)
    print("✅ 评论已发送")
    time.sleep(3)
else:
    print("❌ 找不到发送按钮，退出")
    driver.quit()
    sys.exit(1)

# 找置顶：用 ActionChains hover 评论，让「...」出现，再点置顶
print("\n📌 查找置顶选项...")
time.sleep(3)

def find_renderer():
    return driver.execute_script("""
        function findRenderer(root) {
            var el = root.querySelector('bili-comment-renderer');
            if (el) return el;
            var all = root.querySelectorAll('*');
            for (var item of all) {
                if (item.shadowRoot) {
                    var found = findRenderer(item.shadowRoot);
                    if (found) return found;
                }
            }
            return null;
        }
        return findRenderer(document);
    """)

renderer = find_renderer()
if not renderer:
    print("❌ 找不到 BILI-COMMENT-RENDERER")
else:
    print(f"✅ 找到评论元素，hover 内容区域...")
    # 找 renderer shadow root 里最大的内容 DIV（非 avatar 区域）
    content_div = driver.execute_script("""
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
        if (!renderer || !renderer.shadowRoot) return null;
        // 找最大的内容 div（width > 800，不是 renderer 本身）
        var best = null, bestArea = 0;
        renderer.shadowRoot.querySelectorAll('div').forEach(function(el) {
            var rect = el.getBoundingClientRect();
            var area = rect.width * rect.height;
            if (rect.width > 700 && rect.height > 100 && area < 897 * 444 && area > bestArea) {
                bestArea = area; best = el;
            }
        });
        return best || renderer;
    """)
    target = content_div if content_div else renderer
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    time.sleep(0.5)
    driver.execute_script("window.scrollBy(0, 150);")
    time.sleep(0.5)
    ActionChains(driver).move_to_element(target).perform()
    time.sleep(1.5)

    # hover 后找「...」按钮 —— 只在 BILI-COMMENT-RENDERER shadow DOM 内找
    print("🔍 查找「...」按钮（仅在评论 shadow DOM 内）...")
    more_result = driver.execute_script("""
        function findRenderer(root) {
            var el = root.querySelector('bili-comment-renderer');
            if (el) return el;
            var all = root.querySelectorAll('*');
            for (var item of all) {
                if (item.shadowRoot) { var f = findRenderer(item.shadowRoot); if (f) return f; }
            }
            return null;
        }
        function findMoreInShadow(root, depth) {
            if (depth > 5) return null;
            var all = root.querySelectorAll('*');
            for (var el of all) {
                var tag = (el.tagName || '').toLowerCase();
                var txt = el.textContent.trim();
                var rect = el.getBoundingClientRect();
                // 精确匹配：bili-comment-more 自定义元素
                if (tag === 'bili-comment-more') return el;
                // 纯「...」文字且很小
                if ((txt === '...' || txt === '···' || txt === '•••') && rect.width < 50 && rect.width > 0) return el;
                if (el.shadowRoot) {
                    var found = findMoreInShadow(el.shadowRoot, depth + 1);
                    if (found) return found;
                }
            }
            return null;
        }
        // 打印整个 renderer shadow DOM，用于调试
        function dumpAll(root, depth) {
            if (depth > 3) return [];
            var results = [];
            root.querySelectorAll('*').forEach(function(el) {
                var rect = el.getBoundingClientRect();
                var cls = typeof el.className === 'string' ? el.className : '';
                results.push({
                    tag: el.tagName, depth: depth,
                    cls: cls.substring(0, 50),
                    txt: el.textContent.trim().substring(0, 20),
                    w: Math.round(rect.width), h: Math.round(rect.height),
                    x: Math.round(rect.x), y: Math.round(rect.y),
                    hasShadow: !!el.shadowRoot
                });
                if (el.shadowRoot) {
                    dumpAll(el.shadowRoot, depth+1).forEach(function(r){ results.push(r); });
                }
            });
            return results;
        }
        var renderer = findRenderer(document);
        if (!renderer || !renderer.shadowRoot) return {btn: null, dump: []};
        return {btn: findMoreInShadow(renderer.shadowRoot, 0), dump: dumpAll(renderer.shadowRoot, 0)};
    """)

    more_btn = more_result.get('btn') if more_result else None
    dump_items = more_result.get('dump', []) if more_result else []

    print(f"  评论 shadow DOM 小型可见元素:")
    for item in dump_items:
        if item['w'] > 0 and item['h'] > 0 and item['w'] < 150 and item['h'] < 50:
            indent = "  " * item['depth']
            shadow = "[S]" if item['hasShadow'] else ""
            print(f"{indent}{item['tag']}{shadow} {item['w']}x{item['h']} @({item['x']},{item['y']}) cls='{item['cls']}' txt='{item['txt']}'")

    if more_btn:
        tag = driver.execute_script("return arguments[0].tagName", more_btn)
        txt = driver.execute_script("return arguments[0].textContent.trim()", more_btn)
        print(f"✅ 找到「...」按钮: tag={tag} txt='{txt}'")
        ActionChains(driver).move_to_element(more_btn).click().perform()
        time.sleep(1.5)
    else:
        # 找 renderer shadow DOM 里含 BILI-ICON 的小按钮（图标按钮，无文字）
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
            function findAllSmallClickable(root, depth, results) {
                if (depth > 5) return;
                root.querySelectorAll('*').forEach(function(el) {
                    var tag = (el.tagName || '').toLowerCase();
                    var rect = el.getBoundingClientRect();
                    var txt = el.textContent.trim();
                    // 小型无文字的 button 或 div/span（可能是图标容器）
                    if (rect.width > 0 && rect.width < 40 && rect.height > 0 && rect.height < 40 && txt === '') {
                        if (tag === 'button' || tag === 'div' || tag === 'span') {
                            results.push({el: el, x: rect.x, tag: tag});
                        }
                    }
                    if (el.shadowRoot) findAllSmallClickable(el.shadowRoot, depth + 1, results);
                });
            }
            var renderer = findRenderer(document);
            if (!renderer || !renderer.shadowRoot) return null;
            var items = [];
            findAllSmallClickable(renderer.shadowRoot, 0, items);
            if (!items.length) return null;
            // 取 x 坐标最大的元素（最右边 = 「...」三点菜单）
            items.sort(function(a, b) { return b.x - a.x; });
            return items[0].el;
        """)
        if more_btn:
            print(f"✅ 找到图标按钮（无文字小按钮）")
            # 用 W3C Actions 按精确坐标点击（绕开 shadow DOM 事件问题）
            rect = driver.execute_script("return arguments[0].getBoundingClientRect()", more_btn)
            cx = int(rect['x'] + rect['width'] / 2)
            cy = int(rect['y'] + rect['height'] / 2)
            print(f"  按钮坐标: ({cx}, {cy})")
            # 先 hover 到按钮位置
            ActionChains(driver).w3c_actions.pointer_action.move_to_location(cx, cy)
            ActionChains(driver).perform()
            time.sleep(0.5)
            # 再按坐标点击
            actions = ActionChains(driver)
            actions.w3c_actions.pointer_action.move_to_location(cx, cy)
            actions.w3c_actions.pointer_action.click()
            actions.perform()
            time.sleep(2)
            # 打印点击后页面上新增的可见菜单元素
            print("🔍 点击「...」后查找弹出菜单...")
            menu_items = driver.execute_script("""
                function findMenuItems(root) {
                    var results = [];
                    root.querySelectorAll('*').forEach(function(el) {
                        var rect = el.getBoundingClientRect();
                        var txt = el.textContent.trim();
                        var cls = typeof el.className === 'string' ? el.className : '';
                        // 找小型可见菜单项（文字不空，宽度合理）
                        if (rect.width > 0 && rect.height > 0 && rect.width < 200 && rect.height < 50 && txt.length < 20 && txt.length > 0) {
                            if (cls.includes('menu') || cls.includes('pop') || cls.includes('drop') ||
                                txt === '置顶' || txt === '删除' || txt === '举报' || txt === '复制' ||
                                txt.includes('置顶') || txt.includes('删除')) {
                                results.push({tag: el.tagName, txt: txt, cls: cls.substring(0,50),
                                              x: Math.round(rect.x), y: Math.round(rect.y)});
                            }
                        }
                        if (el.shadowRoot) {
                            findMenuItems(el.shadowRoot).forEach(function(r){ results.push(r); });
                        }
                    });
                    return results;
                }
                return findMenuItems(document);
            """)
            print(f"  弹出菜单项 ({len(menu_items)} 个):")
            for item in menu_items:
                print(f"  {item['tag']} @({item['x']},{item['y']}) txt='{item['txt']}' cls='{item['cls']}'")
        else:
            print("❌ 未找到「...」按钮")

# 找「置顶」选项（菜单弹出后）
time.sleep(2)
pin_btn = driver.execute_script("""
    // 找文字恰好是「设为置顶」或「置顶」的最小可见元素
    function findPin(root) {
        var best = null, bestArea = Infinity;
        function search(r) {
            r.querySelectorAll('*').forEach(function(el) {
                var txt = el.textContent.trim();
                if ((txt === '设为置顶' || txt === '置顶') && !txt.includes('取消')) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        var area = rect.width * rect.height;
                        if (area < bestArea) { bestArea = area; best = el; }
                    }
                }
                if (el.shadowRoot) search(el.shadowRoot);
            });
        }
        search(root);
        return best;
    }
    return findPin(document);
""")
if pin_btn:
    print("✅ 找到「置顶」，用坐标点击...")
    pin_rect = driver.execute_script("return arguments[0].getBoundingClientRect()", pin_btn)
    px = int(pin_rect['x'] + pin_rect['width'] / 2)
    py = int(pin_rect['y'] + pin_rect['height'] / 2)
    print(f"  置顶按钮坐标: ({px}, {py})")
    pin_actions = ActionChains(driver)
    pin_actions.w3c_actions.pointer_action.move_to_location(px, py)
    pin_actions.w3c_actions.pointer_action.click()
    pin_actions.perform()
    time.sleep(1)
    print("🎉 评论已置顶！")
    driver.quit()
    sys.exit(0)
else:
    # 打印所有弹出的小型菜单元素帮助调试
    print("❌ 找不到「置顶」，打印当前小型文字元素...")
    items = driver.execute_script("""
        function findSmall(root) {
            var results = [];
            root.querySelectorAll('*').forEach(function(el) {
                var rect = el.getBoundingClientRect();
                var txt = el.textContent.trim();
                if (rect.width > 0 && rect.height > 0 && rect.width < 200 && rect.height < 50 && txt.length > 0 && txt.length < 15) {
                    var cls = typeof el.className === 'string' ? el.className : '';
                    results.push({tag: el.tagName, txt: txt, x: Math.round(rect.x), y: Math.round(rect.y)});
                }
                if (el.shadowRoot) findSmall(el.shadowRoot).forEach(function(r){ results.push(r); });
            });
            return results;
        }
        return findSmall(document);
    """)
    for item in items:
        print(f"  {item['tag']} @({item['x']},{item['y']}) txt='{item['txt']}'")
    print("\n浏览器保持打开，Ctrl+C 退出")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        driver.quit()
