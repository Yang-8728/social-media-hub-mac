"""
Bilibili 上传器接口
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

from ...core.interfaces import IUploader
from ...core.models import Account, Video, UploadResult

class BilibiliUploader(IUploader):
    """Bilibili 上传器"""
    
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
        """上传视频文件
        
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
            
            # 不等待上传完成，直接开始设置其他信息
            # 等待页面基本元素加载
            time.sleep(3)
            
            # 填写标题
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

            # 快速选择分区
            try:
                print(f"🏷️ 快速设置分区为: {category}")
                
                # 使用更精确的B站分区选择器
                category_selected = False
                
                # 方法1: 直接查找分区下拉菜单（B站常用的class）
                try:
                    # B站投稿页面的分区选择器 
                    category_dropdown = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 
                            ".upload-section .type-selector, .select-type .select-box, .category-selector .select-inner, [class*='category'] [class*='select']"))
                    )
                    
                    # 滚动到分区选择器
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", category_dropdown)
                    time.sleep(0.5)
                    
                    # 点击展开分区菜单
                    category_dropdown.click()
                    print("✅ 分区下拉菜单已展开")
                    time.sleep(1)
                    
                    # 直接查找"小剧场"选项
                    xiaojuchang_option = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//*[text()='{category}' or contains(text(),'{category}')]"))
                    )
                    xiaojuchang_option.click()
                    print(f"✅ 已选择分区: {category}")
                    category_selected = True
                    
                except Exception as e1:
                    print(f"方法1失败: {e1}")
                    
                    # 方法2: 使用通用选择器查找
                    try:
                        # 查找所有可能的下拉菜单
                        dropdowns = self.driver.find_elements(By.CSS_SELECTOR, 
                            "[class*='select'], .dropdown, .category")
                        
                        for dropdown in dropdowns:
                            if dropdown.is_displayed() and "分区" in dropdown.text:
                                dropdown.click()
                                time.sleep(1)
                                
                                # 直接查找小剧场
                                try:
                                    option = self.driver.find_element(By.XPATH, f"//*[text()='{category}']")
                                    option.click()
                                    print(f"✅ 已选择分区: {category}")
                                    category_selected = True
                                    break
                                except:
                                    continue
                                    
                    except Exception as e2:
                        print(f"方法2失败: {e2}")
                
                # 如果分区选择成功，继续选择子分区
                if category_selected and subcategory:
                    print(f"🔍 快速选择子分区: {subcategory}")
                    time.sleep(1)  # 等待子分区选项加载
                    
                    try:
                        # 直接查找"搞笑研究所"子分区
                        subcategory_option = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//*[text()='{subcategory}' or contains(text(),'{subcategory}')]"))
                        )
                        subcategory_option.click()
                        print(f"✅ 已选择子分区: {subcategory}")
                        
                    except Exception as e3:
                        print(f"⚠️ 子分区选择失败: {e3}")
                        # 显示可用的子分区选项
                        try:
                            options = self.driver.find_elements(By.XPATH, "//*[contains(text(),'研究所') or contains(text(),'剧场')]")
                            if options:
                                print("🔍 可用的子分区选项:")
                                for opt in options[:5]:  # 只显示前5个
                                    if opt.is_displayed() and opt.text.strip():
                                        print(f"  - {opt.text.strip()}")
                        except:
                            pass
                
                if not category_selected:
                    print(f"⚠️ 快速分区选择失败，将使用默认分区")
                    
            except Exception as e:
                print(f"⚠️ 分区设置过程出错: {e}")
                print("将使用系统默认分区")

            # 无论分区是否成功，都继续执行投稿流程
            print("📋 分区设置完成，继续投稿流程...")
            
            # 尝试自动点击“立即投稿/发布/提交”按钮
            try:
                print("🔍 寻找并点击“立即投稿/发布/提交”按钮...")
                clicked = False
                # 先滚动到页面底部，因为立即投稿按钮在最下面
                print("⬇️ 滚动到页面底部寻找投稿按钮...")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                submit_selectors = [
                    # 根据原项目的选择器 - 关键是用span标签
                    (By.XPATH, '//span[contains(text(), "立即投稿")]'),
                    (By.XPATH, "//span[text()='立即投稿']"),
                    (By.XPATH, "//span[normalize-space(.)='立即投稿']"),
                    # 备选按钮选择器
                    (By.XPATH, "//button[contains(text(), '立即投稿')]"),
                    (By.XPATH, "//button[text()='立即投稿']"),
                    (By.XPATH, "//button[normalize-space(.)='立即投稿']"),
                    # 作为最后备选，查找所有span和button然后筛选
                    (By.TAG_NAME, "span"),
                    (By.TAG_NAME, "button")
                ]

                # 轮询等待可点击
                end_time = time.time() + 30
                while time.time() < end_time and not clicked:
                    for by, sel in submit_selectors:
                        try:
                            buttons = self.driver.find_elements(by, sel)
                            print(f"找到 {len(buttons)} 个可能的投稿按钮")
                            
                            for btn in buttons:
                                try:
                                    if btn.is_displayed() and btn.is_enabled():
                                        button_text = btn.text.strip()
                                        button_class = btn.get_attribute('class')
                                        print(f"🔍 检查元素: '{button_text}' (tag: {btn.tag_name}, class: {button_class})")
                                        
                                        # 专门匹配"立即投稿"，支持span和button标签
                                        if button_text == '立即投稿':
                                            print(f"🎯 找到立即投稿元素: '{button_text}' (tag: {btn.tag_name})")
                                            
                                            # 滚动到元素位置
                                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                            time.sleep(0.5)
                                            
                                            try:
                                                # 参考原项目，使用ActionChains点击
                                                from selenium.webdriver.common.action_chains import ActionChains
                                                ActionChains(self.driver).move_to_element(btn).pause(0.5).click().perform()
                                                print(f"✅ 已点击立即投稿(ActionChains): '{button_text}'")
                                                clicked = True
                                                break
                                            except Exception:
                                                # 如果ActionChains失败，尝试普通点击
                                                try:
                                                    btn.click()
                                                    print(f"✅ 已点击立即投稿(click): '{button_text}'")
                                                    clicked = True
                                                    break
                                                except Exception:
                                                    # 最后尝试JavaScript点击
                                                    self.driver.execute_script("arguments[0].click();", btn)
                                                    print(f"✅ 已点击立即投稿(JS): '{button_text}'")
                                                    clicked = True
                                                    break
                                        # 如果不是"立即投稿"，跳过其他元素
                                        elif button_text in ['添加分P', '添加分p', '选择文件', '上传', '浏览']:
                                            print(f"⚠️ 跳过元素: '{button_text}' (不是目标元素)")
                                            continue
                                except Exception as e:
                                    continue
                            
                            if clicked:
                                break
                                
                        except Exception:
                            continue
                    
                    if not clicked:
                        time.sleep(1)
                
                # 如果还是没找到，显示页面底部的所有按钮供调试
                if not clicked:
                    print("🔍 显示页面底部的所有按钮:")
                    all_buttons = self.driver.find_elements(By.XPATH, "//button")
                    for i, btn in enumerate(all_buttons[-10:]):  # 只显示最后10个按钮
                        try:
                            if btn.is_displayed():
                                btn_text = btn.text.strip()
                                btn_class = btn.get_attribute('class')
                                print(f"  按钮 {i+1}: '{btn_text}' (class: {btn_class})")
                        except:
                            continue

                # 若有确认弹窗，尝试点击“确定/确认/继续”
                if clicked:
                    try:
                        confirm = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((
                            By.XPATH,
                            "//button[contains(normalize-space(.), '确定') or contains(normalize-space(.), '确认') or contains(normalize-space(.), '继续') or contains(normalize-space(.), '我知道了')]"
                        )))
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm)
                        time.sleep(0.2)
                        try:
                            confirm.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", confirm)
                        print("✅ 已点击确认按钮")
                    except Exception:
                        pass

                    # 等待"稿件投递成功"提示
                    print("🔍 等待稿件投递成功提示...")
                    try:
                        # 专门检测"稿件投递成功"文字
                        success_element = WebDriverWait(self.driver, 120).until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'稿件投递成功')]"))
                        )
                        print("🎉 检测到'稿件投递成功'提示！")
                        
                        # 截图保存成功状态
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
                        time.sleep(1)  # 成功后1秒关闭
                        self.driver.quit()
                        return True
                        
                    except Exception:
                        print("⚠️ 等待120秒后未检测到'稿件投递成功'，可能仍需人工补充必填项")
                        return False
                else:
                    print("⚠️ 未找到可点击的投稿按钮，可能尚未满足必填项或页面布局变化")
                    return False
            except Exception as e:
                print(f"⚠️ 自动点击投稿按钮过程出错: {e}")
                return False
            
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
