# CLAUDE.md — Social Media Hub

## Git

- Remote 名称是 `mac`，不是 `origin`
- Push 命令：`git push mac main`
- 每个 GitHub Issue 对应一个单独的 commit，commit message 里注明 `Closes #N`
- 多个 issue 同时处理时，必须分开提交，不能合并成一个 commit
- 做完一个 issue 立即 commit，不攒

## 目录结构

```
social-media-hub/
├── bot/                        # Telegram Bot
│   ├── bot.py                  # 主循环 + 命令路由
│   ├── tg_client.py
│   ├── interaction_queue.py
│   └── handlers/
│       └── bilibili_comments.py
│
├── platforms/                  # 平台连接层（每个平台自包含）
│   ├── instagram/
│   ├── bilibili/               # uploader.py / monitor.py / merger.py
│   ├── youtube/
│   ├── wechat/
│   └── quark/
│
├── pipelines/                  # 跨平台流程
│   ├── instagram_to_bili.py
│   ├── youtube_to_wechat.py
│   └── quark_share.py
│
├── config/                     # 非敏感配置
├── scripts/                    # 手动维护脚本
├── tests/
├── tools/profiles/             # Chrome 登录状态（gitignored）
├── logs/                       # 运行日志（gitignored）
├── temp/                       # 截图、session、cookie（gitignored）
├── videos/                     # 下载的视频（gitignored）
├── main.py
└── requirements.txt
```

## 新功能放置规则

- 新平台 → `platforms/平台名/`
- 新跨平台流程 → `pipelines/`
- 新 Bot 命令 → `bot/handlers/`
- 手动维护脚本 → `scripts/`
- **根目录不新建任何文件或文件夹**
- 运行时生成的文件（cookie、session、json 状态）一律放 `temp/`

## 架构原则

- `platforms/` 是原子操作层，每个平台文件夹自包含，不共享 utils
- `pipelines/` 是跨平台串联层
- 哪怕两个平台有相似逻辑，也各自实现

## Bot 运行

- LaunchAgent 自动启动：`com.yanglan.telegrambot.plist`
- 重启命令：`launchctl unload ~/Library/LaunchAgents/com.yanglan.telegrambot.plist && launchctl load ~/Library/LaunchAgents/com.yanglan.telegrambot.plist`
- 日志：`tail -f /Users/yanglan/Code/telegram-bot/bot.log`
- Python：`/opt/homebrew/bin/python3`
