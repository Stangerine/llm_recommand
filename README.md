# 基于大模型的个性化商品推荐系统

使用 Qwen2.5-3B + RQ-VAE 的工业科学用品推荐系统。

## 数据说明

本项目使用 Amazon Reviews - Industrial & Scientific 数据集：

| 文件 | 记录数 | 大小 | 说明 |
|------|--------|------|------|
| `products.jsonl` | 165,686 | 128.7 MB | 商品信息（ASIN、标题、描述、品牌、价格等） |
| `user_interactions.jsonl` | 28,096 | 4.0 MB | 用户行为序列（平均长度 7.5） |
| `sid_mapping.json` | 165,686 | 6.8 MB | ASIN ↔ SID 映射（60,203 个唯一 SID） |

## 快速开始

### 方式一：一键启动（推荐）

**Linux/Mac:**
```bash
chmod +x scripts/start_dev.sh
./scripts/start_dev.sh
```

**Windows:**
```bash
scripts\start_dev.bat
```

### 方式二：手动启动

#### 1. 验证数据
```bash
python scripts/validate_data.py
```

#### 2. 启动后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 启动服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. 启动前端
```bash
cd frontend
npm install
npm run dev  # 启动开发服务器 :5173
```
init
### 方式三：Docker 启动

```bash
docker-compose up -d
```

## 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | React 应用 |
| 后端 API | http://localhost:8000 | FastAPI 服务 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | 服务状态 |
| 系统指标 | http://localhost:8000/metrics | 监控数据 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/recommend` | 个性化推荐 |
| GET | `/api/v1/products/{asin}` | 商品详情 |
| GET | `/api/v1/products/search` | 商品搜索 |
| POST | `/api/v1/behavior` | 行为上报 |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | 系统指标 |

### 推荐接口示例

**Request:**
```json
POST /api/v1/recommend
{
  "user_id": "demo_user",
  "history_asins": ["0176496920", "0692782109", "0781776848"],
  "top_k": 10
}
```

**Response:**
```json
{
  "user_id": "demo_user",
  "recommendations": [
    {
      "asin": "...",
      "title": "...",
      "description": "...",
      "category": "Industrial & Scientific > ...",
      "brand": "...",
      "price": 29.99,
      "rating": 4.5,
      "rating_count": 100
    }
  ],
  "total": 10,
  "model_version": "qwen2.5-3b-sft-grpo-v1"
}
```

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── api/                    # API 路由和 Schema
│   ├── config/                 # 配置管理
│   ├── data/                   # 数据处理
│   │   ├── raw/                # 原始数据（JSONL）
│   │   ├── processed/          # 处理后数据
│   │   └── scripts/            # 数据处理脚本
│   ├── elasticsearch/          # ES 客户端和索引
│   ├── models/                 # 模型推理
│   ├── services/               # 业务逻辑
│   └── tests/                  # 测试
├── frontend/                   # React 前端
│   └── src/
│       ├── api/                # API 调用
│       ├── components/         # UI 组件
│       ├── hooks/              # 自定义 Hooks
│       ├── pages/              # 页面
│       ├── store/              # 状态管理
│       └── utils/              # 工具函数
├── nginx/                      # Nginx 配置
└── scripts/                    # 脚本工具
    ├── validate_data.py        # 数据验证
    ├── start_dev.sh/bat        # 开发环境启动
    ├── init_backend.sh         # 后端初始化
    └── health_check.sh         # 健康检查
```

## 测试

```bash
# 后端测试
cd backend
pytest tests/unit/ -v
pytest tests/integration/ -v

# 前端测试
cd frontend
npm run test
```

## 技术栈

- **后端**: FastAPI, Elasticsearch 8.x, Redis 7.x, Transformers + PEFT
- **前端**: React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query
- **部署**: Docker, Nginx
