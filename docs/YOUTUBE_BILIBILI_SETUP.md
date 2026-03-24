# YouTube + 新 B 站账号配置指南

## 📋 配置概览

现在系统支持两个独立的 B 站账号：
- **ai_vanvan** → 原有 B 站账号（搞笑内容）
- **youtube** → 新 B 站账号（YouTube 搞笑内容）

---

## 🎯 账号映射关系

### ai_vanvan 账号
```bash
python main.py --ai_vanvan
```
- 📥 下载：Instagram (ai_vanvan)
- 📤 上传：原有 B 站账号
- 🏷️ 标题：ins海外离大谱#序号

### youtube 账号
```bash
python main.py --youtube
```
- 📥 下载：YouTube 点赞视频
- 📤 上传：新 B 站账号（纯搞笑）
- 🏷️ 标题：YouTube搞笑#序号

---

## 🚀 配置步骤

### 步骤 1：创建新 B 站账号的 Chrome Profile

运行配置脚本：
```bash
python tools/setup/create_youtube_bilibili_profile.py
```

**操作流程**：
1. 脚本会自动打开 Chrome 浏览器
2. 自动导航到 B 站登录页面
3. **你需要**：用新的 B 站搞笑账号登录
4. 登录成功后按 Enter
5. 脚本会验证登录状态并保存

### 步骤 2：测试 YouTube 下载

```bash
python main.py --download --youtube
```

这会：
- ✅ 下载你新点赞的 YouTube 视频
- ✅ 跳过 885 个历史点赞
- ✅ 保存到 `videos/downloads/youtube/2026-02-05/`

### 步骤 3：测试完整流程

```bash
python main.py --youtube
```

这会：
- 📥 下载新点赞的视频
- 🔄 合并标准化
- 📤 上传到**新 B 站账号**

---

## 📁 文件结构

```
tools/profiles/
├── chrome_profile_ai_vanvan/      # ai_vanvan 的 B 站账号
├── chrome_profile_aigf8728/       # aigf8728 的 B 站账号
└── chrome_profile_youtube/        # YouTube 的新 B 站账号（新建）

videos/downloads/
├── ai_vanvan/                     # Instagram 下载
│   └── 2026-02-05/
└── youtube/                       # YouTube 下载
    └── 2026-02-05/

videos/merged/
├── ai_vanvan/                     # Instagram 合并
└── youtube/                       # YouTube 合并

logs/episodes/
├── ai_vanvan_episode.txt          # ai_vanvan 序号（当前：84）
└── youtube_episode.txt            # YouTube 序号（从 1 开始）
```

---

## 🎬 标题格式

### ai_vanvan
```
ins海外离大谱#84
ins海外离大谱#85
ins海外离大谱#86
...
```

### youtube
```
YouTube搞笑#1
YouTube搞笑#2
YouTube搞笑#3
...
```

---

## 💡 使用场景

### 场景 1：只下载 YouTube 视频
```bash
# 1. 去 YouTube 点赞视频
# 2. 运行下载
python main.py --download --youtube
```

### 场景 2：YouTube 完整流程
```bash
# 一键完成：下载 → 合并 → 上传到新 B 站账号
python main.py --youtube
```

### 场景 3：Instagram 完整流程
```bash
# 一键完成：下载 → 合并 → 上传到原 B 站账号
python main.py --ai_vanvan
```

### 场景 4：同时运行两个账号
```bash
# 先运行 Instagram
python main.py --ai_vanvan

# 再运行 YouTube
python main.py --youtube
```

---

## 🔧 配置文件

### config/accounts.json

```json
{
  "ai_vanvan": {
    "bilibili": {
      "chrome_profile_path": "c:\\Code\\social-media-hub\\tools\\profiles\\chrome_profile_ai_vanvan"
    }
  },
  "youtube": {
    "bilibili": {
      "chrome_profile_path": "c:\\Code\\social-media-hub\\tools\\profiles\\chrome_profile_youtube"
    },
    "upload_settings": {
      "title_pattern": "YouTube搞笑#{序号}",
      "next_number": 1
    }
  }
}
```

---

## ✅ 验证清单

配置完成后，请验证：

- [ ] 新 B 站账号已注册
- [ ] Chrome Profile 已创建（运行 create_youtube_bilibili_profile.py）
- [ ] 新 B 站账号已登录并保存
- [ ] YouTube 下载测试成功
- [ ] YouTube 上传测试成功（可选）

---

## 🎉 总结

现在你有两个完全独立的工作流：

1. **Instagram → 原 B 站账号**
   - 命令：`python main.py --ai_vanvan`
   - 内容：Instagram 搞笑视频

2. **YouTube → 新 B 站账号**
   - 命令：`python main.py --youtube`
   - 内容：YouTube 搞笑视频（纯搞笑，无擦边）

两个账号互不干扰，各自管理序号和上传！

---

**创建时间**: 2026-02-05
**状态**: ✅ 配置完成，等待测试
