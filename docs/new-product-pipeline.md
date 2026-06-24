# 新商品入库影响分析

## 目录

1. [影响链总览](#1-影响链总览)
2. [RQ-VAE 语义编码层](#2-rq-vae-语义编码层)
3. [SID 映射表](#3-sid-映射表)
4. [Qwen2.5 推荐模型](#4-qwen25-推荐模型)
5. [Elasticsearch 索引](#5-elasticsearch-索引)
6. [Milvus 向量索引](#6-milvus-向量索引)
7. [完整更新流程](#7-完整更新流程)
8. [增量更新 vs 全量重训](#8-增量更新-vs-全量重训)

---

## 1. 影响链总览

新商品入库后，整条 ML pipeline 依次受影响：

```
新商品入库
    │
    ▼
① RQ-VAE 编码 → 生成新 SID（语义ID）
    │
    ▼
② SID 映射表更新 → sid_mapping.json 追加新映射
    │
    ▼
③ Qwen2.5 推理 → 推荐结果可能包含新商品
    │
    ▼
④ ES 索引更新 → 新商品可被关键词搜索
    │
    ▼
⑤ Milvus 向量索引更新 → 新商品可被语义搜索
```

每个环节的更新成本不同：

| 环节 | 组件 | 是否必须重训 | 更新耗时 | 优先级 |
|------|------|-------------|---------|--------|
| ① | RQ-VAE | 不一定 | 1-2 分钟（1000个商品） | 低 |
| ② | SID 映射 | 必须重建 | < 1 秒 | 高 |
| ③ | Qwen2.5 | 建议重训 | 数小时-数天（GPU） | 中 |
| ④ | ES 索引 | 必须更新 | 10-30 秒 | 高 |
| ⑤ | Milvus 向量索引 | 必须更新 | 1-3 分钟（含 embedding） | 高 |

---

## 2. RQ-VAE 语义编码层

### 2.1 RQ-VAE 的作用

RQ-VAE（残差量化变分自编码器）负责将商品文本映射为离散的语义 ID（SID）：

```
输入: 商品标题 + 描述
      "3M Safety Gloves Industrial Protection..."
      ↓
   Encoder（神经网络）
      ↓
   连续向量 [0.12, -0.34, 0.56, ...]
      ↓
   残差量化（4层 codebook 逐层查找最近邻）
      ↓
   离散 SID: 12_5_3_7
```

SID 格式为 4 层 codebook 索引，以 `_` 连接。每层 codebook 是一个预定义的离散码本，编码器在每层选择最相近的码字。

### 2.2 是否需要重训

RQ-VAE 的核心是 **codebook（码本）**，它定义了离散语义空间。新商品是否需要重训取决于与训练集的相似度。

**不重训的条件：**

- 新商品与现有商品属于相似类别
- 现有 codebook 能覆盖新商品的语义
- 编码质量可接受（SID 碰撞率在合理范围内）

```python
# 用现有模型直接编码新商品
encoder = RQVAEEncoder(ckpt_path="models/checkpoints/rqvae")
new_text = "新型纳米涂层防护手套"
new_sid = encoder.encode_single(new_text)
# 输出: "8_3_11_2"（使用现有 codebook）
```

**必须重训的条件：**

- 新商品类别与训练集差异很大（如从工业品扩展到食品）
- codebook 容量不够（无法区分新类别的细微语义差异）
- 编码质量下降（SID 碰撞率 > 30%）

### 2.3 重训策略

| 策略 | 适用场景 | 成本 |
|------|---------|------|
| 全量重训 | 新类别占比 > 20% | 高（数天 GPU） |
| 增量微调 | 新类别占比 5%-20% | 中（数小时 GPU） |
| 不重训 | 新类别占比 < 5% | 零 |

---

## 3. SID 映射表

### 3.1 映射表结构

SID 映射表存储 ASIN 与 SID 的双向映射关系：

```json
{
  "asin2sid": {
    "0176496920": "12_5_3_7",
    "0692782109": "3_5_8_0",
    ...
  },
  "sid2asin": {
    "12_5_3_7": "0176496920",
    "3_5_8_0": "0692782109",
    ...
  }
}
```

当前规模：165,686 个 ASIN 映射到 60,203 个唯一 SID。

### 3.2 SID 碰撞问题

多个 ASIN 可能映射到同一个 SID（碰撞）。当前策略是取第一个商品：

```python
sid2asin.setdefault(sid, p["asin"])  # 碰撞取首个
```

新商品加入后碰撞率可能上升：

```
碰撞率 = 1 - (唯一SID数 / 总商品数)
当前: 1 - 60203/165686 = 63.6%（即约 64% 的商品有 SID 碰撞）
```

### 3.3 更新方式

**必须更新**，否则新商品无法参与推荐流程。

增量更新步骤：

```python
# 1. 用现有 RQ-VAE 编码新商品
encoder = RQVAEEncoder(ckpt_path="models/checkpoints/rqvae")

for product in new_products:
    text = f"{product['title']} {product['description'][:200]}"
    sid = encoder.encode_single(text)
    asin2sid[product["asin"]] = sid
    sid2asin.setdefault(sid, product["asin"])

# 2. 保存更新后的映射表
with open("data/processed/sid_mapping.json", "w") as f:
    json.dump({"asin2sid": asin2sid, "sid2asin": sid2asin}, f, indent=2)

# 3. 重启后端服务，重新加载内存字典
```

---

## 4. Qwen2.5 推荐模型

### 4.1 训练数据格式

推荐模型在 SID 序列上训练：

```
训练样本:
  输入: [12_5_3_7, 3_5_8_0]          (用户历史 SID 序列)
  标签: [13_8_8_1, 6_5_11_7, ...]    (下一个点击的 SID)

预测目标: 给定历史序列，预测下一个可能点击的 SID
```

### 4.2 新商品的影响

新商品的 SID 在训练时从未出现过，模型无法学到它们的推荐模式：

| 新商品占比 | 模型表现 | 是否重训 |
|-----------|---------|---------|
| < 5% | 泛化能力可能覆盖 | 可以不训 |
| 5%-20% | 部分新商品无法被推荐 | 建议增量微调 |
| > 20% | 大量新商品无法被推荐 | 必须重训 |

### 4.3 增量微调方案

不从头训练，用 LoRA 在现有 checkpoint 上继续训练：

```python
# 增量微调流程
# 1. 用新商品的交互数据构造训练样本
# 2. 加载现有 checkpoint
# 3. 只更新 LoRA adapter 权重
# 4. 保存新的 adapter

# LoRA 微调优势:
# - 训练速度快（只更新少量参数）
# - 不会遗忘旧商品的推荐模式
# - 可以快速迭代
```

### 4.4 训练触发条件

| 条件 | 触发动作 |
|------|---------|
| 新商品 < 100 个 | 不训练，依赖泛化 |
| 新商品 100-1000 个 | 增量 LoRA 微调 |
| 新商品 > 1000 个 | 考虑全量重训 |
| 新类别出现 | 必须训练（至少 LoRA） |
| 用户行为分布变化 | 触发全量重训 |

---

## 5. Elasticsearch 索引

### 5.1 索引结构

ES 存储商品详情，支持两种查询：

| 查询类型 | 用途 | API |
|---------|------|-----|
| mget | 批量精确回查（按 ASIN） | `GET /products/_mget` |
| multi_match | 全文搜索（按关键词） | `POST /products/_search` |

### 5.2 新商品索引

必须更新，否则新商品无法被搜索和回查。

```bash
# 方式1: 全量重新导入（简单但耗时）
python es_client/scripts/bulk_index_products.py

# 方式2: 增量导入（需要新脚本）
python es_client/scripts/bulk_index_products.py --incremental --since "2026-06-23"
```

### 5.3 索引更新流程

```
1. 读取新产品数据（products.jsonl）
2. 读取 SID 映射（sid_mapping.json）
3. 构造 ES 文档: {asin, title, description, category, brand, price, sid}
4. 批量写入 ES: bulk API, chunk_size=500
5. 验证索引: 搜索新商品标题，确认可搜到
```

---

## 6. Milvus 向量索引

### 6.1 向量索引的作用

Milvus 存储商品的语义向量（768维，bge-base-en-v1.5），支持语义搜索：

| 查询类型 | 用途 | 说明 |
|---------|------|------|
| COSINE | 语义相似搜索 | 基于 embedding 余弦相似度 |
| hybrid | 混合搜索 | ES BM25 + Milvus 向量，RRF 融合 |

### 6.2 新商品向量索引

必须更新，否则新商品无法被语义搜索。

```bash
# 方式1: 全量重建（推荐，保证一致性）
python scripts/build_embeddings.py

# 方式2: 增量插入（需自行实现）
# 读取新商品 → 生成 embedding → 插入 Milvus
```

### 6.3 向量索引更新流程

```
1. 读取新产品数据（products.jsonl）
2. 清洗 HTML 标签（description 字段）
3. 使用 bge-base-en-v1.5 生成 768 维向量
4. 批量写入 Milvus: insert API, batch_size=500
5. 验证索引: 向量搜索新商品标题，确认可搜到
```

---

## 7. 完整更新流程

### 7.1 新增 1,000 个商品的标准流程

```
Step 1: 数据预处理
  ├─ 原始数据 → products.jsonl（追加新商品）
  └─ 耗时: 1-2 分钟

Step 2: RQ-VAE 编码（不重训）
  ├─ 用现有模型编码新商品文本 → 生成 SID
  ├─ 更新 sid_mapping.json（追加新映射）
  └─ 耗时: 1-2 分钟

Step 3: 更新 ES 索引
  ├─ 批量导入新商品到 ES
  ├─ 包含 SID 字段（用于推荐回查）
  └─ 耗时: 10-30 秒

Step 4: 更新 Milvus 向量索引
  ├─ 用 bge-base-en-v1.5 编码新商品文本
  ├─ 批量插入 Milvus（含元数据）
  └─ 耗时: 1-3 分钟

Step 5: 重启后端服务
  ├─ 重新加载 SID 映射到内存
  ├─ 重新加载商品缓存到内存
  └─ 耗时: 1-3 秒

Step 6: [可选] 增量微调 Qwen2.5
  ├─ 用新交互数据 LoRA 微调
  ├─ 保存新 adapter
  └─ 耗时: 数小时（取决于 GPU）
```

### 7.2 脚本化更新

```bash
# 一键更新脚本（示例）
#!/bin/bash
echo "Step 1: 预处理新商品数据..."
python data/scripts/preprocess_products.py --incremental

echo "Step 2: 编码新商品 SID..."
python data/scripts/build_sid_mapping.py --incremental

echo "Step 3: 更新 ES 索引..."
python es_client/scripts/bulk_index_products.py --incremental

echo "Step 4: 更新 Milvus 向量索引..."
python scripts/build_embeddings.py

echo "Step 5: 重启后端..."
# systemctl restart recommendation-api
echo "完成"
```

---

## 8. 增量更新 vs 全量重训

### 8.1 决策矩阵

| 场景 | RQ-VAE | SID 映射 | Qwen2.5 | ES | Milvus |
|------|--------|---------|---------|-----|--------|
| 少量同类商品新增 | 不重训 | 增量更新 | 不训练 | 增量导入 | 增量插入 |
| 大量同类商品新增 | 不重训 | 全量重建 | LoRA 微调 | 全量导入 | 全量重建 |
| 新类别商品新增 | 考虑重训 | 全量重建 | LoRA 微调 | 全量导入 | 全量重建 |
| 用户行为分布变化 | 不变 | 不变 | 全量重训 | 不变 | 不变 |
| 商品下架 | 不变 | 移除映射 | 不训练 | 删除文档 | 删除向量 |

### 8.2 成本对比

| 操作 | GPU 需求 | 时间 | 人力 |
|------|---------|------|------|
| RQ-VAE 编码新商品（不重训） | 无 | 分钟级 | 低 |
| RQ-VAE 全量重训 | 需要 | 天级 | 高 |
| SID 映射重建 | 无 | 秒级 | 低 |
| Qwen2.5 LoRA 微调 | 需要 | 小时级 | 中 |
| Qwen2.5 全量重训 | 需要 | 天级 | 高 |
| ES 增量导入 | 无 | 分钟级 | 低 |
| ES 全量导入 | 无 | 十分钟级 | 低 |
| Milvus 增量插入 | 无 | 分钟级 | 低 |
| Milvus 全量重建（含 embedding） | 推荐 CPU/GPU | 分钟-小时级 | 低 |

### 8.3 监控指标

更新后需监控以下指标，判断是否需要进一步调整：

| 指标 | 阈值 | 说明 |
|------|------|------|
| SID 碰撞率 | < 40% | 过高说明 codebook 不足 |
| 新商品推荐覆盖率 | > 80% | 新商品被推荐的比例 |
| 推荐点击率 | 不下降 | 更新后用户体验 |
| 搜索召回率 | > 90% | 新商品能被搜到 |
| 向量搜索召回率 | > 85% | 新商品能被语义搜索到 |
| 混合搜索点击率 | > 关键词搜索 | hybrid 模式效果优于纯关键词 |

---

*文档版本: v1.1 | 最后更新: 2026-06-23*
