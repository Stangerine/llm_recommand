import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

# 尝试导入 elasticsearch
try:
    from elasticsearch import AsyncElasticsearch
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False


class ESClient:
    """Elasticsearch 客户端封装"""

    def __init__(self):
        self.client = None
        self.index = settings.es_index_name
        self.use_simulation = not ES_AVAILABLE
        self._products_cache = {}  # 本地商品缓存

        if ES_AVAILABLE:
            try:
                self.client = AsyncElasticsearch(
                    settings.es_host, request_timeout=settings.es_timeout
                )
            except Exception as e:
                print(f"[WARN] ES 连接失败: {e}，使用本地数据模式")
                self.use_simulation = True

        # 无论是否连接ES，都加载本地商品数据作为备用
        self._load_local_products()

    def _load_local_products(self):
        """加载本地商品数据到缓存"""
        try:
            products_path = Path(settings.products_path)
            if products_path.exists():
                with open(products_path, encoding='utf-8') as f:
                    for line in f:
                        p = json.loads(line)
                        self._products_cache[p['asin']] = p
                print(f"[OK] 加载本地商品数据: {len(self._products_cache):,} 个")
        except Exception as e:
            print(f"[WARN] 加载本地商品失败: {e}")

    async def get_products_by_asins(self, asins: list[str]) -> list[dict]:
        """mget 批量精确回查——推荐流水线末端核心方法。"""
        # 优先使用本地缓存（数据已加载）
        if self._products_cache:
            results = []
            for asin in asins:
                if asin in self._products_cache:
                    results.append(self._products_cache[asin])
                else:
                    # 找不到时返回基本信息
                    results.append({
                        "asin": asin,
                        "title": f"商品 {asin}",
                        "description": "",
                        "category": "",
                        "brand": "",
                        "price": None,
                        "rating": None,
                        "rating_count": 0,
                    })
            return results

        # 本地缓存为空时使用ES
        if not self.use_simulation and self.client is not None:
            try:
                resp = await self.client.mget(index=self.index, body={"ids": asins})
                return [hit["_source"] for hit in resp["docs"] if hit.get("found")]
            except Exception as e:
                print(f"ES mget 错误: {e}")

        return []

    async def search_products(
        self, query: str, size: int = 10, category: str | None = None
    ) -> list[dict]:
        """全文搜索，供前端搜索页调用。"""
        # 优先使用ES
        if not self.use_simulation and self.client is not None:
            try:
                must = [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "description", "brand^2"],
                        }
                    }
                ]
                if category:
                    must.append({"term": {"category": category}})

                resp = await self.client.search(
                    index=self.index,
                    body={"query": {"bool": {"must": must}}, "size": size},
                )
                return [hit["_source"] for hit in resp["hits"]["hits"]]
            except Exception as e:
                print(f"ES search 错误: {e}")

        # 从本地缓存搜索
        query_lower = query.lower()
        results = []
        for p in self._products_cache.values():
            if len(results) >= size:
                break
            # 简单的文本匹配
            searchable = f"{p.get('title', '')} {p.get('description', '')} {p.get('brand', '')} {p.get('category', '')}".lower()
            if query_lower in searchable:
                results.append(p)

        return results

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()
