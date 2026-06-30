# Redis 与 Elasticsearch 架构指南

## 目录

1. [整体架构](#1-整体架构)
2. [Elasticsearch 详解](#2-elasticsearch-详解)
3. [Redis 详解](#3-redis-详解)
4. [数据流向](#4-数据流向)
5. [配置说明](#5-配置说明)
6. [启动方式](#6-启动方式)
7. [降级策略](#7-降级策略)

---

## 1. 整体架构

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户浏览器                                   │
│                     React + TypeScript (Vite)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP/JSON
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway (:8000)                         │
│                                                                      │
│  POST /api/v1/recommend    GET /api/v1/products/{asin}               │
│  GET  /api/v1/products/search    POST /api/v1/behavior               │
│  GET  /api/v1/products                                            │
└─────────┬──────────┬──────────────────┬──────────────┬─────────────┘
          │          │                  │              │
          ▼          ▼                  ▼              ▼
┌──────────────────┐ ┌────────────────┐ ┌────────────────────────────┐
│ RecommendPipeline│ │ SearchService  │ │ EmbeddingService           │
│                  │ │                │ │ (bge-base-en-v1.5, 768维)  │
│ 1. ASIN → SID    │ │ keyword (ES)   │ └─────────────┬──────────────┘
│ 2. 模型推理→候选SID│ │ vector (Milvus)│               │
│ 3. SID → ASIN    │ │ hybrid (RRF)   │               ▼
│ 4. ES+Redis 回查 │ │ 并行 ES + Milvus│ ┌────────────────────────────┐
│ 5. 排序返回 Top-K │ └───────┬────────┘ │ Milvus Lite (VectorService) │
└────────┬─────────┘         │          │                            │
         │                   │          │ products 集合 (768维向量)    │
         ▼                   ▼          │ sid_mapping 集合 (ASIN↔SID) │
┌──────────────────┐ ┌────────────────┐ └────────────────────────────┘
│ Model Inference  │ │ Elasticsearch  │
│ Qwen2.5-3B+LoRA  │ │ (:9200)        │  ┌────────────────────────────┐
│ Beam Search ×20  │ │                │  │ Redis (:6379)              │
│ 模拟模式(降级)    │ │ products index │  │                            │
└──────────────────┘ │ mget / search  │  │ 推荐结果缓存  TTL: 5min     │
                     └────────────────┘  │ 商品详情缓存  TTL: 1h       │
                                         │ SID映射缓存   TTL: 24h      │
┌──────────────────┐                     └────────────────────────────┘
│ SIDService       │
│ ASIN↔SID 双向映射 │
│ 三级:Redis→Milvus│
│ →JSON(兜底)      │
└──────────────────┘
```

### 1.2 组件职责

| 组件 | 职责 | 数据存储 | 查询延迟 |
|------|------|----------|----------|
| **Elasticsearch** | 商品索引、全文搜索、批量回查 | 索引数据 | 5-20ms |
| **Redis** | 推荐结果缓存、商品详情缓存、SID映射缓存 | 内存KV | <1ms |
| **Milvus Lite** | 向量语义搜索、SID映射持久化存储 | 本地文件 | 5-30ms |
| **EmbeddingService** | 文本向量化（bge-base-en-v1.5, 768维） | — | 10-50ms |
| **SearchService** | 统一搜索编排（keyword/vector/hybrid + RRF融合） | — | 取决于后端 |
| **SIDService** | ASIN↔SID双向映射（三级查询） | Redis+Milvus+JSON | <1ms |

---

## 2. Elasticsearch 详解

### 2.1 核心功能

#### 功能1：商品批量回查（mget）

推荐流水线的最后一步，根据ASIN列表批量获取商品详情。

```python
# es_client/client.py
class ESClient:
    """商品客户端：ES 主存储 + Redis 热点缓存"""

    def __init__(self, vector_service=None, cache_service=None):
        self._vector_svc = vector_service   # Milvus（搜索降级用）
        self._cache_svc = cache_service     # Redis 缓存
        self.use_simulation = True
        self.client = None
        # 尝试连接 ES...

    async def get_products_by_asins(self, asins: list[str]) -> list[dict]:
        """
        批量精确回查——推荐流水线末端核心方法。
        Redis 缓存 → ES mget → 占位符
        - 输入: ASIN列表，如 ["B001XXXXX", "B002XXXXX"]
        - 输出: 商品详情列表，保持原始 ASIN 顺序
        - 延迟: <1ms（Redis命中）/ 5-20ms（ES）
        """
        result_map = {}
        missing = list(asins)

        # 1. 批量查 Redis
        if self._cache_svc and missing:
            cached = await self._cache_svc.get_products_batch(missing)
            result_map.update(cached)
            missing = [a for a in missing if a not in cached]

        # 2. ES mget 回查（主数据源）
        if not self.use_simulation and self.client is not None and missing:
            resp = await self.client.mget(index=settings.es_index_name, body={"ids": missing})
            to_cache = {}
            for hit in resp["docs"]:
                if hit.get("found"):
                    source = hit["_source"]
                    result_map[source["asin"]] = source
                    to_cache[source["asin"]] = source
            if self._cache_svc and to_cache:
                await self._cache_svc.set_products_batch(list(to_cache.values()))
            missing = [a for a in missing if a not in to_cache]

        # 3. 组装结果（保持原顺序，查不到的用占位符）
        return [result_map.get(a, _placeholder(a)) for a in asins]
```

**使用场景：**
- 推荐接口返回候选商品详情
- 商品详情页展示

#### 功能2：全文搜索（multi_match）

支持用户搜索商品，按相关性排序。

```python
# es_client/client.py
async def search_products(self, query: str, size: int = 10, category: str | None = None) -> list[dict]:
    """
    全文搜索
    - 输入: 搜索关键词，如 "safety gloves"
    - 输出: 相关商品列表，按相关性排序
    - 延迟: 10-50ms
    """
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "description", "brand^2"]  # title权重最高
            }
        }
    ]
    if category:
        must.append({"term": {"category": category}})
    
    resp = await self.client.search(
        index=self.index,
        body={"query": {"bool": {"must": must}}, "size": size}
    )
    return [hit["_source"] for hit in resp["hits"]["hits"]]
```

**使用场景：**
- 搜索页商品搜索
- 分类筛选

### 2.2 索引结构

```json
// elasticsearch/mappings/products_mapping.json
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
      "asin":         { "type": "keyword" },           // 商品唯一标识
      "title":        { "type": "text",                // 商品标题（全文检索）
                        "analyzer": "product_analyzer",
                        "fields": { "raw": { "type": "keyword" } } },
      "description":  { "type": "text" },              // 商品描述（全文检索）
      "category":     { "type": "keyword" },           // 分类（精确匹配）
      "brand":        { "type": "keyword" },           // 品牌（精确匹配）
      "price":        { "type": "float" },             // 价格
      "rating":       { "type": "float" },             // 评分
      "rating_count": { "type": "integer" },           // 评价数量
      "sid":          { "type": "keyword" }            // 语义ID（推荐用）
    }
  }
}
```

### 2.3 数据导入流程

```bash
# 1. 创建索引
python es_client/scripts/create_index.py

