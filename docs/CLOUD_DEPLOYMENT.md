# 云端全流程部署指南

##  架构说明

**本地环境**: 保持原样，使用Selenium上传
**云端环境**: 完整自动化流程，使用biliup-rs上传

```
云端流程: downloader  standardizer  merger  biliup-uploader
          (下载)      (标准化)      (合并)   (上传B站)
```

##  云端部署步骤

### 1. 首次准备 (本地执行一次)

#### 下载biliup-rs
```powershell
# 访问GitHub下载
https://github.com/biliup/biliup-rs/releases/tag/v0.2.4
# 下载: biliup-x86_64-pc-windows-msvc.zip
# 解压并添加到PATH
```

#### 登录获取Cookie
```powershell
python login_biliup.py ai_vanvan
```

按提示扫码登录，Cookie会保存到 `config/ai_vanvan.json`

### 2. 云端服务器配置

#### 上传项目到服务器
```bash
# 将整个项目上传到云端
scp -r social-media-hub/ user@server:/path/to/
```

#### 上传Cookie文件
```bash
# 将本地Cookie上传到云端config目录
scp config/ai_vanvan.json user@server:/path/to/social-media-hub/config/
```

### 3. 启动云端服务

```bash
cd /path/to/social-media-hub

# 使用云端配置启动
docker-compose -f docker-compose.cloud.yml up -d

# 查看日志
docker-compose -f docker-compose.cloud.yml logs -f
```

### 4. 触发任务 (三种方式)

#### 方式1: API触发
```bash
curl -X POST http://server:8080/download \
  -H "Content-Type: application/json" \
  -d '{"account": "ai_vanvan"}'
```

#### 方式2: Redis直接发送
```python
import redis
import json

r = redis.from_url("redis://server:6379")
task = {
    "account": "ai_vanvan",
    "profile_url": "instagram_profile_url"
}
r.rpush("download_queue", json.dumps(task))
```

#### 方式3: 定时任务
```bash
# 在crontab中添加
0 */6 * * * cd /path/to/social-media-hub && python trigger_download.py
```

##  各容器说明

| 容器 | 功能 | 队列 |
|------|------|------|
| downloader | Instagram下载 | download_queue  standardize_queue |
| standardizer | 视频标准化 | standardize_queue  merge_queue |
| merger | 视频合并 | merge_queue  upload_queue |
| biliup-uploader | B站上传 | upload_queue   |

##  Cookie维护

Cookie约30天有效期，需定期刷新:

### 本地刷新
```powershell
# 刷新Cookie
biliup -u config/ai_vanvan.json renew
```

### 同步到云端
```bash
# 上传新Cookie
scp config/ai_vanvan.json user@server:/path/to/social-media-hub/config/

# 重启上传容器
docker-compose -f docker-compose.cloud.yml restart biliup-uploader
```

##  监控命令

```bash
# 查看所有容器状态
docker-compose -f docker-compose.cloud.yml ps

# 查看队列长度
docker exec social-media-hub-redis-1 redis-cli LLEN upload_queue

# 查看上传器日志
docker logs -f --tail 100 social-media-hub-biliup-uploader-1

# 查看所有容器日志
docker-compose -f docker-compose.cloud.yml logs --tail 50
```

##  完整示例流程

```bash
# 1. 启动所有服务
docker-compose -f docker-compose.cloud.yml up -d

# 2. 发送下载任务
curl -X POST http://localhost:8080/download \
  -d '{"account": "ai_vanvan"}'

# 3. 观察各阶段
# 下载阶段
docker logs -f social-media-hub-downloader-1

# 标准化阶段
docker logs -f social-media-hub-standardizer-1

# 合并阶段
docker logs -f social-media-hub-merger-1

# 上传阶段
docker logs -f social-media-hub-biliup-uploader-1
```

##  注意事项

1. **Cookie安全**: config目录包含敏感信息，不要提交到Git
2. **网络**: 云端需要能访问Instagram和B站
3. **存储**: 确保有足够空间存储视频（建议100GB+）
4. **内存**: biliup-uploader约需200MB内存
5. **定期检查**: 建议每周检查一次Cookie有效性

##  故障排查

### 上传失败
```bash
# 1. 检查Cookie
docker exec social-media-hub-biliup-uploader-1 cat /app/cookies/ai_vanvan.json

# 2. 手动测试上传
docker exec -it social-media-hub-biliup-uploader-1 biliup --version

# 3. 查看详细日志
docker logs --since 1h social-media-hub-biliup-uploader-1
```

### 队列积压
```bash
# 查看各队列长度
for queue in download_queue standardize_queue merge_queue upload_queue; do
  echo "$queue: $(docker exec social-media-hub-redis-1 redis-cli LLEN $queue)"
done
```

##  性能优化

### 并发处理
如果视频量大，可以增加容器副本:

```yaml
# docker-compose.cloud.yml
services:
  biliup-uploader:
    deploy:
      replicas: 3  # 3个上传器并发
```

### 资源限制
```yaml
biliup-uploader:
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: '0.5'
```

##  部署检查清单

- [ ] biliup-rs已下载并测试
- [ ] Cookie已获取并验证
- [ ] config/ai_vanvan.json已上传到云端
- [ ] docker-compose.cloud.yml已配置
- [ ] 所有容器成功启动
- [ ] Redis队列可以正常通信
- [ ] 测试视频上传成功
- [ ] 设置了Cookie刷新提醒(日历)
