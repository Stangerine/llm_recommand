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
└─────────────────┬──────────────────────────────────┬────────────────┘
                  │                                  │
                  ▼                                  ▼
┌─────────────────────────────┐    ┌──────────────────────────────────┐
│      RecommendPipeline      │    │        Elasticsearch (:9200)     │
│                             │    │                                  │
│  1. ASIN → SID (内存字典)    │    │  products index                  │
│  2. 模型推理 → 候选SID       │◄──►│  asin | title | description      │
│  3. SID → ASIN (内存字典)    │    │  category | brand | price | sid  │
│  4. ES/本地缓存回查          │    │                                  │
│  5. 返回排序后Top-K          │    │  mget (精确回查)                  │
│                             │    │  multi_match (全文搜索)           │
└─────────────┬───────────────┘    └──────────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐    ┌──────────────────────────────────┐
│    Model Inference Service  │    │            Redis (:6379)         │
│                             │    │                                  │
│  Qwen2.5-3B + LoRA          │    │  推荐结果缓存  TTL: 5min          │
│  Beam Search (×20 beams)    │◄──►│  SID映射缓存   TTL: 24h          │
│  模拟模式 (无GPU时)          │    │                                  │
└─────────────┬───────────────┘    └──────────────────────────────────┘
              │
              ▼
┌─────────────────────────────┐
│      SID Mapping Service    │
│                             │
│  asin2sid: dict (内存)      │
│  sid2asin: dict (内存)      │
│  查询耗时 < 1ms              │
└─────────────────────────────┘
```

### 1.2 组件职责

| 组件 | 职责 | 数据存储 | 查询延迟 |
|------|------|----------|----------|
| **Elasticsearch** | 商品索引、全文搜索、批量回查 | 索引数据 | 5-20ms |
| **Redis** | 推荐结果缓存、会话存储 | 内存KV | <1ms |
| **SIDService** | ASIN↔SID双向映射 | 内存字典 | <1ms |
| **本地JSONL** | 商品数据备份（ES不可用时） | 文件系统 | 1-5ms |

---

## 2. Elasticsearch 详解

### 2.1 核心功能

#### 功能1：商品批量回查（mget）

推荐流水线的最后一步，根据ASIN列表批量获取商品详情。

```python
# es_client/client.py
async def get_products_by_asins(self, asins: list[str]) -> list[dict]:
    """
    mget 批量精确回查
    - 输入: ASIN列表，如 ["B001XXXXX", "B002XXXXX"]
    - 输出: 商品详情列表，包含title, price, brand等
    - 延迟: 5-20ms（ES）/ 1-5ms（本地缓存）
    """
    # 优先使用本地缓存
    if self._products_cache:
        results = []
        for asin in asins:
            if asin in self._products_cache:
                results.append(self._products_cache[asin])
        return results
    
    # 本地缓存为空时使用ES
    resp = await self.client.mget(index=self.index, body={"ids": asins})
    return [hit["_source"] for hit in resp["docs"] if hit.get("found")]
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

| 查询类型 | ES延迟 | 本地缓存延迟 | 说明 |
|----------|--------|--------------|------|
| mget (10条) | 5-20ms | 1-5ms | 推荐结果回查 |
| 全文搜索 | 10-50ms | 1-10ms | 用户搜索 |
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
| SID映射 | `sid:{asin}` | 24小时 | 减少文件读取（可选） |

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
│  - 本地缓存优先: 直接从内存字典获取                                   │
│  - ES回查: mget批量查询                                              │
│                                                                      │
│  延迟: 1-5ms (本地) / 5-20ms (ES)                                   │
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
GET /api/v1/products/search?q=safety+gloves
        │
        ▼
┌───────────────────────────────────────┐
│ ESClient.search_products("safety gloves") │
│                                       │
│ 1. 构建查询:                          │
│    multi_match {                      │
│      query: "safety gloves",          │
│      fields: ["title^3", "description", "brand^2"]
│    }                                  │
│                                       │
│ 2. 执行搜索:                          │
│    es.search(index="industrial_products", body=...) │
│                                       │
│ 3. 返回结果:                          │
│    [{asin, title, price, ...}, ...]   │
└───────────────────────────────────────┘
        │
        ▼
返回 SearchResponse {results: [...], total: 10}
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
    def __init__(self):
        self._products_cache = {}  # 本地商品缓存
        self._load_local_products()  # 启动时加载165,686个商品
    
    async def get_products_by_asins(self, asins):
        # 优先使用本地缓存
        if self._products_cache:
            return [self._products_cache[asin] for asin in asins if asin in self._products_cache]
        
        # 本地缓存为空时尝试ES
        if self.client:
            try:
                resp = await self.client.mget(...)
                return [...]
            except:
                pass
        
        return []  # 都不可用时返回空
```

**降级效果：**
- ✅ 推荐功能正常（使用本地商品数据）
- ✅ 商品详情正常
- ⚠️ 搜索功能较弱（简单文本匹配 vs ES全文搜索）

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
| 搜索延迟 | 10-50ms | 1-10ms | ES全文搜索 vs 本地匹配 |
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

*文档版本: v1.0 | 最后更新: 2026-06-23*