# 2. 批量导入商品（165,686条）
python es_client/scripts/bulk_index_products.py
```

```python
# es_client/scripts/bulk_index_products.py
def bulk_index():
    """批量导入商品到ES"""
    es = Elasticsearch(settings.es_host)
    
    # 读取SID映射
    with open(settings.sid_mapping_path) as f:
        sid_map = json.load(f)["asin2sid"]
    
    def gen_actions():
        with open(settings.products_path) as f:
            for line in f:
                p = json.loads(line)
                yield {
                    "_index": settings.es_index_name,
                    "_id": p["asin"],
                    "_source": {**p, "sid": sid_map.get(p["asin"], "")}
                }
    
    # 批量写入
    success, failed = bulk(es, gen_actions(), chunk_size=500)
```

### 2.4 查询性能对比

| 查询类型 | ES延迟 | Redis缓存延迟 | 说明 |
|----------|--------|--------------|------|
| mget (10条) | 5-20ms | <1ms | 推荐结果回查 |
| 全文搜索 | 10-50ms | — | ES 搜索无缓存 |
| 单条查询 | 2-10ms | <1ms | 商品详情 |

---

## 3. Redis 详解

### 3.1 核心功能

#### 功能1：推荐结果缓存

缓存推荐结果，避免相同请求重复调用模型推理。

```python
# services/cache_service.py
class CacheService:
    async def get_recommend_cache(self, user_id: str, history_hash: str) -> dict | None:
        """获取推荐缓存"""
        key = f"recommend:{user_id}:{history_hash}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def set_recommend_cache(self, user_id: str, history_hash: str, data: dict) -> bool:
        """设置推荐缓存，5分钟过期"""
        key = f"recommend:{user_id}:{history_hash}"
        await self.redis.setex(key, 300, json.dumps(data))  # TTL: 300秒
        return True
