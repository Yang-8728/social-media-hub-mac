# API Gateway 详解

## 1. 什么是 API Gateway？

API Gateway（API 网关）是微服务架构中的**统一入口点**。

### 类比
```
【传统方式 - 直接访问】
客户 → 会计部门
客户 → 人事部门  
客户 → IT部门

【微服务架构 - 通过 API Gateway】
客户 → 前台（API Gateway） → 会计部门
客户 → 前台（API Gateway） → 人事部门
客户 → 前台（API Gateway） → IT部门
```

## 2. 路由（Routing）概念

**路由** = 根据请求的 URL 路径，决定转发到哪个服务

### 你的项目中的路由表

| 客户端请求 | API Gateway路由 | 转发到哪个服务 | 作用 |
|-----------|----------------|--------------|------|
| `POST /login` | `@app.route('/login')` | auth-service | 登录认证 |
| `POST /download` | `@app.route('/download')` | downloader | 下载视频 |
| `POST /standardize-batch` | `@app.route('/standardize-batch')` | standardizer:8000 | 视频标准化 |
| `POST /merge` | `@app.route('/merge')` | merger:8000 | 合并视频 |
| `GET /merge/status/:account` | `@app.route('/merge/status/<account>')` | merger:8000 | 查询状态 |

## 3. 工作流程图

```
┌─────────────┐
│   客户端     │  (你的浏览器/Postman/Python脚本)
│  localhost  │
└──────┬──────┘
       │ ① 发送请求
       │ POST http://localhost:8080/standardize-batch
       ↓
┌─────────────────────────────────────────────────────┐
│            API Gateway (端口 8080)                   │
│  ┌─────────────────────────────────────────────┐   │
│  │  路由表（app.py）                             │   │
│  │  @app.route('/standardize-batch')           │   │
│  │  → 识别请求路径                               │   │
│  │  → 转发到 standardizer 服务                   │   │
│  └─────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────┘
               │ ② 内部转发
               │ requests.post('http://standardizer:8000/process-batch')
               ↓
┌─────────────────────────────────────────────────────┐
│        Standardizer Service (端口 8000)             │
│  ┌─────────────────────────────────────────────┐   │
│  │  接收任务                                     │   │
│  │  → 标准化视频                                 │   │
│  │  → 返回结果                                   │   │
│  └─────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────┘
               │ ③ 返回响应
               ↓
┌─────────────────────────────────────────────────────┐
│            API Gateway (端口 8080)                   │
│  接收 standardizer 响应 → 转发给客户端               │
└──────────────┬──────────────────────────────────────┘
               │ ④ 最终响应
               ↓
┌─────────────┐
│   客户端     │  收到: {"message": "Batch process task started"}
└─────────────┘
```

## 4. 代码示例解析

### 示例 1: `/standardize-batch` 路由

```python
@app.route('/standardize-batch', methods=['POST'])
def start_standardize_batch():
    """启动批量标准化任务"""
    data = request.get_json()  # ① 接收客户端的 JSON 数据
    
    try:
        # ② 转发到 standardizer 服务
        response = requests.post(
            'http://standardizer:8000/process-batch',  # 目标服务地址
            json=data,  # 传递数据
            timeout=10  # 超时设置
        )
        
        # ③ 检查响应
        if response.status_code == 200:
            return jsonify(response.json())  # 成功：返回 standardizer 的响应
        else:
            return jsonify({'error': f'Standardizer service error'}), 500
            
    except requests.exceptions.RequestException as e:
        # ④ 异常处理
        return jsonify({'error': f'Failed to connect: {e}'}), 500
```

**分解步骤：**
1. 客户端发送: `POST http://localhost:8080/standardize-batch`
2. API Gateway 识别路由: `/standardize-batch`
3. 执行 `start_standardize_batch()` 函数
4. 函数内部转发到: `http://standardizer:8000/process-batch`
5. 等待 standardizer 响应
6. 将响应返回给客户端

### 示例 2: `/merge` 路由

```python
@app.route('/merge', methods=['POST'])
def start_merge():
    data = request.get_json()
    account_name = data.get('account')
    limit = data.get('limit', None)
    
    # 转发到 merger 服务
    response = requests.post('http://merger:8000/merge', json={
        'account': account_name,
        'limit': limit
    })
    
    return jsonify(response.json())
```

