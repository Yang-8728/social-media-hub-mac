"""
Bilibili 上传器接口 - 优化版本
"""
import os
import time
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from ...core.interfaces import IUploader
from ...core.models import Account, Video, UploadResult

class BilibiliUploader(IUploader):
    """Bilibili 上传器 - 优化版本"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.driver = None
        self.wait = None
    
    def setup_driver(self):
        """设置Chrome驱动 - 使用保存的配置文件"""
        try:
            chrome_options = Options()
            
            # 使用已保存的配置文件
            profile_path = f"c:\\Code\\social-media-hub\\tools\\profiles\\chrome_profile_{self.account_name}"
            
            if os.path.exists(profile_path):
                chrome_options.add_argument(f"--user-data-dir={profile_path}")
                chrome_options.add_argument("--profile-directory=Default")
                print(f"✅ 使用已保存的配置文件: {profile_path}")
            else:
                print(f"❌ 配置文件不存在: {profile_path}")
                return False
            
            chrome_options.add_argument("--window-size=1200,800")
            chrome_options.add_argument("--window-position=100,100")
            
            # 禁用一些干扰选项
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            print("🚀 启动Chrome浏览器...")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 30)
            
            print("✅ Chrome启动成功")
            return True
        except Exception as e:
            print(f"❌ Chrome驱动设置失败: {e}")
            return False
    
    def login(self, account: Account) -> bool:
        """登录Bilibili账号"""
        # TODO: 实现Chrome配置文件登录
        pass
    
    def upload_video(self, account: Account, video: Video) -> UploadResult:
        """上传视频到Bilibili"""
        # TODO: 实现视频上传逻辑
        pass
    
    def get_upload_history(self, account: Account) -> List[Video]:
        """获取上传历史"""
        # TODO: 实现上传历史查询
        pass
    
    def upload(self, video_path: str, category: str = "生活", subcategory: str = None) -> bool:
        """优化的上传视频文件方法
        
        Args:
            video_path: 视频文件路径
            category: B站分区类别，如："生活"、"娱乐"、"科技"、"游戏"、"小剧场"等
            subcategory: 子分区，如："搞笑研究所"（当主分区为"小剧场"时）
        """
        try:
            print(f"📤 开始上传视频: {video_path}")
            print(f"🏷️ 目标分区: {category}")
            if subcategory:
                print(f"🏷️ 目标子分区: {subcategory}")
            
            # 设置驱动
            if not self.setup_driver():
                return False
            
            # 直接打开B站上传页面（应该已经登录）
            print("🌐 打开B站上传页面...")
            self.driver.get("https://member.bilibili.com/platform/upload/video/")
            time.sleep(5)
            
            # 检查是否成功到达上传页面
            current_url = self.driver.current_url
            if "upload" not in current_url:
                print("❌ 未能到达上传页面，可能需要重新登录")
                return False
                
            print("✅ 已到达上传页面")
            
            # 等待并选择视频文件
            print("📁 选择视频文件...")
            file_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            
            # 上传文件
            abs_video_path = os.path.abspath(video_path)
            file_input.send_keys(abs_video_path)
            print(f"✅ 文件已选择: {abs_video_path}")
            print("📤 视频开始上传，同时设置其他信息...")
            
            # 等待页面基本元素加载，然后并行处理
            time.sleep(3)
            
            # 1. 填写标题（快速处理）
            self._set_title(video_path)
            
            # 2. 快速设置分区（不等待上传完成）
            self._set_category_fast(category, subcategory)
            
            # 3. 等待并点击立即投稿
            return self._submit_and_wait_success()
            
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
    
    def _set_title(self, video_path: str):
        """快速设置标题"""
        try:
            title_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='标题'], input[placeholder*='请填写标题']"))
            )
            title_input.clear()
            title = f"AI助手自动上传 - {os.path.basename(video_path)}"
            title_input.send_keys(title)
            print(f"📝 标题已设置: {title}")
        except:
            print("⚠️ 无法自动填写标题，请手动填写")
    
    def _set_category_fast(self, category: str, subcategory: str = None):
        """快速设置分区"""
        try:
            print(f"🏷️ 快速设置分区为: {category}")
            
            # 直接使用B站的分区选择器
            try:
                # 等待分区选择器加载
                category_dropdown = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 
                        ".upload-section .type-selector, .select-type .select-box, .category-selector .select-inner, [class*='category'] [class*='select']"))
                )
                
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", category_dropdown)
                time.sleep(0.5)
                category_dropdown.click()
                print("✅ 分区下拉菜单已展开")
                time.sleep(1)
                
                # 直接查找目标分区
                category_option = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[text()='{category}']"))
                )
                category_option.click()
                print(f"✅ 已选择分区: {category}")
                
                # 如果有子分区，继续选择
                if subcategory:
                    time.sleep(1)  # 等待子分区加载
                    subcategory_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//*[text()='{subcategory}']"))
                    )
                    subcategory_option.click()
                    print(f"✅ 已选择子分区: {subcategory}")
                    
            except Exception as e1:
                print(f"⚠️ 快速分区选择失败: {e1}")
                # 使用通用方法作为备选
                self._set_category_fallback(category, subcategory)
                
        except Exception as e:
            print(f"⚠️ 分区设置出错: {e}")
    
    def _set_category_fallback(self, category: str, subcategory: str = None):
        """分区设置的备选方法"""
        try:
            # 查找任何包含"分区"或"选择"的元素
            selectors = self.driver.find_elements(By.XPATH, "//*[contains(text(), '分区') or contains(@class, 'select')]")
            for selector in selectors:
                if selector.is_displayed():
                    try:
                        selector.click()
                        time.sleep(1)
                        
                        # 查找目标分区
                        option = self.driver.find_element(By.XPATH, f"//*[text()='{category}']")
                        option.click()
                        print(f"✅ 备选方法设置分区: {category}")
                        
                        if subcategory:
                            time.sleep(1)
                            sub_option = self.driver.find_element(By.XPATH, f"//*[text()='{subcategory}']")
                            sub_option.click()
                            print(f"✅ 备选方法设置子分区: {subcategory}")
                        break
                    except:
                        continue
        except Exception as e:
            print(f"⚠️ 备选分区设置也失败: {e}")
    
    def _submit_and_wait_success(self) -> bool:
        """提交投稿并等待成功"""
        try:
            print("📋 准备提交投稿...")
            
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # 快速定位立即投稿按钮
            try:
                submit_button = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='立即投稿']"))
                )
                
                print("🎯 找到立即投稿按钮")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                time.sleep(0.5)
                
                # 点击投稿
                ActionChains(self.driver).move_to_element(submit_button).pause(0.5).click().perform()
                print("✅ 立即投稿按钮已点击")
                
            except Exception:
                # 备选方法
                spans = self.driver.find_elements(By.TAG_NAME, "span")
                for span in spans:
                    if span.is_displayed() and span.text.strip() == "立即投稿":
                        ActionChains(self.driver).move_to_element(span).click().perform()
                        print("✅ 立即投稿按钮已点击 (备选方法)")
                        break
                else:
                    print("❌ 未找到立即投稿按钮")
                    return False
            
            # 处理确认弹窗
            try:
                confirm = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '确定') or contains(text(), '确认')]"))
                )
                confirm.click()
                print("✅ 已点击确认按钮")
            except:
                pass
            
            # 等待"稿件投递成功"提示
            print("🔍 等待稿件投递成功提示...")
            try:
                success_element = WebDriverWait(self.driver, 120).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'稿件投递成功')]"))
                )
                print("🎉 检测到'稿件投递成功'提示！")
                
                # 截图保存
                try:
                    import datetime
                    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_dir = "c:/Code/social-media-hub/temp"
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = f"{screenshot_dir}/稿件投递成功_{now}.png"
                    self.driver.save_screenshot(screenshot_path)
                    print(f"📸 已保存成功截图: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ 截图保存失败: {e}")
                    
                print("✅ 稿件投递成功！1秒后关闭浏览器...")
                time.sleep(1)
                self.driver.quit()
                return True
                
            except Exception:
                print("⚠️ 等待120秒后未检测到'稿件投递成功'")
                return False
                
        except Exception as e:
            print(f"❌ 提交过程失败: {e}")
            return False