```

**缓存Key设计：**
```
recommend:{user_id}:{history_hash}
     │           │           │
     │           │           └── 历史ASIN列表的MD5哈希（前12位）
     │           └── 用户ID
     └── 前缀
```

**示例：**
```
recommend:user_abc123:a1b2c3d4e5f6
```

#### 功能2：缓存命中流程

```python
# api/routers/recommend.py
async def recommend(req: RecommendRequest, request: Request):
    # 1. 计算历史哈希
    history_hash = _hash_history(req.history_asins)
    
    # 2. 检查缓存
    cached = await cache_svc.get_recommend_cache(req.user_id, history_hash)
    if cached:
        # 缓存命中，直接返回（跳过模型推理）
        return RecommendResponse(**cached)
    
    # 3. 缓存未命中，执行完整推荐流水线
    # ... 模型推理、ES回查等 ...
    
    # 4. 写入缓存
    await cache_svc.set_recommend_cache(req.user_id, history_hash, result)
    
    return result
```

### 3.2 缓存策略

| 缓存类型 | Key格式 | TTL | 说明 |
|----------|---------|-----|------|
| 推荐结果 | `recommend:{user_id}:{history_hash}` | 5分钟 | 相同历史不重复推理 |
| 商品详情 | `product:{asin}` | 1小时 | 推荐/搜索回查加速 |
| SID映射 | `sid:{asin}` | 24小时 | ASIN↔SID 转换缓存 |

### 3.3 缓存命中率优化

**场景分析：**

| 场景 | 命中率 | 说明 |
|------|--------|------|
| 用户首次访问 | 0% | 无缓存 |
| 用户重复刷新 | 100% | 相同历史+相同用户 |
| 不同用户相同历史 | 0% | user_id不同 |
| 用户添加新商品 | 0% | history_hash变化 |

**优化建议：**
1. 增加TTL（当前5分钟）
2. 使用更细粒度的缓存key
3. 预热热门商品组合的推荐结果

### 3.4 Redis 数据结构

```redis
# 推荐结果缓存
SET recommend:user_abc123:a1b2c3d4 '{"user_id":"user_abc123","recommendations":[...],"total":10}'
EXPIRE recommend:user_abc123:a1b2c3d4 300  # 5分钟过期

# 查询
GET recommend:user_abc123:a1b2c3d4
```

---

## 4. 数据流向

### 4.1 推荐请求完整流程

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: 用户操作                                                    │
│  用户点击商品 → behaviorStore.addRecord()                            │
│  → historyAsins() 更新                                               │
│  → TanStack Query 检测到 queryKey 变化                               │
│  → 自动触发 POST /api/v1/recommend                                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: 检查 Redis 缓存                                             │
│                                                                      │
│  key = "recommend:{user_id}:{history_hash}"                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ if cached:                                                   │   │
│  │     return cached  # 命中缓存，跳过后续步骤                    │   │
│  │ else:                                                        │   │
│  │     continue  # 未命中，继续执行                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ (缓存未命中)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: ASIN → SID 转换                                             │
│                                                                      │
│  Input:  ["0176496920", "0692782109"]                               │
│  Output: ["0_6_14_1", "3_5_8_0"]                                    │
│                                                                      │
│  实现: 内存字典查询，< 1ms                                            │
│  代码: sid_svc.asins_to_sids(history_asins)                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4: 模型推理                                                    │
│                                                                      │
│  Input:  ["0_6_14_1", "3_5_8_0"]                                    │
│  Output: ["13_8_8_1", "6_5_11_7", "14_7_15_0", ...]                │
│                                                                      │
│  实现:                                                               │
│  - 有GPU: Qwen2.5-3B + LoRA, Beam Search (20 beams)                │
│  - 无GPU: 模拟模式，生成确定性随机SID                                 │
│                                                                      │
│  延迟: 500ms-2s (GPU) / < 1ms (模拟)                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 5: SID → ASIN 转换                                             │
│                                                                      │
│  Input:  ["13_8_8_1", "6_5_11_7", "14_7_15_0"]                     │
│  Output: ["B008FCSMX2", "B0010SNA5I", "B0123X823S"]                │
│                                                                      │
│  实现: 内存字典查询，< 1ms                                            │
│  代码: sid_svc.sids_to_asins(candidate_sids)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 6: 商品详情回查                                                │
│                                                                      │
│  Input:  ["B008FCSMX2", "B0010SNA5I", "B0123X823S"]                │
│  Output: [{asin, title, price, brand, ...}, ...]                    │
│                                                                      │
│  实现:                                                               │
│  - Redis 缓存优先: mget 批量查询商品详情                               │
│  - ES mget: 未命中时回查，结果回填 Redis                              │
│  - 占位符: 仍缺失的 ASIN 返回占位对象                                  │
│                                                                      │
│  延迟: <1ms (Redis命中) / 5-20ms (ES)                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 7: 写入缓存并返回                                              │
│                                                                      │
│  1. 按模型打分顺序排序                                               │
│  2. 写入 Redis 缓存 (TTL: 5分钟)                                    │
│  3. 返回 RecommendResponse                                          │
│                                                                      │
│  Response:                                                           │
│  {                                                                   │
│    "user_id": "user_abc123",                                        │
│    "recommendations": [                                              │
│      {"asin": "B008FCSMX2", "title": "...", "price": 29.99},       │
│      ...                                                             │
│    ],                                                                │
│    "total": 10,                                                      │
│    "model_version": "qwen2.5-3b-sft-grpo-v1"                       │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 搜索请求流程

```
用户输入 "safety gloves"
        │
        ▼
