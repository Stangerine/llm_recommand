from fastapi import APIRouter, Depends, HTTPException, Query, Request

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.dependencies import get_search_service
from api.schemas.products import ProductDetail, SearchResponse, ProductListResponse
from services.search_service import SearchService

router = APIRouter()


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = None,
):
    """获取商品列表（分页）"""
    vector_svc = request.app.state.vector_svc

    page_products, total = vector_svc.list_products(
        page=page, page_size=page_size, category=category
    )

    return ProductListResponse(
        products=[ProductDetail(**p) for p in page_products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/products/search", response_model=SearchResponse)
async def search_products(
    q: str = Query(..., min_length=1),
    category: str | None = None,
    size: int = Query(default=20, ge=1, le=100),
    mode: str = Query(default="hybrid", pattern="^(keyword|vector|hybrid)$"),
    search_svc: SearchService = Depends(get_search_service),
):
    """搜索商品 - keyword / vector / hybrid 模式（默认 hybrid）"""
    try:
        results, effective_mode = await search_svc.search(
            query=q, mode=mode, category=category, size=size
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return SearchResponse(
        results=[ProductDetail(**p) for p in results],
        total=len(results),
        query=q,
        search_mode=effective_mode,
    )


@router.get("/products/{asin}", response_model=ProductDetail)
async def get_product(asin: str, request: Request):
    """获取单个商品详情"""
    es_client = request.app.state.es_client
    products = await es_client.get_products_by_asins([asin])
    if not products:
        raise HTTPException(404, f"商品 {asin} 不存在")
    return ProductDetail(**products[0])
