# 华为云 CCE 部署和使用指南

## 部署后的完整工作流（无需 Python 脚本）

### 1. 通过云端负载均衡器访问

```bash
# 假设你的 CCE 配置了 LoadBalancer，获得公网 IP：123.45.67.89

# 查询编号
curl http://123.45.67.89/api/biliup/counter

# 设置编号
curl -X POST http://123.45.67.89/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'

# 上传视频（自动编号）
curl -X POST http://123.45.67.89/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/videos/ai_vanvan/merged_20251104.mp4", "auto_number": true}'
```

### 2. 通过 kubectl port-forward（临时调试）

```bash
# 在本地电脑上映射云端 API Gateway
kubectl port-forward svc/api-gateway 8080:8000 -n social-media-hub

# 然后使用本地访问（和开发环境一样）
curl http://localhost:8080/api/biliup/counter
```

### 3. 在云端 Pod 内部执行

```bash
# 进入任意一个 Pod
kubectl exec -it deployment/api-gateway -n social-media-hub -- sh

# 在容器内执行
apk add curl  # 如果需要
curl http://api-gateway:8000/api/biliup/counter
```

### 4. 配置定时任务（K8s CronJob）

```yaml
# cronjob-daily-upload.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-video-upload
  namespace: social-media-hub
spec:
  schedule: "0 2 * * *"  # 每天凌晨2点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: uploader
            image: curlimages/curl:latest
            command:
            - /bin/sh
            - -c
            - |
              echo "开始每日上传..."
              
              # 调用 merge API 合并昨天的视频
              curl -X POST http://api-gateway:8000/api/merger/merge \
                -H "Content-Type: application/json" \
                -d '{"account": "ai_vanvan", "limit": 15}'
              
              echo "等待合并完成..."
              sleep 60
              
              # 查找最新合并的视频
              LATEST_VIDEO=$(ls -t /videos/merged/ai_vanvan/*.mp4 | head -1)
              
              # 自动编号上传
              curl -X POST http://api-gateway:8000/api/biliup/upload \
                -H "Content-Type: application/json" \
                -d "{\"video_path\": \"$LATEST_VIDEO\", \"auto_number\": true}"
              
              echo "上传任务已提交"
          restartPolicy: OnFailure
          volumeMounts:
          - name: videos
            mountPath: /videos
          volumes:
          - name: videos
            persistentVolumeClaim:
              claimName: video-storage
```

部署定时任务：
```bash
kubectl apply -f cronjob-daily-upload.yaml
```

---

## CCE 部署架构

```
                         ┌─────────────────┐
                         │ 华为云 LoadBalancer │
                         │ (公网 IP)           │
                         └────────┬────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
            ┌───────▼────────┐          ┌───────▼────────┐
            │  API Gateway   │          │  API Gateway   │
            │  (Pod 1)       │          │  (Pod 2)       │
            └───────┬────────┘          └───────┬────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                         ┌────────▼────────┐
                         │  Redis Service  │
                         │  (计数器存储)    │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  Redis Pod      │
                         │  + PVC (持久卷) │
                         └─────────────────┘
```

### 关键配置

#### 1. Redis 持久化存储
```yaml
# redis-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: social-media-hub
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: csi-disk  # 华为云云硬盘
```

#### 2. API Gateway Service (LoadBalancer)
```yaml
# api-gateway-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: social-media-hub
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  selector:
    app: api-gateway
  # 华为云 ELB 配置
  annotations:
    kubernetes.io/elb.class: union
    kubernetes.io/elb.autocreate: '{"type":"public","bandwidth_name":"cce-bandwidth","bandwidth_chargemode":"traffic","bandwidth_size":5,"bandwidth_sharetype":"PER","eip_type":"5_bgp"}'
```

---

## 完整测试流程（CCE 环境）

### 部署后验证

```bash
# 1. 获取 LoadBalancer 公网 IP
kubectl get svc api-gateway -n social-media-hub
# 输出：EXTERNAL-IP: 123.45.67.89

# 2. 设置环境变量
export API_ENDPOINT=http://123.45.67.89

# 3. 测试 API
curl $API_ENDPOINT/api/biliup/counter

# 4. 设置起始编号
curl -X POST $API_ENDPOINT/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'

# 5. 触发下载
curl -X POST $API_ENDPOINT/api/downloader/download \
  -H "Content-Type: application/json" \
  -d '{"account": "ai_vanvan", "limit": 5}'

# 6. 等待下载完成，触发合并
curl -X POST $API_ENDPOINT/api/merger/merge \
  -H "Content-Type: application/json" \
  -d '{"account": "ai_vanvan", "limit": 15}'

# 7. 上传（自动编号为 #125）
curl -X POST $API_ENDPOINT/api/biliup/upload \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/videos/ai_vanvan/ins海外离大谱#125.mp4", "auto_number": true}'

# 8. 在B站删除测试视频后，回退计数器
curl -X POST $API_ENDPOINT/api/biliup/counter \
  -H "Content-Type: application/json" \
  -d '{"value": 124}'
```

---

## 监控和日志

### 查看上传任务日志
```bash
# 查看 biliup worker 日志
kubectl logs -f deployment/biliup-uploader -n social-media-hub

# 查看 API Gateway 日志
kubectl logs -f deployment/api-gateway -n social-media-hub

# 查看 Redis 计数器
kubectl exec -it deployment/redis -n social-media-hub -- redis-cli
> GET ai_vanvan:video_counter
"124"
```

---

## 优势总结

✅ **真正的云原生**: 所有操作通过 HTTP API，无需 SSH 到服务器  
✅ **无状态服务**: API Gateway 可水平扩展（多副本）  
✅ **持久化存储**: Redis 数据在 PVC 中，Pod 重启不丢失  
✅ **自动化**: 可配置 CronJob 定时执行  
✅ **可观测**: 通过 kubectl logs 查看所有日志  
✅ **灵活管理**: 随时通过 API 调整计数器，无需修改代码  

❌ **不需要**:
- ❌ SSH 登录服务器
- ❌ 运行本地 Python 脚本
- ❌ 手动进入容器执行命令
