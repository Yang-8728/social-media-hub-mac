# Twitter 集成设置指南

## 概述
本指南将帮助你完成 Twitter API 的配置，实现从 Twitter Bookmarks 下载视频的功能。

## 前提条件
- ✅ Twitter 开发者账号已申请（用户名：marclan10）
- ✅ 已安装 tweepy 库
- ✅ 代码已集成到项目中

## 步骤 1: 创建 Twitter App

1. 访问 Twitter Developer Portal: https://developer.twitter.com/en/portal/dashboard

2. 点击 "Projects & Apps" → "Overview"

3. 点击 "+ Create App" 或 "+ Add App"

4. 填写 App 信息：
   - **App name**: `social-media-hub-downloader` (或其他名称)
   - **Description**: `Personal tool for downloading bookmarked videos from Twitter`
   - **Website URL**: 可以填写 `https://github.com/yourusername/social-media-hub` (或任意有效URL)
   - **Callback URL**: 留空（我们使用的是 OAuth 1.0a User Context）
   - **Tell us how this app will be used**: 
     ```
     This app is a personal automation tool that helps me organize and download 
     video content from my Twitter bookmarks for offline viewing and content curation. 
     It uses the Twitter API v2 to access my own bookmarks and download videos that 
     I have saved.
     ```

5. 点击 "Create" 创建应用

## 步骤 2: 获取 API Keys

创建 App 后，你会看到 App 的详情页面：

1. 找到 "Keys and tokens" 标签页

2. 你会看到以下信息：
   - **API Key** (也叫 Consumer Key)
   - **API Secret Key** (也叫 Consumer Secret)

3. 点击 "Generate" 按钮生成 **Access Token & Secret**：
   - **Access Token**
   - **Access Token Secret**

4. **重要**: 立即复制并保存这些密钥！它们只会显示一次。

## 步骤 3: 配置权限

1. 在 App 设置页面，找到 "User authentication settings"

2. 点击 "Set up" 配置认证

3. 选择权限：
   - ✅ **Read** (必须)
   - ⬜ Write (不需要)
   - ⬜ Direct Messages (不需要)

4. App 类型选择：
   - 选择 **Native App** 或 **Web App**

5. Callback URL / Redirect URL:
   - 填写 `http://localhost:3000/callback` (即使不使用也需要填写)

6. Website URL:
   - 填写任意有效 URL，如 `https://github.com`

7. 保存设置

## 步骤 4: 更新配置文件

将获取的 API Keys 填入 `config/accounts.json` 中的 `twitter_funny` 账号配置：

```json
{
  "twitter_funny": {
    "name": "twitter_funny",
    "platform": "twitter",
    "username": "marclan10",
    "folder_strategy": "daily",
    "title_prefix": "推特搞笑#",
    "twitter_api": {
      "api_key": "你的_API_KEY",
      "api_secret": "你的_API_SECRET",
      "access_token": "你的_ACCESS_TOKEN",
      "access_token_secret": "你的_ACCESS_TOKEN_SECRET"
    },
    "download_safety": {
      "max_posts_per_session": 50,
      "request_delay": 30
    }
  }
}
```

## 步骤 5: 测试连接

运行以下命令测试 Twitter API 连接：

```bash
python main.py --login --twitter_funny
```

如果看到 "✅ Twitter 认证成功: @marclan10"，说明配置成功！

## 步骤 6: 下载视频

测试下载功能：

```bash
# 下载 20 个 Bookmarks 中的视频
python main.py --download --twitter_funny --limit 20
```

## API 限制说明

Twitter API Free Tier 限制：
- **GET Bookmarks**: 180 requests / 15 minutes
- **每次请求**: 最多返回 100 条 bookmarks
- **月度限制**: 10,000 tweets read per month

建议：
- 每天运行 1-2 次即可
- 每次下载 20-50 个视频
- 设置 `request_delay: 30` 秒避免触发限制

## 常见问题

### Q1: 提示 "403 Forbidden" 错误
**A**: 检查 App 权限设置，确保启用了 "Read" 权限

### Q2: 提示 "401 Unauthorized" 错误
**A**: API Keys 可能填写错误，重新检查配置文件中的 4 个密钥

### Q3: 找不到视频
**A**: 
- 确保你的 Twitter Bookmarks 中有视频内容
- Twitter API 只能访问最近的 800 条 bookmarks

### Q4: 下载速度慢
**A**: 这是正常的，`request_delay: 30` 秒是为了避免触发 API 限制

## 文件结构

下载的视频会保存在：
```
videos/downloads/twitter_funny/
  └── 2026-02-04/          # 按日期分组（daily 策略）
      ├── 1234567890.mp4   # Tweet ID 作为文件名
      ├── 1234567890.json  # 推文元数据
      ├── 1234567891.mp4
      └── 1234567891.json
```

## 下一步

配置完成后，你可以：
1. 定期运行下载命令获取新视频
2. 使用合并功能处理视频
3. 上传到 Bilibili（需要配置 Bilibili 上传设置）

## 参考链接

- Twitter Developer Portal: https://developer.twitter.com/en/portal/dashboard
- Twitter API v2 文档: https://developer.twitter.com/en/docs/twitter-api
- Tweepy 文档: https://docs.tweepy.org/