GET /api/v1/products/search?q=safety+gloves&mode=hybrid
        │
        ▼
SearchService.search("safety gloves", mode="hybrid")
        │
        ├─ keyword 模式: ES multi_match (title^3, description, brand^2)
        ├─ vector 模式: 文本 → embedding → Milvus cosine 搜索
        └─ hybrid 模式: ES + Milvus 并行执行 → RRF 融合
                │
                ▼
返回 SearchResponse {results: [...], total: 10, mode: "hybrid"}
```

---

## 5. 配置说明

### 5.1 环境变量 (.env)

```bash
# Elasticsearch
ES_HOST=http://localhost:9200
ES_INDEX_NAME=industrial_products
ES_TIMEOUT=10

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_RECOMMEND_TTL=300    # 推荐缓存5分钟
REDIS_SID_TTL=86400        # SID缓存24小时
REDIS_PRODUCT_TTL=3600     # 商品缓存1小时

# Milvus
MILVUS_URI=products.db
MILVUS_COLLECTION=products
MILVUS_SID_COLLECTION=sid_mapping

# Embedding
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DIM=768
EMBEDDING_BATCH_SIZE=128

# 模型
MODEL_BASE=Qwen/Qwen2.5-3B
MODEL_DEVICE=cuda
TOP_K=10
BEAM_SEARCH_NUM_BEAMS=20
```

### 5.2 配置类 (config/settings.py)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index_name: str = "industrial_products"
    es_timeout: int = 10

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_recommend_ttl: int = 300
    redis_sid_ttl: int = 86400
    redis_product_ttl: int = 3600

    # Milvus
    milvus_uri: str = "products.db"
    milvus_collection: str = "products"
    milvus_sid_collection: str = "sid_mapping"

    # Embedding
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    embedding_batch_size: int = 128

    # 模型
    model_base: str = "Qwen/Qwen2.5-3B"
    model_device: str = "cuda"
    beam_search_num_beams: int = 20
    top_k: int = 10

    # 数据路径
    sid_mapping_path: str = "./data/processed/sid_mapping.json"
    products_path: str = "./data/processed/products.jsonl"
```

---

## 6. 启动方式

### 6.1 Docker 启动（推荐）

```bash
# 启动 Elasticsearch
docker run -d \
  --name es-rec \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.13.0

# 启动 Redis
docker run -d \
  --name redis-rec \
  -p 6379:6379 \
  redis:7-alpine

# 验证
curl http://localhost:9200/_cluster/health
redis-cli ping
```

### 6.2 本地安装

**Elasticsearch:**
```bash
# 下载: https://www.elastic.co/downloads/elasticsearch
# 解压后运行
bin/elasticsearch.bat  # Windows
./bin/elasticsearch    # Linux/Mac
```

**Redis:**
```bash
# Windows: https://github.com/tporadowski/redis/releases
# Linux: sudo apt install redis-server
# Mac: brew install redis

# 启动
redis-server
```

