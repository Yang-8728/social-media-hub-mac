# 微服务测试指南

## 测试顺序

### 1. 测试 Standardizer 服务（视频标准化）

```bash
python test_standardizer.py
```

**功能**：
- 测试 Standardizer 服务的视频标准化功能
- 使用 3 个已下载的视频进行测试
- 输出到独立的测试文件夹，不影响生产数据

**预期结果**：
- 请求成功返回 200
- 生成 3 个标准化文件 (`*_ultimate.mp4`)
- 显示文件列表和大小

**清理**：
```bash
docker exec social-media-hub-standardizer-1 rm -rf /app/videos/standardized/ai_vanvan/test
```

---

### 2. 测试 Merger 服务（视频合并）

```bash
python test_merger.py
```

**前置条件**：
- 必须先运行 `test_standardizer.py` 生成标准化文件

**功能**：
- 测试 Merger 服务的视频合并功能
- 使用已标准化的文件进行合并
- 不记录到 merged_record.json

**预期结果**：
- 找到 3 个标准化文件
- 成功合并为 `test_merge.mp4`
- 显示输出文件大小

**清理**：
```bash
docker exec social-media-hub-merger-1 rm -f /app/videos/merged/ai_vanvan/test_merge.mp4
docker exec social-media-hub-standardizer-1 rm -rf /app/videos/standardized/ai_vanvan/test
```

---

### 3. 测试完整流程（Standardizer → Merger）

```bash
python test_full_flow.py
```

**功能**：
- 完整测试微服务协作流程
- 自动执行：标准化 → 等待完成 → 合并
- 使用独立的测试文件夹

**预期结果**：
- 步骤 1: Standardizer 成功标准化 3 个视频
- 步骤 2: Merger 成功合并标准化文件
- 生成最终输出文件 `flow_test_output.mp4`

**清理**：
```bash
docker exec social-media-hub-standardizer-1 rm -rf /app/videos/standardized/ai_vanvan/flow_test
docker exec social-media-hub-merger-1 rm -f /app/videos/merged/ai_vanvan/flow_test_output.mp4
```

---

## 查看实时日志

### Standardizer 日志
```bash
docker logs -f social-media-hub-standardizer-1
```

### Merger 日志
```bash
docker logs -f social-media-hub-merger-1
```

### API Gateway 日志
```bash
docker logs -f social-media-hub-api-gateway-1
```

---

## 测试建议

1. **单独测试每个服务**：先确保 Standardizer 和 Merger 各自工作正常
2. **测试完整流程**：验证服务间的协作
3. **查看日志**：每次测试后查看容器日志，了解内部执行情况
4. **及时清理**：测试完成后清理测试文件，避免占用空间

---

## 常见问题

### 1. Standardizer 超时
- 检查容器是否运行：`docker ps`
- 查看日志：`docker logs social-media-hub-standardizer-1`
- 队列可能积压，重启容器：`docker-compose restart standardizer`

### 2. 找不到标准化文件
- 确认 Standardizer 测试成功完成
- 检查文件夹：`docker exec social-media-hub-standardizer-1 ls -lh /app/videos/standardized/ai_vanvan/test/`

### 3. 合并失败
- 检查 FFmpeg 是否安装：`docker exec social-media-hub-merger-1 ffmpeg -version`
- 查看详细错误日志

---

## 测试覆盖

✅ **Standardizer 服务**
- 接收批量视频列表
- 执行终极标准化（分辨率+音频+参数）
- 异步队列处理
- 输出标准化文件

✅ **Merger 服务**
- 读取标准化文件
- 使用 FFmpeg concat 合并
- 生成最终输出

✅ **完整流程**
- 服务间通信
- 异步等待机制
- 端到端数据流
