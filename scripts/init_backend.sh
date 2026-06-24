#!/bin/bash
set -e

echo "=== Step 1: 数据预处理 ==="
cd backend
python data/scripts/preprocess_products.py
python data/scripts/preprocess_interactions.py
python data/scripts/build_sid_mapping.py

echo "=== Step 2: 等待 Elasticsearch 就绪 ==="
until curl -sf http://localhost:9200/_cluster/health | grep -qE 'green|yellow'; do
    echo "  等待 ES 启动..."; sleep 3
done
echo "  ES 就绪 ✅"

echo "=== Step 3: 创建索引并批量导入商品 ==="
python elasticsearch/scripts/create_index.py
python elasticsearch/scripts/bulk_index_products.py

echo "=== 后端初始化完成 ✅ ==="
