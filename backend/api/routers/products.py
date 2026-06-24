import json
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException, Query

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.products import ProductDetail, SearchResponse, ProductListResponse
from config.settings import settings

router = APIRouter()


def rrf_fusion(
    es_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
    limit: int = 10,
) -> list[dict]:
    """Reciprocal Rank Fusion merging ES and Milvus results."""
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


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = None,
):
    """获取商品列表（分页）"""
    es_client = request.app.state.es_client

    # 从本地缓存获取商品
    products = list(es_client._products_cache.values())

    # 按分类过滤
    if category:
        products = [p for p in products if category.lower() in p.get('category', '').lower()]

    # 计算分页
    total = len(products)
    start = (page - 1) * page_size
    end = start + page_size
    page_products = products[start:end]

    return ProductListResponse(
        products=[ProductDetail(**p) for p in page_products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/products/search", response_model=SearchResponse)
async def search_products(
    request: Request,
    q: str = Query(..., min_length=1),
    category: str | None = None,
    size: int = Query(default=20, ge=1, le=100),
    mode: str = Query(default="keyword", pattern="^(keyword|vector|hybrid)$"),
):
    """搜索商品 - keyword / vector / hybrid 模式"""
    es_client = request.app.state.es_client
    embedding_svc = request.app.state.embedding_svc
    vector_svc = request.app.state.vector_svc

    if mode == "vector":
        if not vector_svc.is_available():
            raise HTTPException(503, "Vector search not available")
        query_vec = embedding_svc.encode_query(q)
        hits = vector_svc.search(query_vec, top_k=size, category=category)
        return SearchResponse(
            results=[ProductDetail(**h) for h in hits],
            total=len(hits),
            query=q,
            search_mode="vector",
        )

    if mode == "hybrid":
        # over-fetch from both sources for fusion
        fetch_size = size * 2
        es_results = await es_client.search_products(q, size=fetch_size, category=category)

        vector_hits: list[dict] = []
        if vector_svc.is_available():
            query_vec = embedding_svc.encode_query(q)
            vector_hits = vector_svc.search(query_vec, top_k=fetch_size, category=category)

        # fallback to keyword-only if vector unavailable
        if not vector_hits:
            return SearchResponse(
                results=[ProductDetail(**p) for p in es_results[:size]],
                total=min(len(es_results), size),
                query=q,
                search_mode="keyword",
            )

        fused = rrf_fusion(es_results, vector_hits, limit=size)
        return SearchResponse(
            results=[ProductDetail(**h) for h in fused],
            total=len(fused),
            query=q,
            search_mode="hybrid",
        )

    # default: keyword
    results = await es_client.search_products(q, size=size, category=category)
    return SearchResponse(
        results=[ProductDetail(**p) for p in results],
        total=len(results),
        query=q,
        search_mode="keyword",
    )


@router.get("/products/{asin}", response_model=ProductDetail)
async def get_product(asin: str, request: Request):
    """获取单个商品详情"""
    es_client = request.app.state.es_client
    products = await es_client.get_products_by_asins([asin])
    if not products:
        raise HTTPException(404, f"商品 {asin} 不存在")
    return ProductDetail(**products[0])
