# 完整流程测试指南 - 带自动回退

## 📋 功能说明

### 测试脚本功能
- ✅ 下载新视频（最多3个）
- ✅ 自动标准化视频
- ✅ 合并视频
- ✅ 上传到B站
- ✅ **自动回退所有操作**

### 回退内容
1. ✅ 删除下载的视频文件
2. ✅ 删除下载的文件夹（空文件夹）
3. ✅ 删除下载日志记录
4. ✅ 删除标准化视频
5. ✅ 删除合并视频
6. ✅ 删除合并记录（**序号回退**）
7. ✅ 清理Redis缓存
8. ⚠️  B站视频需要**手动删除**

---

## 🚀 使用方法

### 方式1: 完整测试（推荐）

```bash
python test_full_flow_with_rollback.py
```

**流程：**
1. 提示确认是否开始测试
2. 执行下载 → 标准化 → 合并 → 上传
3. 提示确认是否回退
4. 自动清理所有测试数据
5. 保存测试记录到 JSON 文件
6. 提示手动删除B站视频

**预期结果：**
```
🧪 完整流程测试 - 带自动回退机制
============================================================
📱 账号: ai_vanvan
🌐 API地址: http://localhost:8080
⏰ 开始时间: 2025-10-17 14:30:00

⚠️  测试说明:
   1. 此测试会真实执行：下载 → 标准化 → 合并 → 上传
   2. 视频会真的上传到B站
   3. 测试后会自动回退所有操作
   4. B站上的视频需要手动删除

确认开始测试吗？(yes/no): yes

============================================================
📥 步骤 1/4: 下载最新内容
============================================================
✅ 发现 3 个新下载的视频

============================================================
🔗 步骤 2/4: 合并视频（包含标准化）
============================================================
✅ 合并完成
📁 合并输出: /app/videos/merged/ai_vanvan/ins海外离大谱#110.mp4

============================================================
🚀 步骤 3/4: 上传到B站
============================================================
✅ 上传成功

============================================================
🔙 步骤 4/4: 回退测试操作
============================================================
⚠️  确认要回退所有操作吗？(yes/no): yes

🔄 开始回退...
1️⃣ 删除下载的视频文件...
   ✅ 成功
2️⃣ 清理空文件夹...
   ✅ 成功
3️⃣ 删除下载日志记录...
   ✅ 成功
4️⃣ 删除标准化视频...
   ✅ 成功
5️⃣ 删除合并视频...
   ✅ 成功
6️⃣ 回退合并记录...
   ✅ 成功（序号已回退）
7️⃣ 清理Redis缓存...
   ✅ 成功

✅ 回退完成: 7/7 步成功

⚠️  重要提醒：需要手动删除B站视频！
============================================================
📹 视频: ins海外离大谱#110.mp4

💡 请访问: https://member.bilibili.com/platform/upload-manager/article
   找到今天上传的视频，点击删除
============================================================
```

---

### 方式2: 手动回退工具

如果测试中断或需要单独回退：

#### 回退今天的数据
```bash
python rollback_tool.py --today
```

#### 回退指定日期
```bash
python rollback_tool.py --date 2025-10-17
```

#### 回退最后一次合并
```bash
python rollback_tool.py --last-merge
```

#### 从测试记录文件回退
```bash
python rollback_tool.py --record test_record_20251017_143000.json
```

---

## 📝 测试记录

每次测试会自动保存记录到 JSON 文件：

**文件名格式：**
```
test_record_YYYYMMDD_HHMMSS.json
```

**文件内容示例：**
```json
{
  "account": "ai_vanvan",
  "start_time": "2025-10-17T14:30:00",
  "downloaded_videos": [
    "/app/downloads/ai_vanvan/2025-10-17/video1.mp4",
    "/app/downloads/ai_vanvan/2025-10-17/video2.mp4",
    "/app/downloads/ai_vanvan/2025-10-17/video3.mp4"
  ],
  "download_folders": [
    "/app/downloads/ai_vanvan/2025-10-17"
  ],
  "standardized_folders": [
    "/app/videos/standardized/ai_vanvan/2025-10-17"
  ],
  "merged_videos": [
    "/app/videos/merged/ai_vanvan/ins海外离大谱#110.mp4"
  ],
  "uploaded_videos": [
    {
      "local_path": "/app/videos/merged/ai_vanvan/ins海外离大谱#110.mp4",
      "bilibili_url": "https://www.bilibili.com/video/BVxxxxxxxx"
    }
  ],
  "download_records": [...],
  "merge_records": [...]
}
```

