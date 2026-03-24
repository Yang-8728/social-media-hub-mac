# 测试回退快速参考

## 🚀 快速开始

### 完整测试（推荐）
```bash
python test_full_flow_with_rollback.py
```
按提示操作，测试完成后自动回退。

---

## 🔙 手动回退命令

### 回退今天的数据
```bash
python rollback_tool.py --today
```

### 回退指定日期
```bash
python rollback_tool.py --date 2025-10-17
```

### 回退最后一次合并
```bash
python rollback_tool.py --last-merge
```

### 从记录文件回退
```bash
python rollback_tool.py --record test_record_20251017_143000.json
```

---

## 📝 回退内容

| 项目 | 位置 | 操作 |
|------|------|------|
| 下载的视频 | `/app/downloads/{account}` | ✅ 自动删除 |
| 下载日志 | `/app/logs/downloads/{account}_download.json` | ✅ 自动删除记录 |
| 标准化视频 | `/app/videos/standardized/{account}` | ✅ 自动删除 |
| 合并视频 | `/app/videos/merged/{account}` | ✅ 自动删除 |
| 合并记录 | `/app/logs/merges/{account}_merged_record.json` | ✅ 自动回退序号 |
| Redis缓存 | `merge_result_{account}` | ✅ 自动清理 |
| B站视频 | https://member.bilibili.com | ⚠️ **手动删除** |

---

## ⚠️ 手动删除B站视频

1. 访问：https://member.bilibili.com/platform/upload-manager/article
2. 找到测试时间上传的视频
3. 点击删除

---

## 🔍 验证回退

### 检查下载文件夹
```bash
docker exec social-media-hub-downloader-1 ls -la /app/downloads/ai_vanvan/
```

### 检查合并记录
```bash
docker exec social-media-hub-merger-1 cat /app/logs/merges/ai_vanvan_merged_record.json | tail -20
```

### 检查最后序号
```bash
docker exec social-media-hub-merger-1 python -c "import json; data=json.load(open('/app/logs/merges/ai_vanvan_merged_record.json')); print('最后序号:', data['merged_videos'][-1]['output_file'] if data['merged_videos'] else '无')"
```

---

## 🛠️ 紧急回退（容器内执行）

如果Python脚本无法使用：

### 1. 删除今天的合并
```bash
docker exec social-media-hub-merger-1 bash -c "
python -c \"
import json
log_file='/app/logs/merges/ai_vanvan_merged_record.json'
data=json.load(open(log_file))
if data['merged_videos'] and data['merged_videos'][-1]['timestamp'][:10]=='2025-10-17':
    output_file=data['merged_videos'][-1]['output_file']
    import os; os.system(f'rm -f {output_file}')
    data['merged_videos'].pop()
    json.dump(data,open(log_file,'w'),indent=2,ensure_ascii=False)
    print('✅ 已删除')
\"
"
```

### 2. 清理Redis
```bash
docker exec social-media-hub-redis-1 redis-cli DEL merge_result_ai_vanvan
```

### 3. 删除下载文件
```bash
docker exec social-media-hub-downloader-1 bash -c "
find /app/downloads/ai_vanvan -type f -newermt '2025-10-17' ! -newermt '2025-10-17 23:59:59' -delete
find /app/downloads/ai_vanvan -type d -empty -delete
"
```

---

## 📞 常见问题

### Q: 测试中断了怎么办？
A: 运行 `python rollback_tool.py --today`

### Q: 如何确认回退成功？
A: 检查合并记录文件，最后一条不应该是今天的日期

### Q: B站视频忘记删除了？
A: 访问 https://member.bilibili.com/platform/upload-manager/article 手动删除

### Q: 序号能回退吗？
A: 能！删除合并记录后，序号会自动回退到上一个

### Q: 能回退多天的数据吗？
A: 能！使用 `--date` 参数指定日期

---

## 🎯 测试检查清单

**测试前：**
- [ ] `docker-compose ps` 确认服务运行
- [ ] 确保账号有新视频（或准备测试无新视频场景）

**测试中：**
- [ ] 观察每个步骤的输出
- [ ] 记录任何错误信息

**测试后：**
- [ ] 确认回退脚本执行成功
- [ ] 手动删除B站视频
- [ ] 验证序号回退（下次合并应该使用相同序号）

---

**快速命令：**
```bash
# 测试
python test_full_flow_with_rollback.py

# 回退
python rollback_tool.py --today

# 验证
docker exec social-media-hub-merger-1 cat /app/logs/merges/ai_vanvan_merged_record.json | tail -5
```
