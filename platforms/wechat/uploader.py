import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"

_JS_FIND_FILE_INPUT = """
    function findFileInput(root) {
        const inputs = root.querySelectorAll("input[type='file']");
        for (const inp of inputs) {
            if (inp.accept && inp.accept.includes("video")) return inp;
        }
        for (const el of root.querySelectorAll("*")) {
            if (el.shadowRoot) {
                const found = findFileInput(el.shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return findFileInput(document);
"""

_JS_FIND_DESC = """
    function findDesc(root) {
        for (const el of root.querySelectorAll("textarea")) {
            if (el.className && el.className.includes("textarea-body")) return el;
        }
        for (const el of root.querySelectorAll("*")) {
            if (el.shadowRoot) {
                const found = findDesc(el.shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return findDesc(document);
"""

_JS_FIND_SUBMIT = """
    function findSubmit(root) {
        for (const btn of root.querySelectorAll("button")) {
            const txt = btn.innerText.trim();
            if (txt === "发表" && !btn.className.includes("_disabled")) return btn;
        }
        for (const el of root.querySelectorAll("*")) {
            if (el.shadowRoot) {
                const found = findSubmit(el.shadowRoot);
                if (found) return found;
            }
        }
        return null;
    }
    return findSubmit(document);
"""


class WeChatUploader:

    def __init__(self, account_name: str = "wechat"):
        self.account_name = account_name
        self.driver = None
        self.wait = None
        self.profile_path = os.path.join(PROJECT_DIR, "tools", "profiles", f"chrome_profile_{account_name}")

    def setup_driver(self) -> bool:
        try:
            chrome_options = Options()
            os.makedirs(self.profile_path, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--profile-directory=Default")
            chrome_options.add_argument("--window-size=1400,900")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--remote-debugging-port=9224")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--log-level=3")

            service = Service()
            service.start_timeout = 60

            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 30)
            # 最小化到 Dock，不打扰前台（同步执行确保及时生效）
            import subprocess
            time.sleep(0.3)
            subprocess.run(
                ['osascript', '-e',
                 'tell application "Google Chrome"\n  set miniaturized of window 1 to true\nend tell'],
                capture_output=True, timeout=3
            )
            return True
        except Exception as e:
            print(f"❌ Chrome 启动失败: {e}")
            return False

    def upload(self, video_path: str, title: str) -> bool:
        try:
            if not self.setup_driver():
                return False
            self.driver.get(UPLOAD_URL)
            time.sleep(5)
            if not self._wait_for_login_if_needed():
                return False
            self._upload_file(video_path)
            self._set_description(title)
            if not self._submit():
                return False
            return self._wait_for_success()
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass

    def _wait_for_login_if_needed(self) -> bool:
        try:
            if "post/create" in self.driver.current_url:
                return True
            print("⚠️ 需要微信扫码登录")
            try:
                from bot import tg_client as tg
                tg.send("⚠️ 视频号需要扫码登录，请在 Mac 上打开 Chrome 完成微信扫码")
            except Exception:
                pass
            for _ in range(36):
                time.sleep(5)
                try:
                    url = self.driver.current_url
                    if "post/create" in url or ("channels.weixin.qq.com" in url and "login" not in url):
                        time.sleep(3)
                        self.driver.get(UPLOAD_URL)
                        time.sleep(5)
                        return True
                except Exception:
                    break
            print("⏰ 等待扫码超时")
            return False
        except Exception as e:
            print(f"⚠️ 登录检查失败: {e}")
            return False

    def _dismiss_dialogs(self):
        """关闭页面上所有"我知道了"提示弹窗（不点会离开页面的按钮）"""
        try:
            self.driver.execute_script("""
                function dismissAll(root) {
                    for (const btn of root.querySelectorAll("button")) {
                        const txt = btn.innerText.trim();
                        if (txt === "我知道了") btn.click();
                    }
                    for (const el of root.querySelectorAll("*")) {
                        if (el.shadowRoot) dismissAll(el.shadowRoot);
                    }
                }
                dismissAll(document);
            """)
            time.sleep(1)
        except Exception:
            pass

    def _upload_file(self, video_path: str):
        abs_path = os.path.abspath(video_path)
        self._dismiss_dialogs()

        # Shadow DOM file input — use CDP to bypass stale element issue
        for attempt in range(10):
            result = self.driver.execute_cdp_cmd('Runtime.evaluate', {
                'expression': """
                    (function() {
                        function findFileInput(root) {
                            for (const inp of root.querySelectorAll("input[type='file']")) {
                                if (inp.accept && inp.accept.includes("video")) return inp;
                            }
                            for (const el of root.querySelectorAll("*")) {
                                if (el.shadowRoot) {
                                    const f = findFileInput(el.shadowRoot);
                                    if (f) return f;
                                }
                            }
                            return null;
                        }
                        return findFileInput(document);
                    })()
                """,
                'returnByValue': False
            })
            obj_id = (result.get('result') or {}).get('objectId')
            if obj_id:
                self.driver.execute_cdp_cmd('DOM.setFileInputFiles', {
                    'files': [abs_path],
                    'objectId': obj_id
                })
                break
            time.sleep(2)
        else:
            raise RuntimeError("找不到视频上传 input")
        print("📤 文件已提交，等待上传完成...")

        # Wait for upload to finish: "发表" button becomes enabled (no _disabled class)
        for _ in range(120):
            time.sleep(5)
            result = self.driver.execute_cdp_cmd('Runtime.evaluate', {
                'expression': """
                    (function() {
                        function findSubmit(root) {
                            for (const btn of root.querySelectorAll("button")) {
                                const txt = btn.innerText.trim();
                                if (txt === "发表" && !btn.className.includes("_disabled")) return true;
                            }
                            for (const el of root.querySelectorAll("*")) {
                                if (el.shadowRoot && findSubmit(el.shadowRoot)) return true;
                            }
                            return false;
                        }
                        return findSubmit(document);
                    })()
                """,
                'returnByValue': True
            })
            if (result.get('result') or {}).get('value'):
                print("✅ 上传完成，发表按钮已激活")
                return
        print("⚠️ 上传等待超时，尝试继续")

    def _set_description(self, title: str):
        title = title[:200]
        try:
            # Use CDP to set textarea value without returning a WebElement reference
            set_ok = self.driver.execute_cdp_cmd('Runtime.evaluate', {
                'expression': f"""
                    (function() {{
                        function findDesc(root) {{
                            for (const el of root.querySelectorAll("textarea")) {{
                                if (el.className && el.className.includes("textarea-body")) return el;
                            }}
                            for (const el of root.querySelectorAll("*")) {{
                                if (el.shadowRoot) {{
                                    const f = findDesc(el.shadowRoot);
                                    if (f) return f;
                                }}
                            }}
                            return null;
                        }}
                        const desc = findDesc(document);
                        if (!desc) return false;
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(desc, {repr(title)});
                        desc.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return true;
                    }})()
                """,
                'returnByValue': True
            })
            if not (set_ok.get('result') or {}).get('value'):
                print("⚠️ 设置描述失败（未找到描述框）")
        except Exception as e:
            print(f"⚠️ 设置描述失败: {e}")

    def _submit(self) -> bool:
        try:
            result = self.driver.execute_cdp_cmd('Runtime.evaluate', {
                'expression': """
                    (function() {
                        function findSubmit(root) {
                            for (const btn of root.querySelectorAll("button")) {
                                const txt = btn.innerText.trim();
                                if (txt === "发表" && !btn.className.includes("_disabled")) return btn;
                            }
                            for (const el of root.querySelectorAll("*")) {
                                if (el.shadowRoot) {
                                    const f = findSubmit(el.shadowRoot);
                                    if (f) return f;
                                }
                            }
                            return null;
                        }
                        const btn = findSubmit(document);
                        if (!btn) return false;
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return true;
                    })()
                """,
                'returnByValue': True
            })
            ok = (result.get('result') or {}).get('value')
            if not ok:
                print("❌ 找不到可点击的发表按钮")
            return bool(ok)
        except Exception as e:
            print(f"❌ 点击发表失败: {e}")
            return False

    def _wait_for_success(self) -> bool:
        try:
            WebDriverWait(self.driver, 60).until(
                lambda d: (
                    any(kw in d.page_source for kw in ["发表成功", "发布成功", "上传成功"])
                    or "post/list" in d.current_url
                    or "manage" in d.current_url
                )
            )
            return True
        except Exception:
            try:
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_path = os.path.join(PROJECT_DIR, "temp", f"wechat_debug_{ts}.png")
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                self.driver.save_screenshot(debug_path)
                print(f"📸 截图已保存: {debug_path}")
            except Exception:
                pass
            print("⚠️ 60秒内未检测到成功提示，请手动确认")
            return False