**用途：**
- 记录所有测试操作
- 测试中断后恢复回退
- 审计和追溯

---

## ⚠️ 重要注意事项

### 1. B站视频删除

**自动回退不包括B站视频！**

需要手动操作：
1. 访问：https://member.bilibili.com/platform/upload-manager/article
2. 找到测试时间上传的视频
3. 点击删除

### 2. 合并序号回退

回退会删除最后一条合并记录，序号自动回退：

**回退前：**
```json
{
  "merged_videos": [
    {"timestamp": "2025-10-16", "output_file": "ins海外离大谱#109.mp4"},
    {"timestamp": "2025-10-17", "output_file": "ins海外离大谱#110.mp4"}  ← 测试记录
  ]
}
```

**回退后：**
```json
{
  "merged_videos": [
    {"timestamp": "2025-10-16", "output_file": "ins海外离大谱#109.mp4"}
  ]
}
```

下次合并会再次使用 #110。

### 3. 测试中断处理

如果测试过程中按 Ctrl+C 中断：

```
⚠️  测试被中断！
是否要回退已执行的操作？
回退？(yes/no): yes
```

选择 `yes` 会自动清理已执行的步骤。

### 4. 多账号测试

目前脚本写死了 `ai_vanvan`，如果要测试其他账号：

修改脚本开头：
```python
ACCOUNT = "aigf8728"  # 改成你要测试的账号
```

---

## 🔍 回退验证

回退后检查：

### 1. 检查下载文件夹
```bash
docker exec social-media-hub-downloader-1 ls -la /app/downloads/ai_vanvan/
```
应该不包含今天的测试文件夹。

### 2. 检查合并记录
```bash
docker exec social-media-hub-merger-1 cat /app/logs/merges/ai_vanvan_merged_record.json
```
最后一条记录应该不是今天的。

### 3. 检查合并视频
```bash
docker exec social-media-hub-merger-1 ls -la /app/videos/merged/ai_vanvan/
```
测试的合并视频应该已删除。

### 4. 检查标准化文件
```bash
docker exec social-media-hub-standardizer-1 ls -la /app/videos/standardized/ai_vanvan/
```
测试的标准化文件应该已删除。

---

## 🎯 测试场景

### 场景1: 有新视频（完整流程）

**前提：**
- 账号今天收藏了3个新视频

**执行：**
```bash
python test_full_flow_with_rollback.py
```

**预期：**
- ✅ 下载3个视频
- ✅ 标准化3个视频
- ✅ 合并成1个视频
- ✅ 上传到B站
- ✅ 自动回退所有操作
- ⚠️  提示手动删除B站视频

### 场景2: 无新视频（正常退出）

**前提：**
- 账号今天没有新收藏

**执行：**
```bash
python test_full_flow_with_rollback.py
```

**预期：**
- ✅ 检测到无新视频
- ℹ️  直接退出，无需回退

### 场景3: 测试中断（手动回退）

**前提：**
- 测试到一半按 Ctrl+C

**执行：**
```bash
# 从记录文件回退
python rollback_tool.py --record test_record_20251017_143000.json

# 或直接回退今天的数据
python rollback_tool.py --today
```

**预期：**
- ✅ 清理所有测试数据
- ✅ 序号回退

---

## 📊 回退步骤详解

### 步骤1: 删除下载的视频文件

```bash
# 在 downloader 容器中执行
find /app/downloads/ai_vanvan -type f -name '*.mp4' \
  -newermt '2025-10-17' ! -newermt '2025-10-17 23:59:59' \
  -delete
```

### 步骤2: 清理空文件夹

```bash
find /app/downloads/ai_vanvan -type d -empty -delete
```

### 步骤3: 删除下载日志

```python
import json
log_file = '/app/logs/downloads/ai_vanvan_download.json'
data = json.load(open(log_file))
# 过滤掉今天的记录
data['downloads'] = [d for d in data['downloads'] 
                     if d.get('timestamp', '')[:10] != '2025-10-17']
json.dump(data, open(log_file, 'w'), indent=2)
```

