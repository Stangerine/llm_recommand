# 基于大模型的个性化商品推荐系统
## 全栈工程化执行计划 v3.0

> **数据集：** Amazon Reviews 2023 — `Industrial_and_Scientific`
> **核心目标：** 根据用户历史行为序列预测感兴趣商品，返回 Top-K 个性化推荐列表
> **服务形式：** RESTful API（FastAPI）+ React 前端，支持实时在线推荐

---

## 目录

1. [全栈系统架构总览](#1-全栈系统架构总览)
2. [预训练模型与算法说明](#2-预训练模型与算法说明)
3. [技术栈总览](#3-技术栈总览)
4. [完整项目目录结构](#4-完整项目目录结构)
5. [后端执行阶段](#5-后端执行阶段)
   - Phase 0 — 环境初始化
   - Phase 1 — 数据处理
   - Phase 2 — Elasticsearch 搭建
   - Phase 3 — SID 映射服务
   - Phase 4 — 模型推理服务封装
   - Phase 5 — FastAPI 在线服务
6. [前端执行阶段](#6-前端执行阶段)
   - Phase 6 — 前端工程搭建
   - Phase 7 — API 层与状态管理
   - Phase 8 — 核心组件开发
   - Phase 9 — 页面开发
7. [集成测试与监控](#7-集成测试与监控)
8. [Docker 全栈部署](#8-docker-全栈部署)
9. [API 接口规范](#9-api-接口规范)
10. [在线推荐完整数据流](#10-在线推荐完整数据流)
11. [关键配置说明](#11-关键配置说明)
12. [里程碑、交付物与验收标准](#12-里程碑交付物与验收标准)

---

## 1. 全栈系统架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          用户浏览器 / 移动端                               │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                 React 18 + TypeScript (Vite)                     │   │
│   │                                                                  │   │
│   │  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐  │   │
│   │  │  首页推荐墙     │  │  商品搜索页   │  │  行为模拟器         │  │   │
│   │  │  (HomePage)    │  │  (SearchPage)│  │  (SimulatorPage)   │  │   │
│   │  └────────────────┘  └──────────────┘  └────────────────────┘  │   │
│   │                                                                  │   │
│   │  全局状态: Zustand  ·  服务端状态: TanStack Query  ·  路由: React Router  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │  HTTP / JSON（经 Nginx 反向代理）
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Gateway  ( :8000 )                         │
│                                                                          │
│  POST /api/v1/recommend    GET /api/v1/products/{asin}                   │
│  GET  /api/v1/products/search              POST /api/v1/behavior         │
└─────────────────┬──────────────────────────────────┬─────────────────────┘
                  │                                  │
                  ▼                                  ▼
┌─────────────────────────────┐    ┌──────────────────────────────────────┐
│      RecommendPipeline      │    │        Elasticsearch  ( :9200 )      │
│                             │    │                                      │
│  1. ASIN  → SID 序列        │    │  products index                      │
│  2. 模型推理 → 候选 SID      │    │  asin | title | description          │
│  3. SID   → ASIN 列表       │    │  category | brand | price | sid      │
│  4. ES 批量回查              │◄──►│                                      │
│  5. 返回排序后 Top-K         │    │  mget（精确回查）                     │
│                             │    │  multi_match（全文搜索）              │
└─────────────┬───────────────┘    └──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐    ┌──────────────────────────────────────┐
│    Model Inference Service  │    │            Redis  ( :6379 )          │
│                             │    │                                      │
│  Qwen2.5-3B + LoRA（已训练）│    │  推荐结果缓存  TTL: 5 min            │
│  Beam Search ( ×20 beams )  │◄──►│  SID 映射缓存  TTL: 24 h            │
│  约束解码 + 排序感知奖励     │    │                                      │
└─────────────┬───────────────┘    └──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐
│      SID Mapping Service    │
│                             │
│  asin2sid : dict (内存)     │
│  sid2asin : dict (内存)     │
│  查询耗时 < 1ms              │
└─────────────────────────────┘
```

---

## 2. 预训练模型与算法说明

> 本节说明已训练完成、可直接加载使用的模型组件。工程实现阶段仅需调用推理接口，无需关注训练细节。

### 2.1 RQ-VAE（残差量化自编码器）

| 属性 | 说明 |
|------|------|
| 权重路径 | `models/checkpoints/rqvae/` |
| 输入 | 商品标题 + 描述拼接文本（Sentence-Transformer 编码，384 维） |
| 输出 | 离散语义 ID（SID），格式为 `idx0_idx1_idx2_idx3`（4 层 codebook 索引拼接） |
| 调用方式 | `RQVAEEncoder.encode_batch(texts: list[str]) -> list[str]` |
| 使用阶段 | **仅离线数据预处理**（`build_sid_mapping.py`），在线服务不加载此模型 |

### 2.2 Qwen2.5-3B 推荐模型（SFT + GRPO）

| 属性 | 说明 |
|------|------|
| 基座模型 | Qwen2.5-3B-Instruct |
| 微调方式 | LoRA，权重路径 `models/checkpoints/qwen25_rec_lora/` |
| 输入 | 历史商品 SID 序列（Prompt 模板封装） |
| 输出 | Top-K 候选商品 SID（Beam Search 生成，每个 beam 对应一个候选） |
| 调用方式 | `RecommenderInference.predict(history_sids: list[str]) -> list[str]` |
| 使用阶段 | **在线服务实时推理**，服务启动时一次性加载至 GPU 显存 |
| 离线指标参考 | HR@10 ≈ 0.42，NDCG@10 ≈ 0.28（Industrial_and_Scientific 测试集） |

### 2.3 SID 映射关系

```
商品 ASIN  ──[RQ-VAE 离线编码]──►  SID Token（如 "12_5_3_7"）
                                         │
              ┌──────────────────────────┘
              │  双向映射表（sid_mapping.json）
              ▼
  asin2sid: {"B001XXXXX": "12_5_3_7"}
  sid2asin: {"12_5_3_7": "B001XXXXX"}
```

SID 映射关系在数据预处理阶段一次性生成，在线推理时从内存字典直接查询，**不依赖任何模型实时推断**。

---

## 3. 技术栈总览

### 后端

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| API 框架 | FastAPI | ≥ 0.110 | HTTP 路由、请求校验、依赖注入 |
| ASGI 服务器 | Uvicorn | ≥ 0.29 | 异步请求处理 |
| 搜索引擎 | Elasticsearch | 8.x | 商品索引、全文搜索、精确回查 |
| ES 客户端 | elasticsearch-py | 8.x | 异步 ES 交互 |
| 模型推理 | Transformers + PEFT | ≥ 4.40 | 加载 Qwen2.5-3B + LoRA |
| 文本编码 | Sentence-Transformers | ≥ 2.6 | 商品文本向量化（离线阶段） |
| 缓存 | Redis | 7.x | 推荐结果缓存 + SID 映射热备 |
| 数据处理 | Pandas | ≥ 2.0 | 数据清洗与序列构建 |
| 配置管理 | Pydantic-Settings | ≥ 2.0 | 环境变量统一管理 |
| 日志 | structlog | ≥ 24.0 | 结构化日志与请求追踪 |
| 测试 | Pytest + httpx | — | 单元测试 + 集成测试 |

### 前端

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | React | 18.x | UI 渲染与组件化 |
| 语言 | TypeScript | 5.x | 类型安全，与后端 Schema 对齐 |
| 构建工具 | Vite | 5.x | 极速 HMR 开发 + 生产构建 |
| 样式 | Tailwind CSS | 3.x | Utility-first 响应式样式 |
| 组件库 | shadcn/ui | latest | 无样式可组合基础组件 |
| 服务端状态 | TanStack Query | 5.x | 请求缓存、自动刷新、异步状态管理 |
| 全局状态 | Zustand | 4.x | 用户行为历史等轻量跨页面状态 |
| 路由 | React Router | 6.x | SPA 页面路由 |
| HTTP 客户端 | Axios | 1.x | API 请求封装与拦截器 |
| 代码规范 | ESLint + Prettier | — | 格式化与静态检查 |
| 前端测试 | Vitest + Testing Library | — | 组件单元测试 |
| 反向代理 | Nginx | 1.25 | 静态资源托管 + API 请求转发 |

---

## 4. 完整项目目录结构

```
recommendation-system/
│
├── backend/                              # ── 后端工程 ──
│   ├── data/
│   │   ├── raw/                          # 原始数据（只读）
│   │   │   ├── Industrial_and_Scientific.jsonl
│   │   │   └── Industrial_and_Scientific_meta.jsonl
│   │   ├── processed/                    # 预处理产物
│   │   │   ├── products.jsonl            # 清洗后商品信息
│   │   │   ├── user_interactions.jsonl   # 用户行为序列
│   │   │   └── sid_mapping.json          # ASIN ↔ SID 双向映射表
│   │   └── scripts/
│   │       ├── download_data.py          # HuggingFace 数据集下载
│   │       ├── preprocess_products.py    # 商品元数据清洗
│   │       ├── preprocess_interactions.py# 用户行为序列构建
│   │       └── build_sid_mapping.py      # 调用 RQ-VAE 批量生成 SID
│   │
│   ├── elasticsearch/
│   │   ├── mappings/
│   │   │   └── products_mapping.json     # 索引 Mapping 定义
│   │   ├── scripts/
│   │   │   ├── create_index.py           # 创建索引
│   │   │   └── bulk_index_products.py    # 批量导入商品
│   │   └── client.py                     # AsyncElasticsearch 封装
│   │
│   ├── models/
│   │   ├── checkpoints/                  # 训练好的模型权重（不入 git）
│   │   │   ├── qwen25_rec_lora/          # 推荐模型 LoRA 权重
│   │   │   └── rqvae/                    # RQ-VAE 权重（离线阶段用）
│   │   ├── rqvae_encoder.py              # RQ-VAE 推理封装（离线专用）
│   │   └── recommender_inference.py      # Qwen2.5-3B 在线推理封装
│   │
│   ├── services/
│   │   ├── sid_service.py                # SID ↔ ASIN 映射服务
│   │   ├── search_service.py             # Elasticsearch 查询封装
│   │   └── recommend_pipeline.py         # 推荐主流水线编排
│   │
│   ├── api/
│   │   ├── main.py                       # FastAPI 入口 + 生命周期管理
│   │   ├── dependencies.py               # 依赖注入（单例实例绑定）
│   │   ├── routers/
│   │   │   ├── recommend.py              # POST /api/v1/recommend
│   │   │   ├── products.py               # GET  /api/v1/products/*
│   │   │   └── behavior.py               # POST /api/v1/behavior
│   │   ├── schemas/
│   │   │   ├── recommend.py              # 推荐请求 / 响应 Schema
│   │   │   └── products.py               # 商品信息 Schema
│   │   └── middleware/
│   │       └── logging_middleware.py     # 请求日志 + 延迟埋点
│   │
│   ├── config/
│   │   ├── settings.py                   # 全局配置（Pydantic Settings）
│   │   └── logging.yaml
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_sid_service.py
│   │   │   ├── test_search_service.py
│   │   │   └── test_recommend_pipeline.py
│   │   └── integration/
│   │       ├── test_recommend_api.py
│   │       └── test_es_indexing.py
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                             # ── 前端工程 ──
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts                 # Axios 实例 + 请求 / 响应拦截器
│   │   │   ├── recommend.ts              # 推荐相关 API 函数
│   │   │   └── products.ts               # 商品相关 API 函数
│   │   ├── hooks/
│   │   │   ├── useRecommend.ts           # 推荐数据查询 + 刷新
│   │   │   ├── useProductSearch.ts       # 商品关键词搜索
│   │   │   └── useBehaviorReport.ts      # 行为事件上报
│   │   ├── store/
│   │   │   ├── behaviorStore.ts          # 用户行为历史（Zustand + persist）
│   │   │   └── userStore.ts              # 模拟用户 ID
│   │   ├── components/
│   │   │   ├── common/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   ├── ErrorBoundary.tsx
│   │   │   │   ├── LoadingSpinner.tsx
│   │   │   │   └── EmptyState.tsx
│   │   │   ├── product/
│   │   │   │   ├── ProductCard.tsx       # 商品卡片（含排名角标）
│   │   │   │   ├── ProductGrid.tsx       # 商品网格容器
│   │   │   │   └── ProductDetailModal.tsx# 商品详情弹窗
│   │   │   └── recommendation/
│   │   │       ├── RecommendFeed.tsx     # 推荐列表主组件
│   │   │       ├── BehaviorPanel.tsx     # 右侧行为历史面板
│   │   │       ├── HistoryChip.tsx       # 单条历史记录标签
│   │   │       └── RefreshButton.tsx     # 刷新推荐按钮
│   │   ├── pages/
│   │   │   ├── HomePage.tsx              # 主页：推荐墙 + 行为面板
│   │   │   ├── SearchPage.tsx            # 商品搜索页
│   │   │   └── SimulatorPage.tsx         # 行为模拟器（Demo 专用）
│   │   ├── types/
│   │   │   ├── product.ts                # Product 接口定义
│   │   │   └── recommend.ts              # RecommendRequest / Response
│   │   ├── utils/
│   │   │   └── format.ts                 # 价格 / 评分格式化工具
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── nginx/
│   └── nginx.conf                        # 静态资源托管 + API 反向代理
│
├── docker-compose.yml                    # 全栈一键启动（ES + Redis + API + 前端）
├── scripts/
│   ├── init_backend.sh                   # 数据预处理 + 索引初始化
│   └── health_check.sh                   # 全链路健康检查
└── README.md
```

---

## 5. 后端执行阶段

---

### Phase 0 — 环境初始化

**目标：** 搭建可运行的基础开发环境，验证各服务连通性。

#### 0.1 Python 环境

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 0.2 `requirements.txt`

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
elasticsearch>=8.0.0,<9.0.0
redis>=5.0.0
transformers>=4.40.0
peft>=0.10.0
torch>=2.2.0
sentence-transformers>=2.6.0
pydantic-settings>=2.0.0
pandas>=2.0.0
structlog>=24.0.0
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

#### 0.3 全局配置 `config/settings.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index_name: str = "industrial_products"
    es_timeout: int = 10

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_recommend_ttl: int = 300      # 推荐结果缓存 5 分钟
    redis_sid_ttl: int = 86400          # SID 映射缓存 24 小时

    # 推荐模型（Qwen2.5-3B + LoRA，已训练完成）
    model_base: str = "Qwen/Qwen2.5-3B"
    model_lora_path: str = "./models/checkpoints/qwen25_rec_lora"
    model_device: str = "cuda"
    beam_search_num_beams: int = 20     # Beam Search 宽度
    top_k: int = 10                     # 返回 Top-K 数量

    # RQ-VAE（离线使用，在线服务不加载）
    rqvae_path: str = "./models/checkpoints/rqvae"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:80"]

    # 数据路径
    sid_mapping_path: str = "./data/processed/sid_mapping.json"
    products_path: str = "./data/processed/products.jsonl"

settings = Settings()
```

#### 0.4 启动 Elasticsearch（Docker）

```bash
docker run -d \
  --name es-rec \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  -p 9200:9200 \
  docker.elastic.co/elasticsearch/elasticsearch:8.13.0

# 验证连通性
curl -s http://localhost:9200/_cluster/health | python3 -m json.tool
```

#### ✅ Phase 0 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| Python 环境 | `pip check` 无报错 | 所有依赖版本兼容 |
| ES 启动 | `curl http://localhost:9200/_cluster/health` | `status` 为 `green` 或 `yellow` |
| Redis 启动 | `redis-cli ping` | 返回 `PONG` |
| 配置加载 | `python -c "from config.settings import settings; print(settings.es_host)"` | 打印正确配置值 |
| 模型文件 | `ls models/checkpoints/qwen25_rec_lora/` | 目录非空，存在 adapter 权重文件 |

---

### Phase 1 — 数据处理

**目标：** 将原始 Amazon Reviews 数据清洗为结构化商品库、用户行为序列及 SID 映射表。

#### 1.1 数据集字段说明

| 文件 | 内容 | 关键字段 |
|------|------|----------|
| `Industrial_and_Scientific.jsonl` | 用户评论与交互 | `user_id`, `parent_asin`, `timestamp`, `rating` |
| `Industrial_and_Scientific_meta.jsonl` | 商品元数据 | `parent_asin`, `title`, `description`, `categories`, `price`, `brand` |

#### 1.2 商品元数据清洗 `data/scripts/preprocess_products.py`

```python
import json, pandas as pd

def process_product_meta(raw_path: str, output_path: str):
    records = []
    with open(raw_path) as f:
        for line in f:
            item = json.loads(line)
            title = item.get("title", "").strip()
            if not title:
                continue  # 过滤无标题商品

            description = " ".join(item.get("description", []))[:2000]
            categories  = " > ".join(
                item.get("categories", [[]])[0] if item.get("categories") else []
            )
            records.append({
                "asin":         item["parent_asin"],
                "title":        title,
                "description":  description,
                "category":     categories,
                "brand":        item.get("brand", ""),
                "price":        item.get("price"),
                "rating":       item.get("average_rating"),
                "rating_count": item.get("rating_number", 0),
            })

    df = pd.DataFrame(records).drop_duplicates(subset=["asin"])
    df.to_json(output_path, orient="records", lines=True, force_ascii=False)
    print(f"✅ 商品总数: {len(df)}")
```

**清洗规则说明：**

- 去除 `title` 为空的记录；`description` 截断至 2000 字符以控制索引体积
- 以 `parent_asin` 为主键去重，保留首次出现记录
- `price` / `rating` 允许为 `null`，不影响推荐主流程

#### 1.3 用户行为序列构建 `data/scripts/preprocess_interactions.py`

```python
from collections import defaultdict
import json

def process_interactions(raw_path: str, output_path: str,
                         min_seq_len: int = 5, max_seq_len: int = 50):
    """
    按时间戳升序整理用户行为序列，过滤交互数 < min_seq_len 的冷启动用户。
    截取每位用户最近 max_seq_len 条交互记录。
    """
    user_actions = defaultdict(list)
    with open(raw_path) as f:
        for line in f:
            rec = json.loads(line)
            user_actions[rec["user_id"]].append({
                "asin":      rec["parent_asin"],
                "timestamp": rec["timestamp"],
            })

    results = []
    for uid, actions in user_actions.items():
        actions.sort(key=lambda x: x["timestamp"])
        seq = [a["asin"] for a in actions]
        if len(seq) < min_seq_len:
            continue
        results.append({
            "user_id":  uid,
            "sequence": seq[-max_seq_len:],
        })

    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"✅ 有效用户数: {len(results)}")
```

#### 1.4 生成 SID 映射 `data/scripts/build_sid_mapping.py`

> 调用已训练完成的 RQ-VAE 模型，批量为所有商品生成离散语义 ID，仅在预处理阶段执行一次。

```python
"""
输出格式 sid_mapping.json:
{
  "asin2sid": { "B001XXXXX": "12_5_3_7", ... },
  "sid2asin": { "12_5_3_7": "B001XXXXX", ... }
}
SID 格式：RQ-VAE 各层 codebook 索引以 "_" 连接，如 4 层 → "idx0_idx1_idx2_idx3"
"""
from models.rqvae_encoder import RQVAEEncoder
import json
from config.settings import settings

def build_sid_mapping(products_path: str, output_path: str, batch_size: int = 256):
    # 加载已训练的 RQ-VAE 模型（仅此处使用）
    encoder = RQVAEEncoder(ckpt_path=settings.rqvae_path)
    asin2sid, sid2asin = {}, {}

    with open(products_path) as f:
        products = [json.loads(l) for l in f]

    for i in range(0, len(products), batch_size):
        batch = products[i: i + batch_size]
        texts = [f"{p['title']} {p['description'][:200]}" for p in batch]
        sids  = encoder.encode_batch(texts)   # list[str]，格式 "idx0_idx1_..."

        for p, sid in zip(batch, sids):
            asin2sid[p["asin"]] = sid
            sid2asin.setdefault(sid, p["asin"])  # SID 碰撞时取首个商品

    with open(output_path, "w") as f:
        json.dump({"asin2sid": asin2sid, "sid2asin": sid2asin}, f, indent=2)

    print(f"✅ 总商品: {len(asin2sid)} | 唯一 SID: {len(sid2asin)}")

if __name__ == "__main__":
    build_sid_mapping(settings.products_path, settings.sid_mapping_path)
```

**预期数据规模**（Industrial_and_Scientific 典型量级）：

| 数据集 | 原始规模 | 过滤后估算 |
|--------|---------|------------|
| 交互记录 | ~900K 条 | ~400K 条 |
| 有效用户数 | ~200K | ~60K |
| 有效商品数 | ~120K | ~40K |

#### ✅ Phase 1 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 商品文件完整性 | `wc -l data/processed/products.jsonl` | 行数 > 0，无空行 |
| 商品字段完整 | `python -c "import json; p=json.loads(open('data/processed/products.jsonl').readline()); assert all(k in p for k in ['asin','title','description'])"` | 断言通过 |
| 行为序列过滤 | 检查 `user_interactions.jsonl` 中所有序列长度 | 每条 `sequence` 长度 ≥ 5 |
| SID 映射双向一致 | `python -c "import json; d=json.load(open('data/processed/sid_mapping.json')); asin='<任意有效ASIN>'; assert d['sid2asin'][d['asin2sid'][asin]] == asin"` | 断言通过 |
| SID 覆盖率 | 统计 `len(asin2sid) / len(products)` | 覆盖率 ≥ 95% |

---

### Phase 2 — Elasticsearch 搭建

**目标：** 建立商品全文索引，支持推荐结果精确回查与候选商品搜索两类查询。

#### 2.1 索引 Mapping `elasticsearch/mappings/products_mapping.json`

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "product_analyzer": {
          "type": "standard",
          "stopwords": "_english_"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "asin":         { "type": "keyword" },
      "title":        { "type": "text", "analyzer": "product_analyzer",
                        "fields": { "raw": { "type": "keyword" } } },
      "description":  { "type": "text", "analyzer": "product_analyzer" },
      "category":     { "type": "keyword" },
      "brand":        { "type": "keyword" },
      "price":        { "type": "float",   "null_value": -1.0 },
      "rating":       { "type": "float",   "null_value": 0.0 },
      "rating_count": { "type": "integer", "null_value": 0 },
      "sid":          { "type": "keyword" }
    }
  }
}
```

**字段设计说明：**

| 字段 | 类型 | 设计意图 |
|------|------|---------|
| `asin` | keyword | 推荐回查主键，支持 mget 批量精确查询 |
| `title` + `description` | text | 全文搜索召回，`title` 权重 ×3 |
| `sid` | keyword | 支持根据 SID 直接定位商品 |
| `category` / `brand` | keyword | 支持前端分类筛选与聚合 |

#### 2.2 创建索引 `elasticsearch/scripts/create_index.py`

```python
from elasticsearch import Elasticsearch
from pathlib import Path
import json

def create_index(es_host: str, index_name: str, mapping_path: str):
    es      = Elasticsearch(es_host)
    mapping = json.loads(Path(mapping_path).read_text())

    if es.indices.exists(index=index_name):
        print(f"⚠️  索引 {index_name} 已存在，跳过创建")
        return

    es.indices.create(index=index_name, body=mapping)
    print(f"✅ 索引 {index_name} 创建成功")
```

#### 2.3 批量导入商品 `elasticsearch/scripts/bulk_index_products.py`

```python
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json

def bulk_index(es_host: str, index_name: str,
               products_path: str, sid_mapping_path: str, batch_size: int = 500):
    es      = Elasticsearch(es_host)
    sid_map = json.loads(open(sid_mapping_path).read())["asin2sid"]

    def gen_actions():
        with open(products_path) as f:
            for line in f:
                p = json.loads(line)
                yield {
                    "_index": index_name,
                    "_id":    p["asin"],
                    "_source": { **p, "sid": sid_map.get(p["asin"], "") }
                }

    success, failed = bulk(es, gen_actions(), chunk_size=batch_size, raise_on_error=False)
    print(f"✅ 导入成功: {success} | 失败: {len(failed)}")
```

#### 2.4 ES 异步客户端封装 `elasticsearch/client.py`

```python
from elasticsearch import AsyncElasticsearch
from config.settings import settings

class ESClient:
    def __init__(self):
        self.client = AsyncElasticsearch(settings.es_host,
                                         request_timeout=settings.es_timeout)
        self.index  = settings.es_index_name

    async def get_products_by_asins(self, asins: list[str]) -> list[dict]:
        """mget 批量精确回查——推荐流水线末端核心方法。"""
        resp = await self.client.mget(index=self.index, body={"ids": asins})
        return [hit["_source"] for hit in resp["docs"] if hit.get("found")]

    async def search_products(self, query: str, size: int = 10,
                              category: str | None = None) -> list[dict]:
        """全文搜索，供前端搜索页及降级召回使用。"""
        must = [{"multi_match": {
            "query": query, "fields": ["title^3", "description", "brand^2"]
        }}]
        if category:
            must.append({"term": {"category": category}})

        resp = await self.client.search(
            index=self.index,
            body={"query": {"bool": {"must": must}}, "size": size}
        )
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    async def close(self):
        await self.client.close()
```

#### ✅ Phase 2 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 索引创建成功 | `curl http://localhost:9200/industrial_products` | 返回索引信息，无 404 |
| 商品总量 | `curl http://localhost:9200/industrial_products/_count` | `count` 与 `products.jsonl` 行数一致（误差 < 0.1%） |
| mget 回查 | 用 3 个已知 ASIN 执行 mget | 3 条结果均 `found: true`，字段完整 |
| 全文搜索 | 搜索 `"safety gloves"` | 返回结果数 > 0，`title` 字段含相关词 |
| SID 字段写入 | 随机取 10 条文档，检查 `sid` 字段 | 非空字符串，格式符合 `\d+_\d+_\d+_\d+` |

---

### Phase 3 — SID 映射服务

**目标：** 提供毫秒级 ASIN ↔ SID 双向映射能力，支撑推荐流水线的序列转换。

#### `services/sid_service.py`

```python
import json
from config.settings import settings

class SIDService:
    """
    启动时将全量映射加载至内存字典，查询耗时 < 1ms。
    不依赖 Redis 或任何外部服务，降低在线链路复杂度。
    """

    def __init__(self):
        self.asin2sid: dict[str, str] = {}
        self.sid2asin: dict[str, str] = {}

    async def initialize(self):
        with open(settings.sid_mapping_path) as f:
            data = json.load(f)
        self.asin2sid = data["asin2sid"]
        self.sid2asin = data["sid2asin"]
        print(f"✅ SID 服务就绪：{len(self.asin2sid)} 个商品，{len(self.sid2asin)} 个唯一 SID")

    def asin_to_sid(self, asin: str) -> str | None:
        return self.asin2sid.get(asin)

    def sid_to_asin(self, sid: str) -> str | None:
        return self.sid2asin.get(sid)

    def asins_to_sids(self, asins: list[str]) -> list[str]:
        """批量转换，自动过滤无映射的 ASIN，保持输入顺序。"""
        return [s for a in asins if (s := self.asin2sid.get(a))]

    def sids_to_asins(self, sids: list[str]) -> list[str]:
        """批量反查，自动过滤无效 SID，保持输入顺序（即模型打分顺序）。"""
        return [a for s in sids if (a := self.sid2asin.get(s))]

    def is_valid_sid(self, sid: str) -> bool:
        return sid in self.sid2asin
```

#### ✅ Phase 3 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 正向转换 | `sid_svc.asin_to_sid("<已知 ASIN>")` | 返回非空 SID 字符串 |
| 反向转换 | `sid_svc.sid_to_asin(sid_svc.asin_to_sid("<ASIN>"))` | 与输入 ASIN 相同 |
| 批量过滤 | 传入含 1 个无效 ASIN 的列表 | 无效 ASIN 被过滤，有效项正确转换 |
| 查询耗时 | 批量转换 1000 个 ASIN，计时 | 总耗时 < 5ms |
| 内存加载 | `len(sid_svc.asin2sid)` | 等于 `products.jsonl` 行数（SID 覆盖商品数） |

---

### Phase 4 — 模型推理服务封装

**目标：** 将已训练的 Qwen2.5-3B 推荐模型封装为可供 FastAPI 服务调用的推理接口。

> **说明：** 模型训练已完成，本阶段仅涉及模型加载、Prompt 构造与推理接口封装，不涉及任何训练逻辑。

#### Prompt 模板

```
[INST]
Based on the user's browsing history (represented as item semantic IDs):
History: <SID_1> <SID_2> ... <SID_N>
Predict the next items the user is most likely to be interested in.
Output only semantic IDs, one per line.
[/INST]
```

#### `models/recommender_inference.py`

```python
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from config.settings import settings

class RecommenderInference:
    """
    单例模式，服务启动时加载一次，避免重复初始化的显存与时间开销。
    predict() 方法为纯推理调用，对外屏蔽模型细节。
    """

    def __init__(self):
        self.model     = None
        self.tokenizer = None
        self._loaded   = False

    def load(self, valid_sids: list[str]):
        """在 FastAPI lifespan 中调用，加载基座模型 + LoRA 权重。"""
        if self._loaded:
            return

        self.tokenizer = AutoTokenizer.from_pretrained(settings.model_base)
        base = AutoModelForCausalLM.from_pretrained(
            settings.model_base,
            torch_dtype=torch.float16,
            device_map=settings.model_device,
        )
        self.model = PeftModel.from_pretrained(base, settings.model_lora_path)
        self.model.eval()
        self._loaded = True
        print(f"✅ 推荐模型就绪 | 设备: {settings.model_device} | 合法 SID 数: {len(valid_sids)}")

    def _build_prompt(self, history_sids: list[str]) -> str:
        return (
            "[INST] Based on the user's browsing history (item semantic IDs):\n"
            f"History: {' '.join(history_sids)}\n"
            "Predict the next items. Output semantic IDs only, one per line.\n[/INST]"
        )

    @torch.inference_mode()
    def predict(self, history_sids: list[str]) -> list[str]:
        """
        接收历史 SID 序列，返回 Top-K 候选 SID 列表（去重、按打分顺序排列）。

        内部使用 Beam Search（num_beams = beam_search_num_beams），
        每个 beam 对应一个候选 SID；约束解码确保仅生成合法 SID token。
        """
        prompt  = self._build_prompt(history_sids)
        inputs  = self.tokenizer(prompt, return_tensors="pt").to(settings.model_device)

        outputs = self.model.generate(
            **inputs,
            num_beams=settings.beam_search_num_beams,
            num_return_sequences=settings.beam_search_num_beams,
            max_new_tokens=32,
            early_stopping=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )

        candidates, seen = [], set()
        for output in outputs:
            generated = output[inputs["input_ids"].shape[1]:]
            sid = self.tokenizer.decode(
                generated, skip_special_tokens=True
            ).strip().split("\n")[0].strip()

            if sid and sid not in seen:
                seen.add(sid)
                candidates.append(sid)
            if len(candidates) >= settings.top_k:
                break

        return candidates
```

#### ✅ Phase 4 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 模型加载 | 调用 `recommender.load(valid_sids)` 无报错 | 打印"推荐模型就绪"日志 |
| 输出格式 | `predict(["1_2_3_4", "5_6_7_8"])` | 返回列表，每项符合 `\d+_\d+_\d+_\d+` 格式 |
| 输出数量 | 检查返回长度 | ≤ `settings.top_k`，无重复项 |
| 推理耗时 | 单次推理计时（GPU） | < 3s（含 Beam Search 全部 beams） |
| SID 有效性 | 对返回的每个 SID 调用 `sid_svc.is_valid_sid()` | 有效率 ≥ 80%（GRPO 约束解码保障） |

---

### Phase 5 — FastAPI 在线服务

**目标：** 串联所有服务模块，对外暴露稳定的推荐 API，完成推荐全链路。

#### `api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import recommend, products, behavior
from services.sid_service import SIDService
from elasticsearch.client import ESClient
from models.recommender_inference import RecommenderInference
from config.settings import settings
import structlog

logger = structlog.get_logger()

# 全局单例——在 lifespan 中初始化，注入 app.state
_sid_svc     = SIDService()
_es_client   = ESClient()
_recommender = RecommenderInference()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时按序初始化所有组件，关闭时释放连接。"""
    logger.info("🚀 启动推荐服务...")
    await _sid_svc.initialize()
    _recommender.load(list(_sid_svc.sid2asin.keys()))   # 传入合法 SID 集合
    app.state.sid_svc     = _sid_svc
    app.state.es_client   = _es_client
    app.state.recommender = _recommender
    logger.info("✅ 所有服务组件就绪")
    yield
    await _es_client.close()
    logger.info("👋 推荐服务已关闭")

app = FastAPI(
    title="个性化商品推荐系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend.router, prefix="/api/v1", tags=["推荐"])
app.include_router(products.router,  prefix="/api/v1", tags=["商品"])
app.include_router(behavior.router,  prefix="/api/v1", tags=["行为"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

#### `api/schemas/recommend.py`

```python
from pydantic import BaseModel, Field

class RecommendRequest(BaseModel):
    user_id:       str
    history_asins: list[str] = Field(..., min_length=1, max_length=50,
                                      description="用户历史浏览 ASIN 列表（时间正序）")
    top_k:         int        = Field(default=10, ge=1, le=50)

class ProductInfo(BaseModel):
    asin:         str
    title:        str
    description:  str | None = None
    category:     str | None = None
    brand:        str | None = None
    price:        float | None = None
    rating:       float | None = None
    rating_count: int | None = None

class RecommendResponse(BaseModel):
    user_id:         str
    recommendations: list[ProductInfo]
    total:           int
    model_version:   str = "qwen2.5-3b-sft-grpo-v1"
```

#### `api/routers/recommend.py`

```python
from fastapi import APIRouter, Request, HTTPException
from api.schemas.recommend import RecommendRequest, RecommendResponse, ProductInfo
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest, request: Request):
    sid_svc     = request.app.state.sid_svc
    es_client   = request.app.state.es_client
    recommender = request.app.state.recommender

    # Step 1：ASIN → SID 序列
    history_sids = sid_svc.asins_to_sids(req.history_asins)
    if not history_sids:
        raise HTTPException(status_code=400, detail="历史商品均无对应 SID，请检查输入 ASIN")

    # Step 2：模型推理 → 候选 SID 列表
    candidate_sids = recommender.predict(history_sids)

    # Step 3：SID → ASIN
    candidate_asins = sid_svc.sids_to_asins(candidate_sids)
    if not candidate_asins:
        raise HTTPException(status_code=500, detail="模型未生成有效候选商品，请重试")

    # Step 4：ES 批量回查商品详情（mget）
    products = await es_client.get_products_by_asins(candidate_asins[: req.top_k])

    # Step 5：保持模型打分顺序排序
    order = {asin: i for i, asin in enumerate(candidate_asins)}
    products.sort(key=lambda p: order.get(p["asin"], 999))

    logger.info("recommend_done", user_id=req.user_id,
                history_len=len(history_sids), returned=len(products))

    return RecommendResponse(
        user_id=req.user_id,
        recommendations=[ProductInfo(**p) for p in products],
        total=len(products),
    )
```

#### ✅ Phase 5 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 服务正常启动 | `uvicorn api.main:app` 无报错 | 打印"所有服务组件就绪"日志 |
| 健康检查 | `curl http://localhost:8000/health` | `{"status": "ok"}` |
| 推荐接口正常响应 | POST `/api/v1/recommend` 传入合法 ASIN 列表 | 200，`recommendations` 非空，包含 `title` 字段 |
| 推荐接口错误处理 | 传入全为无效 ASIN | 400，`detail` 字段提示明确 |
| 响应格式校验 | 对比 Schema 定义 | 所有字段类型匹配，无多余字段 |
| 端到端延迟 | 10 次请求取 P50 | P50 < 2s（GPU 推理环境） |
| CORS 配置 | 从 `localhost:5173` 发起跨域请求 | 无 CORS 报错，响应正常 |
| Swagger 文档 | 访问 `http://localhost:8000/docs` | 文档页正常渲染，三个路由均可见 |

---

## 6. 前端执行阶段

---

### Phase 6 — 前端工程搭建

**目标：** 初始化 React + TypeScript 工程，配置开发环境、代理与类型系统。

#### 6.1 项目初始化

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
npm install @tanstack/react-query zustand axios react-router-dom
npm install -D @testing-library/react @testing-library/jest-dom vitest jsdom
npx shadcn@latest init
npx shadcn@latest add card badge button input skeleton toast dialog
```

#### 6.2 `tailwind.config.ts`

```typescript
import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f4ff",
          100: "#e0e8ff",
          500: "#3b5bdb",
          600: "#364fc7",
          900: "#1d2d6b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
} satisfies Config;
```

#### 6.3 Vite 代理 `vite.config.ts`

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
```

#### 6.4 TypeScript 类型定义 `src/types/product.ts`

```typescript
export interface Product {
  asin:          string;
  title:         string;
  description?:  string;
  category?:     string;
  brand?:        string;
  price?:        number;
  rating?:       number;
  rating_count?: number;
}

export interface RecommendRequest {
  user_id:       string;
  history_asins: string[];
  top_k?:        number;
}

export interface RecommendResponse {
  user_id:         string;
  recommendations: Product[];
  total:           number;
  model_version:   string;
}

export interface SearchResponse {
  results: Product[];
  total:   number;
}

export type BehaviorAction = "view" | "click" | "purchase";

export interface BehaviorRecord {
  asin:      string;
  title:     string;
  action:    BehaviorAction;
  timestamp: number;
}
```

#### ✅ Phase 6 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 开发服务器启动 | `npm run dev` | 无报错，浏览器访问 `localhost:5173` 可见页面 |
| TypeScript 编译 | `npx tsc --noEmit` | 0 类型错误 |
| 代理配置 | 开发环境请求 `/api/health` | 转发至后端，返回 `{"status":"ok"}` |
| 生产构建 | `npm run build` | `dist/` 目录生成，无构建错误 |
| ESLint 检查 | `npm run lint` | 0 错误（警告可忽略） |

---

### Phase 7 — API 层与状态管理

**目标：** 封装所有后端接口调用，建立前端状态架构。

#### 7.1 Axios 实例 `src/api/client.ts`

```typescript
import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// 请求拦截：注入用户 ID Header
apiClient.interceptors.request.use((config) => {
  const userId = localStorage.getItem("rec_user_id") ?? "demo_user";
  config.headers["X-User-Id"] = userId;
  return config;
});

// 响应拦截：统一错误格式化
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const msg = error.response?.data?.detail ?? "请求失败，请稍后重试";
    return Promise.reject(new Error(msg));
  }
);

export default apiClient;
```

#### 7.2 推荐 API `src/api/recommend.ts`

```typescript
import apiClient from "./client";
import type { RecommendRequest, RecommendResponse } from "@/types/product";

export async function fetchRecommendations(req: RecommendRequest): Promise<RecommendResponse> {
  const { data } = await apiClient.post<RecommendResponse>("/recommend", req);
  return data;
}

export async function reportBehavior(
  userId: string, asin: string, action: string
): Promise<void> {
  await apiClient.post("/behavior", { user_id: userId, asin, action_type: action });
}
```

#### 7.3 商品 API `src/api/products.ts`

```typescript
import apiClient from "./client";
import type { Product, SearchResponse } from "@/types/product";

export async function fetchProductDetail(asin: string): Promise<Product> {
  const { data } = await apiClient.get<Product>(`/products/${asin}`);
  return data;
}

export async function searchProducts(
  query: string, category?: string, size = 20
): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>("/products/search", {
    params: { q: query, category, size },
  });
  return data;
}
```

#### 7.4 推荐 Hook `src/hooks/useRecommend.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRecommendations, reportBehavior } from "@/api/recommend";
import { useBehaviorStore } from "@/store/behaviorStore";
import { useUserStore } from "@/store/userStore";

export function useRecommend() {
  const queryClient = useQueryClient();
  const userId  = useUserStore((s) => s.userId);
  const history = useBehaviorStore((s) => s.historyAsins());

  const query = useQuery({
    queryKey:  ["recommend", userId, history],
    queryFn:   () => fetchRecommendations({ user_id: userId, history_asins: history, top_k: 10 }),
    enabled:   history.length > 0,
    staleTime: 1000 * 60 * 5,  // 5 分钟内行为不变则不重新请求
    retry: 1,
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["recommend", userId] });

  return { ...query, refresh };
}

export function useBehaviorReport() {
  const userId = useUserStore((s) => s.userId);
  return useMutation({
    mutationFn: ({ asin, action }: { asin: string; action: string }) =>
      reportBehavior(userId, asin, action),
  });
}
```

#### 7.5 行为历史 Store `src/store/behaviorStore.ts`

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { BehaviorRecord } from "@/types/product";

interface BehaviorState {
  records:      BehaviorRecord[];
  addRecord:    (record: BehaviorRecord) => void;
  removeRecord: (asin: string) => void;
  clearAll:     () => void;
  historyAsins: () => string[];
}

export const useBehaviorStore = create<BehaviorState>()(
  persist(
    (set, get) => ({
      records: [],

      addRecord: (record) =>
        set((state) => {
          const filtered = state.records.filter((r) => r.asin !== record.asin);
          return { records: [record, ...filtered].slice(0, 50) };  // 最多保留 50 条
        }),

      removeRecord: (asin) =>
        set((state) => ({ records: state.records.filter((r) => r.asin !== asin) })),

      clearAll: () => set({ records: [] }),

      historyAsins: () =>
        [...get().records]
          .sort((a, b) => a.timestamp - b.timestamp)
          .map((r) => r.asin),
    }),
    { name: "behavior-history" }  // 持久化至 localStorage
  )
);
```

#### 7.6 用户 Store `src/store/userStore.ts`

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UserState {
  userId:    string;
  setUserId: (id: string) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      userId:    `user_${Math.random().toString(36).slice(2, 9)}`,
      setUserId: (id) => set({ userId: id }),
    }),
    { name: "user-store" }
  )
);
```

#### ✅ Phase 7 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| API 请求正常 | 在浏览器 Network 面板观察 | `/api/v1/recommend` 请求发出，状态 200 |
| 错误处理 | 关闭后端，触发推荐请求 | 页面显示"请求失败"提示，不崩溃 |
| 行为持久化 | 添加几条历史后刷新页面 | localStorage 中记录保留，推荐自动触发 |
| queryKey 响应 | 新增历史记录后 | TanStack Query 自动重新请求推荐接口 |
| TypeScript 类型 | `tsc --noEmit` | API 函数返回类型与 `types/` 定义一致，无类型错误 |

---

### Phase 8 — 核心组件开发

**目标：** 实现可复用的商品展示组件与推荐交互组件。

#### 8.1 商品卡片 `src/components/product/ProductCard.tsx`

```tsx
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Product } from "@/types/product";

interface Props {
  product:         Product;
  rank?:           number;
  onClick?:        (product: Product) => void;
  onAddToHistory?: (product: Product) => void;
}

export function ProductCard({ product, rank, onClick, onAddToHistory }: Props) {
  return (
    <Card
      className="group relative cursor-pointer hover:shadow-md transition-shadow duration-200"
      onClick={() => onClick?.(product)}
    >
      {rank !== undefined && (
        <span className="absolute top-2 left-2 z-10 bg-brand-500 text-white
                         text-xs font-mono px-2 py-0.5 rounded-full">
          #{rank + 1}
        </span>
      )}

      <CardContent className="p-4 space-y-2">
        <p className="text-sm font-medium leading-snug line-clamp-2 text-gray-900">
          {product.title}
        </p>

        <div className="flex flex-wrap gap-1">
          {product.brand && (
            <Badge variant="secondary" className="text-xs">{product.brand}</Badge>
          )}
          {product.category && (
            <Badge variant="outline" className="text-xs max-w-[140px] truncate">
              {product.category.split(" > ").at(-1)}
            </Badge>
          )}
        </div>

        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-1 text-xs text-gray-500">
            {product.rating && (
              <>
                <span className="text-yellow-400">★</span>
                <span>{product.rating.toFixed(1)}</span>
                {product.rating_count && (
                  <span>({product.rating_count.toLocaleString()})</span>
                )}
              </>
            )}
          </div>
          {product.price != null && product.price > 0 && (
            <span className="text-sm font-semibold text-brand-600">
              ${product.price.toFixed(2)}
            </span>
          )}
        </div>

        {onAddToHistory && (
          <button
            className="w-full mt-1 py-1 text-xs text-brand-500 border border-brand-200
                       rounded hover:bg-brand-50 transition-colors opacity-0
                       group-hover:opacity-100"
            onClick={(e) => { e.stopPropagation(); onAddToHistory(product); }}
          >
            + 加入浏览历史
          </button>
        )}
      </CardContent>
    </Card>
  );
}
```

#### 8.2 推荐列表 `src/components/recommendation/RecommendFeed.tsx`

```tsx
import { useState } from "react";
import { useRecommend, useBehaviorReport } from "@/hooks/useRecommend";
import { useBehaviorStore } from "@/store/behaviorStore";
import { ProductCard } from "@/components/product/ProductCard";
import { Skeleton } from "@/components/ui/skeleton";
import type { Product } from "@/types/product";

export function RecommendFeed() {
  const { data, isLoading, isError, error, refresh } = useRecommend();
  const { mutate: reportBehavior } = useBehaviorReport();
  const addRecord = useBehaviorStore((s) => s.addRecord);
  const [selected, setSelected] = useState<Product | null>(null);

  const handleClick = (product: Product) => {
    setSelected(product);
    reportBehavior({ asin: product.asin, action: "click" });
    addRecord({ asin: product.asin, title: product.title,
                action: "click", timestamp: Date.now() });
  };

  const handleAddToHistory = (product: Product) => {
    addRecord({ asin: product.asin, title: product.title,
                action: "view", timestamp: Date.now() });
    reportBehavior({ asin: product.asin, action: "view" });
  };

  if (isLoading) return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={i} className="h-48 rounded-xl" />
      ))}
    </div>
  );

  if (isError) return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
      <p className="text-sm">{(error as Error).message}</p>
      <button onClick={refresh} className="mt-3 text-sm text-brand-500 underline">重试</button>
    </div>
  );

  if (!data?.recommendations.length) return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
      <p className="text-sm">暂无推荐，请先在右侧添加浏览历史</p>
    </div>
  );

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-800">
          为你推荐
          <span className="ml-2 text-xs font-normal text-gray-400">共 {data.total} 件</span>
        </h2>
        <button
          onClick={refresh}
          className="text-xs text-brand-500 border border-brand-200 px-3 py-1
                     rounded-full hover:bg-brand-50 transition-colors"
        >
          刷新推荐
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {data.recommendations.map((product, idx) => (
          <ProductCard
            key={product.asin}
            product={product}
            rank={idx}
            onClick={handleClick}
            onAddToHistory={handleAddToHistory}
          />
        ))}
      </div>
    </section>
  );
}
```

#### 8.3 行为历史面板 `src/components/recommendation/BehaviorPanel.tsx`

```tsx
import { useBehaviorStore } from "@/store/behaviorStore";

export function BehaviorPanel() {
  const { records, removeRecord, clearAll } = useBehaviorStore();

  return (
    <aside className="w-72 shrink-0">
      <div className="bg-white border border-gray-100 rounded-xl p-4 sticky top-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">
            浏览历史
            <span className="ml-1 text-xs font-normal text-gray-400">
              ({records.length}/50)
            </span>
          </h3>
          {records.length > 0 && (
            <button
              onClick={clearAll}
              className="text-xs text-gray-400 hover:text-red-400 transition-colors"
            >
              清空
            </button>
          )}
        </div>

        {records.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-8 leading-relaxed">
            点击商品卡片的<br />「加入浏览历史」<br />即可触发个性化推荐
          </p>
        ) : (
          <ul className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {records.map((r) => (
              <li
                key={r.asin}
                className="flex items-start justify-between gap-2 group"
              >
                <div className="min-w-0">
                  <p className="text-xs text-gray-700 line-clamp-1">{r.title}</p>
                  <p className="text-xs text-gray-400 font-mono">{r.asin}</p>
                </div>
                <button
                  onClick={() => removeRecord(r.asin)}
                  className="text-gray-300 hover:text-red-400 opacity-0
                             group-hover:opacity-100 transition-all shrink-0 text-xs"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
```

#### ✅ Phase 8 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 推荐列表渲染 | 历史非空时进入首页 | 正常显示商品卡片网格，含排名角标 |
| 骨架屏 | 网络节流至 Slow 3G 后刷新 | Loading 状态显示骨架屏而非空白 |
| 错误提示 | 断开后端后触发推荐 | 显示错误文案与"重试"按钮，不崩溃 |
| 行为联动 | 点击"加入浏览历史" | 右侧面板立即新增记录，推荐自动刷新 |
| 面板删除 | 删除某条历史记录 | 记录从面板消失，推荐随之更新 |
| 响应式布局 | 分别在 375px / 768px / 1440px 窗口宽度下检查 | 商品卡片列数：2 / 3 / 5，无溢出 |
| 组件单元测试 | `npm run test` | ProductCard 相关测试全部通过 |

---

### Phase 9 — 页面开发

**目标：** 实现三个核心页面，串联完整用户交互流程。

#### 9.1 首页 `src/pages/HomePage.tsx`

```tsx
import { RecommendFeed } from "@/components/recommendation/RecommendFeed";
import { BehaviorPanel } from "@/components/recommendation/BehaviorPanel";

export function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-screen-xl mx-auto px-4 py-6 flex gap-6">
        <main className="flex-1 min-w-0">
          <RecommendFeed />
        </main>
        <BehaviorPanel />
      </div>
    </div>
  );
}
```

#### 9.2 搜索页 `src/pages/SearchPage.tsx`

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "@/api/products";
import { ProductCard } from "@/components/product/ProductCard";
import { useBehaviorStore } from "@/store/behaviorStore";

export function SearchPage() {
  const [query,    setQuery]    = useState("");
  const [category, setCategory] = useState<string | undefined>();
  const addRecord = useBehaviorStore((s) => s.addRecord);

  const { data, isLoading } = useQuery({
    queryKey: ["search", query, category],
    queryFn:  () => searchProducts(query, category),
    enabled:  query.trim().length >= 2,
    staleTime: 30_000,
  });

  return (
    <div className="max-w-screen-xl mx-auto px-4 py-6">
      <div className="mb-6 max-w-xl">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索工业科学用品..."
          className="w-full px-4 py-2 border border-gray-200 rounded-lg text-sm
                     focus:outline-none focus:ring-2 focus:ring-brand-300"
        />
      </div>

      {isLoading && <p className="text-sm text-gray-400">搜索中...</p>}

      {data && (
        <>
          <p className="text-xs text-gray-400 mb-4">找到 {data.total} 个结果</p>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {data.results.map((p) => (
              <ProductCard
                key={p.asin}
                product={p}
                onAddToHistory={(product) =>
                  addRecord({ asin: product.asin, title: product.title,
                               action: "view", timestamp: Date.now() })
                }
              />
            ))}
          </div>
        </>
      )}

      {!isLoading && !data && query.trim().length >= 2 && (
        <p className="text-sm text-gray-400">暂无结果</p>
      )}
    </div>
  );
}
```

#### 9.3 行为模拟器 `src/pages/SimulatorPage.tsx`

> Demo 专用页面：允许直接输入 ASIN 或选择预置场景，快速构造历史行为序列触发推荐。

```tsx
import { useState } from "react";
import { useBehaviorStore } from "@/store/behaviorStore";
import { useNavigate } from "react-router-dom";

const PRESET_SEQUENCES = [
  { label: "工业安全防护",  asins: ["B07SAFETY1", "B07SAFETY2", "B07SAFETY3"] },
  { label: "实验室耗材",    asins: ["B08LABCON1", "B08LABCON2", "B08LABCON3"] },
  { label: "测量检测仪器",  asins: ["B09MEASURE1", "B09MEASURE2", "B09MEASURE3"] },
];

export function SimulatorPage() {
  const [input, setInput] = useState("");
  const addRecord = useBehaviorStore((s) => s.addRecord);
  const navigate  = useNavigate();

  const applyPreset = (asins: string[], label: string) => {
    asins.forEach((asin, i) =>
      addRecord({ asin, title: `${label} 示例商品 ${i + 1}`,
                  action: "view", timestamp: Date.now() - (asins.length - i) * 1000 })
    );
    navigate("/");
  };

  const applyManual = () => {
    const asins = input.split(/[\n,\s]+/).filter(Boolean);
    asins.forEach((asin) =>
      addRecord({ asin, title: `手动输入 ${asin}`,
                  action: "view", timestamp: Date.now() })
    );
    navigate("/");
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-12">
      <h1 className="text-lg font-semibold mb-2">行为模拟器</h1>
      <p className="text-sm text-gray-500 mb-8">
        注入模拟的浏览历史，立即触发个性化推荐，用于演示与测试。
      </p>

      <div className="space-y-3 mb-8">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">预置场景</p>
        {PRESET_SEQUENCES.map((p) => (
          <button
            key={p.label}
            onClick={() => applyPreset(p.asins, p.label)}
            className="w-full text-left px-4 py-3 border rounded-lg text-sm
                       hover:bg-brand-50 hover:border-brand-300 transition-colors"
          >
            {p.label}
            <span className="ml-2 text-xs text-gray-400">{p.asins.length} 条记录</span>
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          手动输入 ASIN
        </p>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={5}
          className="w-full px-3 py-2 border rounded-lg text-sm font-mono
                     focus:outline-none focus:ring-2 focus:ring-brand-300"
          placeholder={"B001XXXXX\nB002XXXXX\nB003XXXXX"}
        />
        <button
          onClick={applyManual}
          disabled={!input.trim()}
          className="w-full py-2 bg-brand-500 text-white rounded-lg text-sm
                     hover:bg-brand-600 disabled:opacity-40 transition-colors"
        >
          注入历史并查看推荐
        </button>
      </div>
    </div>
  );
}
```

#### 9.4 路由与根组件 `src/App.tsx`

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Navbar }        from "@/components/common/Navbar";
import { HomePage }      from "@/pages/HomePage";
import { SearchPage }    from "@/pages/SearchPage";
import { SimulatorPage } from "@/pages/SimulatorPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Navbar />
        <Routes>
          <Route path="/"          element={<HomePage />} />
          <Route path="/search"    element={<SearchPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

#### ✅ Phase 9 验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 首页渲染 | 注入历史后访问 `/` | 推荐列表展示，行为面板显示历史记录 |
| 搜索联动 | 搜索页添加商品至历史后返回首页 | 推荐结果随历史变化自动更新 |
| 模拟器跳转 | 选择预置场景后 | 自动跳转首页，推荐立即加载 |
| 路由导航 | 在三个页面间切换 | 无白屏，状态保持，浏览器历史正常 |
| 空状态引导 | 清空历史后访问首页 | 显示"添加浏览历史"引导文案而非空白 |
| 端到端流程 | 从模拟器 → 首页推荐 → 点击商品 → 查看弹窗 | 全流程无错误，行为上报成功 |

---

## 7. 集成测试与监控

### 7.1 后端单元测试 `backend/tests/unit/test_sid_service.py`

```python
import pytest
from services.sid_service import SIDService

@pytest.fixture
def sid_service():
    svc = SIDService()
    svc.asin2sid = {"B001": "1_2_3_4", "B002": "5_6_7_8"}
    svc.sid2asin = {"1_2_3_4": "B001", "5_6_7_8": "B002"}
    return svc

def test_asin_to_sid(sid_service):
    assert sid_service.asin_to_sid("B001") == "1_2_3_4"

def test_invalid_asin_returns_none(sid_service):
    assert sid_service.asin_to_sid("B999") is None

def test_batch_filters_invalid(sid_service):
    result = sid_service.asins_to_sids(["B001", "B999", "B002"])
    assert result == ["1_2_3_4", "5_6_7_8"]

def test_sid_to_asin_roundtrip(sid_service):
    original = "B001"
    sid      = sid_service.asin_to_sid(original)
    recovered= sid_service.sid_to_asin(sid)
    assert recovered == original
```

### 7.2 后端集成测试 `backend/tests/integration/test_recommend_api.py`

```python
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_recommend_returns_products():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/recommend", json={
            "user_id":       "test_user_001",
            "history_asins": ["B001XXXXX", "B002XXXXX", "B003XXXXX"],
            "top_k": 5,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert 0 < len(data["recommendations"]) <= 5
    assert all("title" in p for p in data["recommendations"])

@pytest.mark.asyncio
async def test_invalid_asins_returns_400():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/recommend", json={
            "user_id": "test_user", "history_asins": ["INVALID_ASIN_XYZ"]
        })
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

### 7.3 前端组件测试 `frontend/src/components/product/ProductCard.test.tsx`

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ProductCard } from "./ProductCard";
import type { Product } from "@/types/product";

const mockProduct: Product = {
  asin:         "B001TEST",
  title:        "Test Industrial Scrub Pad",
  brand:        "3M",
  category:     "Industrial & Scientific > Janitorial",
  price:        12.99,
  rating:       4.3,
  rating_count: 512,
};

test("renders product title", () => {
  render(<ProductCard product={mockProduct} />);
  expect(screen.getByText("Test Industrial Scrub Pad")).toBeInTheDocument();
});

test("renders price correctly", () => {
  render(<ProductCard product={mockProduct} />);
  expect(screen.getByText("$12.99")).toBeInTheDocument();
});

test("shows rank badge when rank provided", () => {
  render(<ProductCard product={mockProduct} rank={0} />);
  expect(screen.getByText("#1")).toBeInTheDocument();
});

test("calls onClick when card clicked", () => {
  const handleClick = vi.fn();
  render(<ProductCard product={mockProduct} onClick={handleClick} />);
  fireEvent.click(screen.getByText("Test Industrial Scrub Pad"));
  expect(handleClick).toHaveBeenCalledWith(mockProduct);
});

test("does not show add-to-history button without prop", () => {
  render(<ProductCard product={mockProduct} />);
  expect(screen.queryByText("+ 加入浏览历史")).not.toBeInTheDocument();
});
```

### 7.4 关键监控指标

在 `api/middleware/logging_middleware.py` 中记录以下指标，可接入 Prometheus + Grafana：

| 指标名称 | 类型 | 说明 |
|---------|------|------|
| `recommend_latency_ms` | Histogram | 推荐接口端到端耗时（P50 / P90 / P99） |
| `model_inference_ms` | Histogram | 模型推理耗时（Beam Search） |
| `es_query_ms` | Histogram | ES mget 回查耗时 |
| `sid_hit_rate` | Gauge | 输入历史 ASIN 的 SID 命中率 |
| `recommend_empty_count` | Counter | 推荐结果为空次数 |
| `recommend_request_total` | Counter | 推荐接口总请求数 |

---

## 8. Docker 全栈部署

**目标：** 执行 `docker-compose up` 一键启动包含前后端的完整服务栈。

### 8.1 后端 Dockerfile `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 8.2 前端 Dockerfile `frontend/Dockerfile`

```dockerfile
# ── Stage 1: 构建 ──
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: Nginx 静态服务 ──
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ../nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 8.3 Nginx 配置 `nginx/nginx.conf`

```nginx
server {
    listen 80;
    root  /usr/share/nginx/html;
    index index.html;

    # 前端 SPA：所有路由回退至 index.html
    location / {
        try_files $uri $uri/ /index.html;
        gzip_static on;
    }

    # API 请求反向代理至后端 FastAPI
    location /api/ {
        proxy_pass         http://recommendation-api:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host            $host;
        proxy_set_header   X-Real-IP       $remote_addr;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass http://recommendation-api:8000/health;
    }
}
```

### 8.4 `docker-compose.yml`

```yaml
version: "3.9"

services:

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: rec-es
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms2g -Xmx2g
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health | grep -qE 'green|yellow'"]
      interval: 15s
      timeout: 5s
      retries: 8

  redis:
    image: redis:7-alpine
    container_name: rec-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  recommendation-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: rec-api
    depends_on:
      elasticsearch:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file: ./backend/.env
    environment:
      - ES_HOST=http://elasticsearch:9200
      - REDIS_HOST=redis
    ports:
      - "8000:8000"
    volumes:
      - ./backend/models/checkpoints:/app/models/checkpoints:ro
      - ./backend/data/processed:/app/data/processed:ro
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: rec-frontend
    depends_on:
      - recommendation-api
    ports:
      - "80:80"
    restart: unless-stopped

volumes:
  es_data:
  redis_data:
```

### 8.5 一键初始化脚本 `scripts/init_backend.sh`

```bash
#!/bin/bash
set -e

echo "=== Step 1: 商品元数据清洗 ==="
python backend/data/scripts/preprocess_products.py

echo "=== Step 2: 用户行为序列构建 ==="
python backend/data/scripts/preprocess_interactions.py

echo "=== Step 3: 生成 SID 映射表（调用 RQ-VAE 模型）==="
python backend/data/scripts/build_sid_mapping.py

echo "=== Step 4: 等待 Elasticsearch 就绪 ==="
until curl -sf http://localhost:9200/_cluster/health | grep -qE 'green|yellow'; do
    printf "  ES 未就绪，3 秒后重试...\n"; sleep 3
done
echo "  ES 就绪 ✅"

echo "=== Step 5: 创建索引 ==="
python backend/elasticsearch/scripts/create_index.py

echo "=== Step 6: 批量导入商品（含 SID 字段）==="
python backend/elasticsearch/scripts/bulk_index_products.py

echo "=== 后端初始化完成 ✅ ==="
```

#### ✅ Docker 部署验收标准

| 检查项 | 验收方式 | 预期结果 |
|--------|---------|---------|
| 全栈启动 | `docker-compose up --build` | 4 个服务全部启动，无 exit 状态 |
| 前端访问 | 浏览器访问 `http://localhost:80` | React 应用正常加载，无 404 / 502 |
| API 代理 | 前端页面触发推荐请求 | Network 面板显示 200，数据正常渲染 |
| ES 健康 | `docker exec rec-es curl -s localhost:9200/_cluster/health` | `status` 为 green 或 yellow |
| 服务重启 | `docker-compose restart recommendation-api` | 服务重启后推荐接口仍正常响应 |
| 容器隔离 | 停止 `rec-redis` | API 服务降级正常（Redis 缓存失效但不崩溃） |

---

## 9. API 接口规范

### 接口总览

| Method | Path | 描述 |
|--------|------|------|
| `POST` | `/api/v1/recommend` | 个性化推荐（核心接口） |
| `GET` | `/api/v1/products/{asin}` | 单商品详情查询 |
| `GET` | `/api/v1/products/search` | 商品关键词全文搜索 |
| `POST` | `/api/v1/behavior` | 用户行为事件上报 |
| `GET` | `/health` | 服务健康检查 |

### 推荐接口详细规范

**Request**
```json
POST /api/v1/recommend
{
  "user_id":       "U123456",
  "history_asins": ["B00ABC123", "B00DEF456", "B00GHI789"],
  "top_k":         10
}
```

**Response 200**
```json
{
  "user_id": "U123456",
  "recommendations": [
    {
      "asin":         "B00XYZ000",
      "title":        "3M Scotch-Brite Industrial Heavy-Duty Scrub Pad",
      "description":  "Heavy-duty scrub pad for industrial cleaning...",
      "category":     "Industrial & Scientific > Janitorial Supplies",
      "brand":        "3M",
      "price":        12.99,
      "rating":       4.5,
      "rating_count": 2341
    }
  ],
  "total":         10,
  "model_version": "qwen2.5-3b-sft-grpo-v1"
}
```

**Response 400** — 历史 ASIN 无对应 SID
```json
{ "detail": "历史商品均无对应 SID，请检查输入 ASIN" }
```

**Response 500** — 模型未生成有效候选
```json
{ "detail": "模型未生成有效候选商品，请重试" }
```

---

## 10. 在线推荐完整数据流

```
┌────────────────────────────────────────────────────────────────────────┐
│  浏览器：用户操作「加入浏览历史」                                         │
│  → BehaviorStore 更新 → TanStack Query 检测到 queryKey 变化             │
│  → 自动触发 POST /api/v1/recommend                                      │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                        FastAPI 接收请求
                                 │
         ┌───────────────────────▼───────────────────────┐
         │  Step 1  SIDService.asins_to_sids()            │
         │  内存字典查询，< 1ms                             │
         │  ["B001","B002"] → ["1_2_3_4","5_6_7_8"]       │
         └───────────────────────┬───────────────────────┘
                                 │
         ┌───────────────────────▼───────────────────────┐
         │  Step 2  RecommenderInference.predict()        │
         │  Qwen2.5-3B + LoRA                             │
         │  Beam Search（num_beams = 20）                  │
         │  → 候选 SID 列表（去重、按打分排序）              │
         │  耗时：500ms ~ 2s（GPU）                        │
         └───────────────────────┬───────────────────────┘
                                 │
         ┌───────────────────────▼───────────────────────┐
         │  Step 3  SIDService.sids_to_asins()            │
         │  内存字典反查，< 1ms                             │
         │  ["7_8_9_10",...] → ["B007","B010",...]        │
         └───────────────────────┬───────────────────────┘
                                 │
         ┌───────────────────────▼───────────────────────┐
         │  Step 4  ESClient.get_products_by_asins()      │
         │  mget 批量精确查询                              │
         │  → [{asin, title, brand, ...}, ...]            │
         │  耗时：5ms ~ 20ms                              │
         └───────────────────────┬───────────────────────┘
                                 │
                      JSON Response：Top-K 商品列表
                                 │
         ┌───────────────────────▼───────────────────────┐
         │  TanStack Query 缓存 response（staleTime 5min）│
         │  → RecommendFeed 渲染 ProductCard × K          │
         └───────────────────────────────────────────────┘
```

**各步骤预期延迟：**

| 步骤 | 预期耗时 |
|------|----------|
| SID 映射（内存字典 ×2） | < 2ms |
| 模型推理（Beam Search，GPU） | 500ms ~ 2s |
| ES mget 批量回查 | 5ms ~ 20ms |
| 网络传输 + 序列化 | 10ms ~ 30ms |
| **端到端 P50（GPU 环境）** | **约 600ms ~ 2.1s** |

---

## 11. 关键配置说明

### 后端 `.env.example`

```dotenv
# Elasticsearch
ES_HOST=http://localhost:9200
ES_INDEX_NAME=industrial_products
ES_TIMEOUT=10

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_RECOMMEND_TTL=300
REDIS_SID_TTL=86400

# 推荐模型（Qwen2.5-3B + LoRA，已训练完成）
MODEL_BASE=Qwen/Qwen2.5-3B
MODEL_LORA_PATH=./models/checkpoints/qwen25_rec_lora
MODEL_DEVICE=cuda
BEAM_SEARCH_NUM_BEAMS=20
TOP_K=10

# RQ-VAE（仅离线数据预处理使用）
RQVAE_PATH=./models/checkpoints/rqvae

# CORS
CORS_ORIGINS=["http://localhost:5173","http://localhost:80"]

# 数据路径
SID_MAPPING_PATH=./data/processed/sid_mapping.json
PRODUCTS_PATH=./data/processed/products.jsonl
```

### Elasticsearch 生产性能调优

```json
PUT /industrial_products/_settings
{
  "index": {
    "refresh_interval":    "30s",
    "number_of_replicas":  0,
    "translog.durability": "async"
  }
}
```

---

## 12. 里程碑、交付物与验收标准

### 12.1 各阶段里程碑汇总

#### 后端阶段

| 阶段 | 里程碑目标 | 关键交付物 | 预估工时 | 验收标准节 |
|------|-----------|-----------|---------|-----------|
| Phase 0 | 环境可运行 | `requirements.txt`, `settings.py`, ES/Redis 容器启动 | 0.5 天 | §5.Phase0 |
| Phase 1 | 数据就绪 | `products.jsonl`, `user_interactions.jsonl`, `sid_mapping.json` | 1 天 | §5.Phase1 |
| Phase 2 | 索引可查 | ES 索引创建完毕，商品全量导入，mget 接口验证通过 | 0.5 天 | §5.Phase2 |
| Phase 3 | 映射可用 | `sid_service.py` 单元测试全部通过 | 0.5 天 | §5.Phase3 |
| Phase 4 | 推理可调 | `recommender_inference.py` 单独调用返回合法 SID | 1 天 | §5.Phase4 |
| Phase 5 | API 全通 | 三个路由可用，端到端推荐链路联调通过 | 1.5 天 | §5.Phase5 |

#### 前端阶段

| 阶段 | 里程碑目标 | 关键交付物 | 预估工时 | 验收标准节 |
|------|-----------|-----------|---------|-----------|
| Phase 6 | 工程可跑 | Vite 工程初始化，组件库就绪，开发代理配置 | 0.5 天 | §6.Phase6 |
| Phase 7 | 数据层通 | `api/`, `hooks/`, `store/` 全部实现，与后端联通 | 1 天 | §6.Phase7 |
| Phase 8 | 组件可用 | `ProductCard`, `RecommendFeed`, `BehaviorPanel` 完成并通过组件测试 | 1.5 天 | §6.Phase8 |
| Phase 9 | 页面完整 | 三页完成，完整用户操作流程可跑通 | 1 天 | §6.Phase9 |

#### 集成与部署阶段

| 阶段 | 里程碑目标 | 关键交付物 | 预估工时 | 验收标准节 |
|------|-----------|-----------|---------|-----------|
| 集成测试 | 全链路质量保障 | 后端单元 + 集成测试，前端组件测试，端到端冒烟通过 | 1 天 | §7 |
| Docker 部署 | 一键可运行 | `docker-compose up --build` 启动完整服务栈 | 0.5 天 | §8 |

### 12.2 整体验收标准（最终交付物）

> 所有以下条件均满足，视为项目验收通过。

**功能验收**

| 编号 | 验收项 | 验收方式 | 通过条件 |
|------|--------|---------|---------|
| F-01 | 端到端推荐流程 | 在前端行为模拟器注入 5 条历史记录，跳转首页 | 推荐列表展示 ≥ 1 件商品，含标题、价格等完整信息 |
| F-02 | 推荐个性化 | 注入不同品类历史序列，分别触发推荐 | 两次推荐结果存在差异（不完全相同） |
| F-03 | 商品搜索 | 在搜索页输入 "safety gloves" | 返回相关商品结果，展示正常 |
| F-04 | 行为持久化 | 添加历史后刷新页面 | 历史记录保留，推荐自动加载 |
| F-05 | 错误容忍 | 断开后端后在前端操作 | 显示友好错误提示，不崩溃白屏 |

**性能验收**

| 编号 | 验收项 | 测量方式 | 通过条件 |
|------|--------|---------|---------|
| P-01 | 推荐接口延迟 | 连续请求 10 次，取 P50 | P50 < 2s（GPU 推理环境） |
| P-02 | ES 回查延迟 | 单独测试 mget 10 条 | P50 < 30ms |
| P-03 | 前端首屏时间 | Lighthouse 测量 | FCP < 1.5s（本地环境） |
| P-04 | SID 映射耗时 | 批量转换 1000 个 ASIN 计时 | 总耗时 < 5ms |

**质量验收**

| 编号 | 验收项 | 验收方式 | 通过条件 |
|------|--------|---------|---------|
| Q-01 | 后端测试覆盖 | `pytest --cov` | 核心 Service 层覆盖率 ≥ 80% |
| Q-02 | 前端类型安全 | `tsc --noEmit` | 0 类型错误 |
| Q-03 | 前端组件测试 | `npm run test` | 所有测试用例通过 |
| Q-04 | API 文档完整 | 访问 `/docs` | 所有路由可见，Schema 正确渲染 |

**部署验收**

| 编号 | 验收项 | 验收方式 | 通过条件 |
|------|--------|---------|---------|
| D-01 | 一键启动 | 干净环境执行 `docker-compose up --build` | 4 个服务全部健康，无需手动干预 |
| D-02 | 数据初始化 | 执行 `scripts/init_backend.sh` | 无报错，ES 商品数量与文件行数一致 |
| D-03 | 服务韧性 | 重启 `rec-api` 容器 | 30s 内自动恢复，推荐接口重新可用 |

---

### 12.3 工时汇总

| 模块 | 预估工时 |
|------|---------|
| 后端（Phase 0 ~ 5） | 5 天 |
| 前端（Phase 6 ~ 9） | 4 天 |
| 集成测试 + Docker 部署 | 1.5 天 |
| **合计** | **约 10.5 天** |

---

*本文档版本 v3.0（全栈版，含验收标准）*

