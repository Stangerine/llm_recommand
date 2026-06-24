import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from es_client.client import ESClient


class SearchService:
    """搜索服务，封装 ES 搜索逻辑"""

    def __init__(self, es_client: ESClient):
        self.es = es_client

    async def search(
        self,
        query: str,
        category: str | None = None,
        size: int = 20,
    ) -> list[dict]:
        """搜索商品"""
        return await self.es.search_products(query, size=size, category=category)

    async def get_by_asins(self, asins: list[str]) -> list[dict]:
        """批量获取商品"""
        return await self.es.get_products_by_asins(asins)
