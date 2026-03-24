# 微服务测试命令

## 1. 测试 Standardizer 服务

### 使用 curl (推荐)
```bash
curl -X POST http://localhost:8080/standardize-batch \
  -H "Content-Type: application/json" \
  -d '{
    "account": "ai_vanvan",
    "video_files": [
      "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_17-51-15_UTC.mp4",
      "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_00-02-09_UTC.mp4",
      "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-12_23-07-00_UTC.mp4"
    ],
    "output_folder": "/app/videos/standardized/ai_vanvan/test",
    "process_type": "ultimate"
  }'
```

### 使用 PowerShell
```powershell
$body = @{
    account = "ai_vanvan"
    video_files = @(
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_17-51-15_UTC.mp4",
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_00-02-09_UTC.mp4",
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-12_23-07-00_UTC.mp4"
    )
    output_folder = "/app/videos/standardized/ai_vanvan/test"
    process_type = "ultimate"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/standardize-batch" -Method Post -Body $body -ContentType "application/json"
```

### 查看标准化进度
```bash
# 查看 Standardizer 日志
docker logs -f social-media-hub-standardizer-1

# 检查输出文件
docker exec social-media-hub-standardizer-1 ls -lh /app/videos/standardized/ai_vanvan/test/
```

---

## 2. 测试 Merger 服务

### 触发合并任务
```powershell
$body = @{
    account = "ai_vanvan"
    limit = 3
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/merge" -Method Post -Body $body -ContentType "application/json"
```

### 查看合并状态
```powershell
Invoke-RestMethod -Uri "http://localhost:8080/merge/status/ai_vanvan" -Method Get
```

### 查看合并日志
```bash
docker logs -f social-media-hub-merger-1
```

---

## 3. 完整流程测试（手动）

### 步骤 1: 标准化 3 个视频
```powershell
$body = @{
    account = "ai_vanvan"
    video_files = @(
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_17-51-15_UTC.mp4",
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_00-02-09_UTC.mp4",
        "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-12_23-07-00_UTC.mp4"
    )
    output_folder = "/app/videos/standardized/ai_vanvan/manual_test"
    process_type = "ultimate"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/standardize-batch" -Method Post -Body $body -ContentType "application/json"
```

### 步骤 2: 等待完成（查看文件）
```bash
# 每隔几秒检查一次
docker exec social-media-hub-standardizer-1 ls /app/videos/standardized/ai_vanvan/manual_test/ | grep .mp4 | wc -l
```

### 步骤 3: 手动合并（在容器内）
```bash
docker exec -it social-media-hub-merger-1 bash

# 在容器内执行
cd /app/videos/standardized/ai_vanvan/manual_test
ls -lh *.mp4

# 创建 concat 文件
cat > /tmp/manual_concat.txt << EOF
file '/app/videos/standardized/ai_vanvan/manual_test/2025-10-12_23-07-00_UTC_ultimate.mp4'
file '/app/videos/standardized/ai_vanvan/manual_test/2025-10-13_00-02-09_UTC_ultimate.mp4'
file '/app/videos/standardized/ai_vanvan/manual_test/2025-10-13_17-51-15_UTC_ultimate.mp4'
EOF

# FFmpeg 合并
ffmpeg -f concat -safe 0 -i /tmp/manual_concat.txt -c copy -y /app/videos/merged/ai_vanvan/manual_test.mp4

# 检查结果
ls -lh /app/videos/merged/ai_vanvan/manual_test.mp4
```

---

## 4. Postman 测试集合

### Collection: Social Media Hub API

#### 1. Standardize Batch
- **Method**: POST
- **URL**: `http://localhost:8080/standardize-batch`
- **Headers**: 
  - Content-Type: application/json
- **Body** (raw JSON):
```json
{
  "account": "ai_vanvan",
  "video_files": [
    "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_17-51-15_UTC.mp4",
    "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_00-02-09_UTC.mp4",
    "/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-12_23-07-00_UTC.mp4"
  ],
  "output_folder": "/app/videos/standardized/ai_vanvan/test",
  "process_type": "ultimate"
}
```

#### 2. Merge Videos
- **Method**: POST
- **URL**: `http://localhost:8080/merge`
- **Headers**: 
  - Content-Type: application/json
- **Body** (raw JSON):
```json
{
  "account": "ai_vanvan",
  "limit": 3
}
```

#### 3. Get Merge Status
- **Method**: GET
- **URL**: `http://localhost:8080/merge/status/ai_vanvan`

---

## 5. 快速测试命令

### 一键标准化测试
```powershell
# 标准化
Invoke-RestMethod -Uri "http://localhost:8080/standardize-batch" -Method Post -Body (@{account="ai_vanvan";video_files=@("/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_17-51-15_UTC.mp4","/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-13_00-02-09_UTC.mp4","/app/videos/downloads/ai_vanvan/2025-10-14/2025-10-12_23-07-00_UTC.mp4");output_folder="/app/videos/standardized/ai_vanvan/test";process_type="ultimate"} | ConvertTo-Json) -ContentType "application/json"

# 查看进度
docker logs --tail 20 social-media-hub-standardizer-1
```

### 一键合并测试
```powershell
# 合并
Invoke-RestMethod -Uri "http://localhost:8080/merge" -Method Post -Body (@{account="ai_vanvan";limit=3} | ConvertTo-Json) -ContentType "application/json"

# 查看进度
docker logs --tail 20 social-media-hub-merger-1
```

---

## 6. 检查和清理

### 检查文件
```bash
# 标准化文件
docker exec social-media-hub-standardizer-1 ls -lh /app/videos/standardized/ai_vanvan/test/

# 合并文件
docker exec social-media-hub-merger-1 ls -lh /app/videos/merged/ai_vanvan/
```

### 清理测试文件
```bash
# 清理标准化文件
docker exec social-media-hub-standardizer-1 rm -rf /app/videos/standardized/ai_vanvan/test

# 清理合并文件
docker exec social-media-hub-merger-1 rm -f /app/videos/merged/ai_vanvan/test_*.mp4
docker exec social-media-hub-merger-1 rm -f /app/videos/merged/ai_vanvan/manual_test.mp4
```

---

## 优势对比

| 方式 | 优点 | 缺点 |
|------|------|------|
| **PowerShell/curl** | 快速、直接、可复制 | 需要手动检查结果 |
| **Postman** | 图形界面、保存请求、团队共享 | 需要安装软件 |
| **Python脚本** | 自动化、包含验证逻辑 | 需要维护代码 |

建议：
- 🎯 **快速测试** → PowerShell/curl
- 📊 **调试开发** → Postman
- 🤖 **自动化测试** → Python脚本
