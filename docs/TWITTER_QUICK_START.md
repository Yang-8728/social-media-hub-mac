# Twitter 快速开始

## 🚀 3 步开始使用

### 步骤 1: 获取 API Keys (5分钟)

1. 访问：https://developer.twitter.com/en/portal/dashboard
2. 创建 App：点击 "+ Create App"
3. 获取密钥：在 "Keys and tokens" 页面生成并复制 4 个密钥

### 步骤 2: 配置密钥 (1分钟)

编辑 `config/accounts.json`，找到 `twitter` 部分，填入你的密钥：

```json
"twitter_api": {
  "api_key": "粘贴你的 API Key",
  "api_secret": "粘贴你的 API Secret",
  "access_token": "粘贴你的 Access Token",
  "access_token_secret": "粘贴你的 Access Token Secret"
}
```

### 步骤 3: 测试运行 (1分钟)

```bash
# 测试登录
python main.py --login --twitter

# 下载 5 个视频测试
python main.py --download --twitter --limit 5
```

## ✅ 成功标志

看到以下输出说明成功：
```
✅ Twitter 认证成功: @marclan10
找到 X 个 Bookmarks
发现 X 个新视频
✅ 下载成功: xxx.mp4
```

## 📁 文件位置

下载的视频在：
```
videos/downloads/twitter/2026-02-04/
```

## 🎯 常用命令

```bash
# 每天运行一次，下载新视频
python main.py --download --twitter --limit 20

# 查看状态
python main.py --status --twitter

# 查看文件夹
python main.py --folders --twitter
```

## 💡 提示

- 第一次运行会下载所有 bookmarks 中的视频
- 之后只下载新收藏的视频（自动去重）
- 建议每天运行 1 次，每次 --limit 20
- 如果遇到问题，查看 `TWITTER_SETUP_GUIDE.md` 详细指南

## 🆚 对比 Instagram

| 特性 | Instagram | Twitter |
|------|-----------|---------|
| API 稳定性 | ❌ 容易 429 | ✅ 官方 API |
| 速率限制 | ⚠️ 不明确 | ✅ 180/15min |
| 认证方式 | 🦊 Firefox Session | 🔑 API Keys |
| IP 封禁风险 | ⚠️ 高 | ✅ 低 |
| 设置难度 | 简单 | 简单 |

## 🎉 完成！

配置完成后，你就有了双平台下载能力：
- Instagram: `--ai_vanvan` / `--aigf8728`
- Twitter: `--twitter`

可以根据需要选择使用哪个平台！
