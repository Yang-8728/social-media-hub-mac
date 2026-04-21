# Social Media Hub — ai_vanvan

Instagram内容自动下载、合并、上传B站，并通过Telegram Bot管理评论。

## 功能

- **全自动流程**：Instagram收藏 → 下载 → 合并视频 → 上传B站 → 设置标题/简介/章节评论置顶
- **评论实时监控**：B站评论30秒轮询，垃圾评论自动删除+拉黑，真实评论转发到Telegram
- **Telegram Bot**：所有操作通过手机Telegram远程控制

## 项目结构

```
├── main.py                    # 主流程入口
├── bili_monitor.py            # B站通知轮询（评论/@ /私信）
├── export_bili_cookies.py     # 导出B站Cookie（首次或过期时运行）
├── telegram-bot/
│   └── bot.py                 # Telegram Bot 主程序
├── core/
│   ├── config.py              # 配置（token、路径等）
│   ├── tg_client.py           # Telegram消息发送
│   └── interaction_queue.py   # 用户交互队列
├── features/
│   ├── bili_pipeline.py       # 完整流程（下载→合并→上传）
│   ├── download_only.py       # 仅下载（测试用）
│   ├── spam_cleaner.py        # 垃圾评论扫描清理
│   └── comment_monitor.py     # 实时评论监控
├── src/
│   ├── platforms/instagram/   # Instagram下载器
│   ├── platforms/bilibili/    # B站上传器
│   └── utils/                 # 视频合并、日志等工具
├── config/
│   ├── accounts.json          # 账号配置
│   └── quark.json             # 夸克网盘链接配置
└── tools/
    └── profiles/              # Chrome Profile（本地，不入库）
```

## Telegram Bot 命令

| 命令 | 功能 |
|------|------|
| `/bilibili` | 执行完整流程（下载→合并→上传） |
| `/download` | 仅扫描并下载新视频（不合并不上传） |
| `/auto_clean` | 自动扫描并删除最近3个视频的垃圾评论 |
| `/clean_comments` | 逐条确认模式扫描垃圾评论 |
| `/addspam 关键词` | 添加自定义垃圾词到词库 |
| `/help` | 显示帮助 |

## 评论监控逻辑

- **垃圾评论**（命中关键词/含链接）→ 自动删除 + 拉黑 + TG通知（含评论链接）
- **含图片内容**（`[xxx]`格式）→ 加⚠️警告转发
- **普通评论** → 转发到TG，可回复 `1` 删除+拉黑+加词库，`0` 跳过

## 环境要求

- Python 3.11+
- Chrome + ChromeDriver
- ffmpeg（`/opt/homebrew/bin/ffmpeg`）
- Instaloader

安装依赖：
```bash
pip install -r requirements.txt
```

## 首次配置

1. 填写账号配置 `config/accounts.json`

2. 在 `core/config.py` 填写 Telegram Bot Token 和 Chat ID

3. 导出B站Cookie（需要先用Chrome登录B站）：
   ```bash
   python3 export_bili_cookies.py
   ```

4. 启动Bot（手动）：
   ```bash
   python3 telegram-bot/bot.py
   ```

5. 或通过 LaunchAgent 开机自启（macOS）：
   ```bash
   launchctl load ~/Library/LaunchAgents/com.yanglan.telegrambot.plist
   ```

## Cookie维护

B站Cookie有效期约1个月。过期时Telegram会收到提醒：
> ⚠️ B站Cookie已过期，请在Mac上运行：python3 export_bili_cookies.py

以下文件保存在本地，不入git：
- `bili_cookies_ai_vanvan.json` — B站登录Cookie
- `bili_monitor_state.json` — 通知轮询游标
- `spam_keywords_custom.json` — 自定义垃圾词库
- `tools/profiles/` — Chrome Profile
- `logs/` — 下载/合并记录
