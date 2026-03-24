# Biliup 上传服务 API 文档

## 概述
所有操作通过 HTTP API 完成，无需本地 Python 脚本。适用于本地开发和云端部署（华为云 CCE）。

---

## 1. 自动编号上传视频

**接口**: `POST /api/biliup/upload`

**自动编号模式**（推荐）:
```bash
curl -X POST http://localhost:8080/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/videos/ai_vanvan/merged_20251104.mp4",
    "auto_number": true
  }'
```

**响应**:
```json
{
  "status": "success",
  "task": {
    "account": "ai_vanvan",
    "video_path": "/videos/ai_vanvan/merged_20251104.mp4",
    "title": "ins海外离大谱#125",
    "tid": 138,
    "tag": "Instagram,搞笑,离大谱,海外,沙雕"
  }
}
```

**手动指定模式**:
```bash
curl -X POST http://localhost:8080/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/videos/ai_vanvan/test.mp4",
    "title": "测试视频",
    "tid": 138,
    "tag": "测试"
  }'
```

---

## 2. 查询当前编号

**接口**: `GET /api/biliup/counter`

```bash
curl http://localhost:8080/api/biliup/counter
```

**响应**:
```json
{
  "account": "ai_vanvan",
  "current_number": 124
}
```
> 下次上传将使用 #125

---

## 3. 设置编号

**接口**: `POST /api/biliup/counter`

**用途**: 测试后删除视频，需要回退编号

```bash
curl -X POST http://localhost:8080/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'
```

**响应**:
```json
{
  "status": "success",
  "account": "ai_vanvan",
  "value": 124
}
```

---

## 4. 重置编号

**接口**: `DELETE /api/biliup/counter`

```bash
curl -X DELETE http://localhost:8080/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"account": "ai_vanvan"}'
```

---

## 测试工作流程

### 场景: 上传3个测试视频，测试后删除

```bash
# 1️⃣ 设置起始编号
curl -X POST http://localhost:8080/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'

# 2️⃣ 上传测试视频（自动 #125, #126, #127）
curl -X POST http://localhost:8080/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/videos/ai_vanvan/test1.mp4", "auto_number": true}'

curl -X POST http://localhost:8080/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/videos/ai_vanvan/test2.mp4", "auto_number": true}'

curl -X POST http://localhost:8080/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/videos/ai_vanvan/test3.mp4", "auto_number": true}'

# 3️⃣ 在B站删除测试视频

# 4️⃣ 回退计数器到124，下次正式上传从#125开始
curl -X POST http://localhost:8080/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'

# 5️⃣ 验证计数器
curl http://localhost:8080/api/biliup/counter
# 输出: {"current_number": 124} ✅
```

---

## 云端使用（华为云 CCE）

### 通过公网访问
```bash
# 假设你的 CCE 集群暴露在公网 IP 或域名
curl -X POST http://your-domain.com/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/videos/ai_vanvan/video.mp4",
    "auto_number": true
  }'
```

### 通过 kubectl port-forward（临时测试）
```bash
# 在本地映射到云端 API Gateway
kubectl port-forward svc/api-gateway 8080:8000

# 然后使用 localhost 访问
curl -X POST http://localhost:8080/api/biliup/upload ...
```

### 通过云端定时任务（CronJob）
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-upload
spec:
  schedule: "0 2 * * *"  # 每天凌晨2点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: uploader
            image: curlimages/curl
            command:
            - /bin/sh
            - -c
            - |
              curl -X POST http://api-gateway:8000/api/biliup/upload \
                -H "Content-Type: application/json" \
                -d '{"video_path": "/videos/ai_vanvan/daily.mp4", "auto_number": true}'
          restartPolicy: OnFailure
```

---

## 数据持久化

- **存储位置**: Redis (`ai_vanvan:video_counter`)
- **持久化**: Redis 需要配置 AOF 或 RDB
- **容器重启**: 计数器不丢失（只要 Redis 数据卷挂载正确）

### CCE 配置示例
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  template:
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        volumeMounts:
        - name: data
          mountPath: /data
        command:
        - redis-server
        - --appendonly yes  # 启用 AOF 持久化
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: redis-data
```

---

## 注意事项

1. **删除视频后需手动调整计数器**  
   程序无法自动检测B站视频删除，测试完需手动回退

2. **并发安全**  
   Redis `INCR` 是原子操作，支持并发上传不会重复编号

3. **多账号支持**  
   默认 `ai_vanvan`，可传入 `"account": "other_account"` 使用不同计数器

4. **云端认证**  
   生产环境建议添加 API Token 认证（当前未实现）