### 步骤4: 删除标准化视频

```bash
# 在 standardizer 容器中执行
find /app/videos/standardized/ai_vanvan -type f -name '*ultimate.mp4' \
  -newermt '2025-10-17' ! -newermt '2025-10-17 23:59:59' \
  -delete
```

### 步骤5: 删除合并视频

```bash
# 在 merger 容器中执行
rm -f /app/videos/merged/ai_vanvan/ins海外离大谱#110.mp4
```

### 步骤6: 回退合并记录

```python
import json
log_file = '/app/logs/merges/ai_vanvan_merged_record.json'
data = json.load(open(log_file))
# 删除最后一条记录（如果是今天的）
if data['merged_videos'] and \
   data['merged_videos'][-1]['timestamp'][:10] == '2025-10-17':
    data['merged_videos'].pop()
json.dump(data, open(log_file, 'w'), indent=2, ensure_ascii=False)
```

### 步骤7: 清理Redis缓存

```bash
# 在 redis 容器中执行
redis-cli DEL merge_result_ai_vanvan
redis-cli DEL standardize_result_ai_vanvan
```

---

## 🛡️ 安全机制

### 1. 确认提示

脚本会在关键步骤要求确认：
- 开始测试前确认
- 回退前确认

### 2. 测试记录

所有操作记录到 JSON 文件，可追溯。

### 3. 时间标记

创建 `/tmp/test_start` 标记文件，确保只删除测试时间段的文件。

### 4. 条件删除

回退时检查：
- 只删除今天的数据
- 只删除测试时间段的文件
- 验证日期匹配

---

## 💡 最佳实践

### 1. 测试前准备

```bash
# 1. 确保服务运行
docker-compose ps

# 2. 确保有新视频（可选）
# 在Instagram收藏3个新视频

# 3. 备份重要数据（可选）
docker exec social-media-hub-merger-1 \
  cp /app/logs/merges/ai_vanvan_merged_record.json \
  /app/logs/merges/ai_vanvan_merged_record.json.backup
```

### 2. 测试执行

```bash
# 运行测试
python test_full_flow_with_rollback.py

# 按提示操作
# 测试完成后确认回退
```

### 3. 测试后验证

```bash
# 检查回退是否成功
python rollback_tool.py --today  # 如果已回退，不应有数据删除

# 手动删除B站视频
# 访问: https://member.bilibili.com/platform/upload-manager/article
```

---

## 🔧 故障排查

### 问题1: 回退失败

**症状：**
```
❌ 删除失败: No such file or directory
```

**解决：**
```bash
# 手动检查文件是否存在
docker exec social-media-hub-downloader-1 \
  ls -la /app/downloads/ai_vanvan/

# 使用手动回退工具
python rollback_tool.py --today
```

### 问题2: 序号未回退

**症状：**
下次合并仍然是 #111 而不是 #110

**解决：**
```bash
# 手动编辑合并记录
docker exec -it social-media-hub-merger-1 bash
vi /app/logs/merges/ai_vanvan_merged_record.json
# 删除最后一条记录，保存退出
```

### 问题3: Redis缓存未清理

**症状：**
合并时提示"任务已存在"

**解决：**
```bash
# 手动清理Redis
docker exec social-media-hub-redis-1 redis-cli FLUSHDB
```

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `test_full_flow_with_rollback.py` | 完整测试脚本（带自动回退） |
| `rollback_tool.py` | 手动回退工具 |
| `test_record_*.json` | 测试记录文件 |
| `TEST_REPORT_*.md` | 测试报告 |

---

## ✅ 检查清单

测试前：
- [ ] 服务已启动 (`docker-compose ps`)
- [ ] 了解回退机制
- [ ] 准备手动删除B站视频

测试中：
- [ ] 观察日志输出
- [ ] 记录异常情况
- [ ] 保存测试记录文件

测试后：
- [ ] 确认自动回退成功
- [ ] 手动删除B站视频
- [ ] 验证序号回退
- [ ] 清理测试记录文件（可选）

---

**准备好了吗？开始测试吧！** 🚀

```bash
python test_full_flow_with_rollback.py
```