**流程：**
```
客户端 → API Gateway → Merger Service
POST /merge     转发到     http://merger:8000/merge
```

## 5. 为什么要用 API Gateway？

### ✅ 优点

#### 1. **统一入口**
```
【没有 API Gateway】
客户端需要知道所有服务的地址:
- http://standardizer:8000/process-batch
- http://merger:8000/merge
- http://downloader:8000/download

【有 API Gateway】
客户端只需要知道一个地址:
- http://localhost:8080/standardize-batch
- http://localhost:8080/merge
- http://localhost:8080/download
```

#### 2. **服务隔离**
- 客户端不需要知道内部服务的 IP 和端口
- 可以随时修改后端服务地址，不影响客户端

#### 3. **统一处理**
```python
# API Gateway 可以统一处理:
- 认证/授权: 检查用户是否有权限
- 日志记录: 记录所有请求
- 限流: 防止服务过载
- 错误处理: 统一的错误格式
```

#### 4. **负载均衡**
```python
# API Gateway 可以分发请求到多个实例
if standardizer_1_busy:
    forward_to(standardizer_2)
else:
    forward_to(standardizer_1)
```

## 6. 你的项目架构

```
外部访问 (localhost:8080)
    ↓
┌─────────────────────────────────────────┐
│       API Gateway (端口 8080)            │
│  - 接收所有外部请求                       │
│  - 路由到对应的微服务                     │
└─────────────────────────────────────────┘
    ↓         ↓         ↓         ↓
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│ Auth │  │Down- │  │Stand-│  │Merger│
│      │  │loader│  │ardiz │  │      │
│ :8000│  │ :8000│  │er    │  │ :8000│
│      │  │      │  │ :8000│  │      │
└──────┘  └──────┘  └──────┘  └──────┘

内部网络 (Docker network: social-media-hub_default)
```

## 7. Docker 网络中的服务名

### 为什么用 `http://standardizer:8000` 而不是 IP？

在 Docker Compose 中，服务可以通过**服务名**互相访问：

```yaml
# docker-compose.yml
services:
  api-gateway:
    ports:
      - "8080:8000"  # 外部:内部
  
  standardizer:
    # 没有 ports，只能内部访问
  
  merger:
    # 没有 ports，只能内部访问
```

**DNS 解析：**
- `standardizer` → Docker 自动解析为 standardizer 容器的 IP
- `merger` → Docker 自动解析为 merger 容器的 IP

## 8. 测试示例

### PowerShell 测试
```powershell
# 客户端只需要访问 API Gateway
$body = @{
    account = "ai_vanvan"
    video_files = @("video1.mp4", "video2.mp4")
    output_folder = "/app/output"
    process_type = "ultimate"
} | ConvertTo-Json

# 统一入口: localhost:8080
Invoke-RestMethod -Uri "http://localhost:8080/standardize-batch" `
    -Method Post `
    -Body $body `
    -ContentType "application/json"
```

### API Gateway 自动转发
```python
# API Gateway 内部代码自动处理
requests.post(
    'http://standardizer:8000/process-batch',  # 内部服务名
    json=data
)
```

## 9. 路由添加流程

当你需要添加新功能时：

1. **修改 API Gateway**
```python
# containers/api-gateway/app.py

@app.route('/new-feature', methods=['POST'])
def new_feature():
    data = request.get_json()
    
    # 转发到对应服务
    response = requests.post('http://new-service:8000/process', json=data)
    
    return jsonify(response.json())
```

2. **重新构建和启动**
```bash
docker-compose build api-gateway
docker-compose up -d api-gateway
```

3. **测试新路由**
```powershell
Invoke-RestMethod -Uri "http://localhost:8080/new-feature" -Method Post
```

## 10. 总结

| 概念 | 解释 | 例子 |
|------|------|------|
| **API Gateway** | 统一入口，转发请求 | 前台接待员 |
| **路由** | 请求路径 → 服务映射 | `/merge` → merger服务 |
| **转发** | 将请求发送到后端服务 | `requests.post('http://merger:8000')` |
| **服务名** | Docker 内部 DNS | `standardizer` = 容器 IP |
| **端口映射** | 外部:内部 | `8080:8000` |

**简单记忆：**
- **路由** = 决定"去哪里"
- **API Gateway** = "前台"，负责接待和转发
- **服务名** = Docker 内部的"电话簿"