### 6.3 验证连接

```bash
# 测试ES
curl http://localhost:9200/_cluster/health
# 返回: {"cluster_name":"...", "status":"green/yellow", ...}

# 测试Redis
redis-cli ping
# 返回: PONG
```

---

## 7. 降级策略

### 7.1 ES不可用时

```python
# es_client/client.py
class ESClient:
    """商品客户端：ES 主存储 + Redis 热点缓存，Milvus 仅作搜索降级"""

    def __init__(self, vector_service=None, cache_service=None):
        self._vector_svc = vector_service   # Milvus（搜索降级用）
        self._cache_svc = cache_service     # Redis 缓存
        self.use_simulation = True          # ES 不可用时为 True
        self.client = None

    async def search_products(self, query, size=10, category=None):
        # 优先使用 ES
        if not self.use_simulation and self.client is not None:
            try:
                resp = await self.client.search(...)
                return [...]
            except Exception:
                pass

        # 降级：从 Milvus 取商品做内存子串匹配
        if self._vector_svc and self._vector_svc.is_available():
            all_products, _ = self._vector_svc.list_products(page=1, page_size=500)
            # 对 title + description + brand 做子串匹配
            results = [p for p in all_products if query.lower() in searchable_text(p)]
            return results[:size]

        return []
```

**降级效果：**
- ✅ 商品回查正常（Redis → ES → 占位符）
- ✅ 商品详情正常
- ⚠️ 搜索功能降级为 Milvus 内存子串匹配（精确度低于 ES 全文搜索）

### 7.2 Redis不可用时

```python
# services/cache_service.py
class CacheService:
    async def initialize(self):
        try:
            self.redis = aioredis.Redis(...)
            await self.redis.ping()
        except:
            self.redis = None  # 连接失败，禁用缓存
    
    async def get(self, key):
        if not self.redis:
            return None  # 无Redis，返回None（未命中）
        ...
    
    async def set(self, key, value, ttl):
        if not self.redis:
            return False  # 无Redis，跳过写入
        ...
```

**降级效果：**
- ✅ 推荐功能正常
- ⚠️ 每次请求都重新推理（无缓存）
- ⚠️ 响应延迟增加（500ms-2s）

### 7.3 降级状态检查

```bash
# 查看当前状态
curl http://localhost:8000/health
# 返回: {"status": "ok"}

curl http://localhost:8000/metrics
# 返回: {
#   "recommend_request_total": 10,
#   "recommend_empty_count": 0,
#   "sid_hit_rate": 1.0,
#   ...
# }
```

---

## 8. 性能对比

### 8.1 有ES/Redis vs 无ES/Redis

| 指标 | 有ES/Redis | 无ES/Redis | 说明 |
|------|-----------|-----------|------|
| 推荐延迟 (首次) | 600ms-2.1s | 600ms-2.1s | 主要耗时在模型推理 |
| 推荐延迟 (缓存) | < 10ms | 600ms-2.1s | Redis缓存命中 |
| 搜索延迟 | 10-50ms | 50-200ms | ES全文搜索 vs Milvus子串匹配 |
| 搜索质量 | 高 | 中 | ES相关性排序 vs 简单匹配 |
| 内存占用 | 高 | 低 | ES需要额外内存 |

### 8.2 优化建议

1. **生产环境必须启动ES/Redis**
2. **增加ES副本**提高可用性
3. **调整Redis TTL**平衡缓存命中率和数据新鲜度
4. **预热缓存**热门商品组合

---

## 9. 监控指标

### 9.1 /metrics 接口

```json
{
  "recommend_request_total": 100,      // 总请求数
  "recommend_empty_count": 2,          // 空结果数
  "sid_hit_rate": 0.98,                // SID命中率
  "avg_recommend_latency_ms": 150.5,   // 平均推荐延迟
  "avg_model_inference_ms": 120.3,     // 平均模型推理延迟
  "avg_es_query_ms": 15.2              // 平均ES查询延迟
}
```

### 9.2 告警阈值

| 指标 | 阈值 | 说明 |
|------|------|------|
| recommend_empty_rate | > 5% | 推荐空结果过多 |
| avg_recommend_latency_ms | > 3000ms | 推荐延迟过高 |
| sid_hit_rate | < 90% | SID映射命中率低 |

---

*文档版本: v1.1 | 最后更新: 2026-06-30*
