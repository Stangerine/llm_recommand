import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class ESClient:
    """商品客户端：Milvus 主存储 + Redis 热点缓存 + ES 全文检索"""

    def __init__(self, vector_service=None, cache_service=None):
        self._vector_svc = vector_service
        self._cache_svc = cache_service
        self.use_simulation = True  # 默认不连 ES
        self.client = None

        # 尝试连接 ES（用于全文检索）
        try:
            from elasticsearch import AsyncElasticsearch
            self.client = AsyncElasticsearch(
                settings.es_host, request_timeout=settings.es_timeout
            )
            self.use_simulation = False
        except Exception as e:
            print(f"[WARN] ES 连接失败: {e}，全文检索降级")

    async def get_products_by_asins(self, asins: list[str]) -> list[dict]:
        """批量精确回查——推荐流水线末端核心方法。"""
        result_map = {}
        missing = list(asins)

        # 1. 批量查 Redis
        if self._cache_svc and missing:
            cached = await self._cache_svc.get_products_batch(missing)
            result_map.update(cached)
            missing = [a for a in missing if a not in cached]

        # 2. 批量查 Milvus
        if self._vector_svc and self._vector_svc.is_available() and missing:
            milvus_results = self._vector_svc.get_by_asins(missing)
            to_cache = {}
            for r in milvus_results:
                asin = r.get("asin", "")
                if asin:
                    result_map[asin] = r
                    to_cache[asin] = r
            if self._cache_svc and to_cache:
                await self._cache_svc.set_products_batch(list(to_cache.values()))
            missing = [a for a in missing if a not in to_cache]

        # 3. ES mget 降级（如果 ES 可用）
        if not self.use_simulation and self.client is not None and missing:
            try:
                resp = await self.client.mget(index=settings.es_index_name, body={"ids": missing})
                for hit in resp["docs"]:
                    if hit.get("found"):
                        result_map[hit["_source"]["asin"]] = hit["_source"]
            except Exception:
                pass

        # 4. 组装结果（保持原顺序）
        return [result_map.get(a, self._placeholder(a)) for a in asins]

    @staticmethod
    def _placeholder(asin: str) -> dict:
        return {
            "asin": asin,
            "title": f"商品 {asin}",
            "description": "",
            "category": "",
            "brand": "",
            "price": None,
            "rating": None,
            "rating_count": 0,
        }

    async def search_products(
        self, query: str, size: int = 10, category: str | None = None
    ) -> list[dict]:
        """全文搜索，供前端搜索页调用。"""
        # 优先使用 ES
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
                    index=settings.es_index_name,
                    body={"query": {"bool": {"must": must}}, "size": size},
                )
                return [hit["_source"] for hit in resp["hits"]["hits"]]
            except Exception as e:
                print(f"ES search 错误: {e}")

        # 降级：从 Milvus 查询后做内存子串匹配
        if self._vector_svc and self._vector_svc.is_available():
            try:
                # 获取一批商品做文本匹配（简单降级）
                all_products, _ = self._vector_svc.list_products(page=1, page_size=500)
                query_lower = query.lower()
                results = []
                for p in all_products:
                    if len(results) >= size:
                        break
                    searchable = f"{p.get('title', '')} {p.get('description', '')} {p.get('brand', '')} {p.get('category', '')}".lower()
                    if query_lower in searchable:
                        if not category or category.lower() in p.get('category', '').lower():
                            results.append(p)
                return results
            except Exception:
                pass

        return []

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()
