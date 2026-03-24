# src/ - 核心源代码目录

这是项目的核心源代码目录，包含所有主要功能模块。

## 📁 目录结构

```
src/
├── __init__.py              # 包初始化文件
├── core/                    # 核心功能模块
│   ├── interfaces.py        # 抽象接口定义
│   ├── models.py           # 数据模型定义
│   └── pipeline.py         # 核心处理流水线
├── platforms/              # 平台特定实现
│   ├── instagram/          # Instagram平台支持
│   │   └── downloader.py   # Instagram下载器 (已修复Unicode路径bug)
│   └── bilibili/           # Bilibili平台支持 (规划中)
├── accounts/               # 账户管理模块
├── exceptions/             # 自定义异常定义
└── utils/                  # 工具类和辅助函数
    ├── folder_manager.py   # 文件夹管理工具
    ├── logger.py          # 日志记录工具
    └── video_merger.py    # 视频合并工具 (支持智能分辨率)
```

## 🚀 主要功能

- **🔧 Core**: 提供抽象接口和数据模型，支持多平台扩展
- **📱 Platforms**: 各社交媒体平台的具体实现
- **👤 Accounts**: 多账户管理和切换
- **🛠️ Utils**: 通用工具类，包括文件管理、日志记录、视频处理

## 🎯 设计原则

- **模块化**: 每个平台独立实现，便于维护和扩展
- **可扩展**: 基于接口设计，易于添加新平台支持
- **健壮性**: 完善的错误处理和日志记录
- **Unicode支持**: 全面支持中文路径和文件名

## 🔍 关键文件说明

- `core/interfaces.py`: 定义所有平台必须实现的抽象接口
- `platforms/instagram/downloader.py`: Instagram核心下载逻辑，已修复Unicode路径问题
- `utils/video_merger.py`: 智能视频合并，支持不同分辨率自动标准化
- `utils/logger.py`: 统一日志管理，支持中文日志记录
