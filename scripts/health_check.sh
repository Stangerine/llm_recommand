#!/bin/bash

echo "=== 健康检查 ==="

# 检查后端 API
echo -n "后端 API (http://localhost:8000/health): "
if curl -sf http://localhost:8000/health | grep -q '"status":"ok"'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 检查 Elasticsearch
echo -n "Elasticsearch (http://localhost:9200): "
if curl -sf http://localhost:9200/_cluster/health | grep -qE 'green|yellow'; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 检查 Redis
echo -n "Redis (localhost:6379): "
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

# 检查前端
echo -n "前端 (http://localhost:80): "
if curl -sf http://localhost:80 > /dev/null; then
    echo "✅ 正常"
else
    echo "❌ 异常"
fi

echo "=== 检查完成 ==="
