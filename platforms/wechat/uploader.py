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
            chrome_options.add_argument("--window-position=100,100")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--remote-debugging-port=9224")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--log-level=3")

            service = Service()
            service.start_timeout = 60

            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 30)
            return True
        except Exception as e:
            print(f"❌ Chrome 启动失败: {e}")
            return False

    def upload(self, video_path: str, title: str) -> bool:
        try:
            if not self.setup_driver():
                return False
            self.driver.get(UPLOAD_URL)
            time.sleep(3)
            if not self._wait_for_login_if_needed():
                return False
            self._upload_file(video_path)
            self._set_title(title)
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
                        time.sleep(2)
                        self.driver.get(UPLOAD_URL)
                        time.sleep(3)
                        return True
                except Exception:
                    break
            print("⏰ 等待扫码超时")
            return False
        except Exception as e:
            print(f"⚠️ 登录检查失败: {e}")
            return False

    def _upload_file(self, video_path: str):
        abs_path = os.path.abspath(video_path)
        file_input = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(abs_path)
        try:
            WebDriverWait(self.driver, 30).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "[class*='progress'], [class*='upload']")
            )
            WebDriverWait(self.driver, 600).until_not(
                lambda d: any(
                    "uploading" in (el.get_attribute("class") or "")
                    for el in d.find_elements(By.CSS_SELECTOR, "[class*='upload']")
                )
            )
        except Exception:
            time.sleep(10)

    def _set_title(self, title: str):
        title = title[:80]
        try:
            title_elem = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "textarea[placeholder], input[placeholder*='标题'], textarea[class*='title'], input[class*='title']"
                ))
            )
            title_elem.clear()
            title_elem.send_keys(title)
        except Exception as e:
            print(f"⚠️ 设置标题失败: {e}")

    def _submit(self) -> bool:
        try:
            btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//button[contains(text(),'发表') or contains(text(),'发布') or contains(text(),'提交')]"
                ))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.5)
            btn.click()
            return True
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
