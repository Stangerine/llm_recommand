import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from es_client.client import ESClient
from services.embedding_service import EmbeddingService
from services.vector_service import VectorService


def _rrf_fusion(
    es_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
    limit: int = 10,
) -> list[dict]:
    """Reciprocal Rank Fusion — merge ES and Milvus result lists."""
    scores: dict[str, float] = {}
    asin_to_product: dict[str, dict] = {}

    for rank, item in enumerate(es_results):
        asin = item["asin"]
        scores[asin] = scores.get(asin, 0) + 1.0 / (k + rank + 1)
        asin_to_product[asin] = item

    for rank, item in enumerate(vector_results):
        asin = item["asin"]
        scores[asin] = scores.get(asin, 0) + 1.0 / (k + rank + 1)
        if asin not in asin_to_product:
            asin_to_product[asin] = item

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    results = []
    for asin, score in ranked[:limit]:
        product = asin_to_product[asin].copy()
        product["rrf_score"] = score
        results.append(product)
    return results


class SearchService:
    """Unified search — keyword (ES), vector (Milvus), and hybrid with RRF."""

    def __init__(
        self,
        es_client: ESClient,
        embedding_svc: EmbeddingService,
        vector_svc: VectorService,
    ):
        self._es = es_client
        self._embedding = embedding_svc
        self._vector = vector_svc

    async def search(
        self,
        query: str,
        mode: str = "hybrid",
        category: str | None = None,
        size: int = 20,
    ) -> tuple[list[dict], str]:
        """
        Search products.

        Returns (results, effective_mode) where effective_mode may differ
        from requested mode when vector search is unavailable.
        """
        if mode == "keyword":
            results = await self._es.search_products(query, size=size, category=category)
            return results, "keyword"

        if mode == "vector":
            if not self._vector.is_available():
                raise RuntimeError("Vector search not available")
            query_vec = self._embedding.encode_query(query)
            hits = self._vector.search(query_vec, top_k=size, category=category)
            return hits, "vector"

        # hybrid (default): ES + vector with RRF fusion
        fetch_size = size * 2
        es_results = await self._es.search_products(query, size=fetch_size, category=category)

        vector_hits: list[dict] = []
        if self._vector.is_available():
            query_vec = self._embedding.encode_query(query)
            vector_hits = self._vector.search(query_vec, top_k=fetch_size, category=category)

        if not vector_hits:
            return es_results[:size], "keyword"

        fused = _rrf_fusion(es_results, vector_hits, limit=size)
        return fused, "hybrid"

    async def get_by_asins(self, asins: list[str]) -> list[dict]:
        """Batch fetch products by ASIN (ES only, fallback to vector)."""
        return await self._es.get_products_by_asins(asins)
