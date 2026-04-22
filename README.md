# Social Media Hub — ai_vanvan

Instagram 内容自动下载、合并、上传 B站，通过 Telegram Bot 远程管理。

## 功能

- **全自动流程**：Instagram 收藏 → 下载 → 合并 → 上传 B站 → 标题/章节评论自动发布置顶
- **评论监控**：B站评论/私信/@ 实时推送到 Telegram，垃圾评论自动删除+拉黑
- **粉丝分享**：下载 IG 账号视频打包上传夸克网盘，生成分享链接并回复 B站评论
- **微信视频号**：YouTube 视频下载后自动上传视频号

## Telegram 命令

| 命令 | 功能 |
|------|------|
| `/bilibili` | 全流程（下载 → 合并 → 上传 B站） |
| `/download` | 仅下载新视频（不合并不上传） |
| `/share ig用户名 [rpid]` | 下载 IG 合集打包上传夸克，可附带回复 B站评论 |
| `/wechat <YouTube URL>` | 下载并上传到微信视频号 |
| `/clean_comments` | 垃圾评论逐条确认模式 |
| `/auto_clean` | 自动删除所有垃圾评论 |
| `/addspam 关键词` | 添加自定义垃圾词 |
| `/help` | 显示帮助 |

## 环境要求

- macOS，Python 3.11+
- Chrome + ChromeDriver
- ffmpeg（`brew install ffmpeg`）
- yt-dlp（`brew install yt-dlp`）

```bash
pip install -r requirements.txt
```

## 首次配置

1. 填写 `config/accounts.json` 账号信息
2. 填写 `config/quark.json` 夸克 cookie
3. 导出 B站 Cookie（Chrome 登录 B站后运行）：
   ```bash
   python3 scripts/export_bili_cookies.py
   ```
4. 通过 LaunchAgent 开机自启：
   ```bash
   launchctl load ~/Library/LaunchAgents/com.yanglan.telegrambot.plist
   ```

## Cookie 维护

B站 Cookie 约 1 个月过期，过期时 Telegram 会收到提醒。以下文件保存本地，不入 git：

- `temp/bili_cookies_ai_vanvan.json` — B站 Cookie
- `temp/bili_monitor_state.json` — 通知轮询游标
- `config/spam_keywords_custom.json` — 自定义垃圾词库
- `tools/profiles/` — Chrome Profile
