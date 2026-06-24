import hashlib
import time

from fastapi import APIRouter, Request, HTTPException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.recommend import RecommendRequest, RecommendResponse, ProductInfo
from api.middleware.logging_middleware import metrics
import structlog

router = APIRouter()
logger = structlog.get_logger()


def _hash_history(asins: list[str]) -> str:
    """计算历史列表的哈希值，用于缓存 key"""
    return hashlib.md5(",".join(sorted(asins)).encode()).hexdigest()[:12]


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest, request: Request):
    sid_svc = request.app.state.sid_svc
    es_client = request.app.state.es_client
    recommender = request.app.state.recommender
    cache_svc = request.app.state.cache_svc

    # 0. 检查缓存
    history_hash = _hash_history(req.history_asins)
    cached = await cache_svc.get_recommend_cache(req.user_id, history_hash)
    if cached:
        logger.info("recommend_cache_hit", user_id=req.user_id)
        return RecommendResponse(**cached)

    # 1. ASIN → SID 序列
    start_sid = time.time()
    history_sids = sid_svc.asins_to_sids(req.history_asins)
    sid_hit = len(history_sids) > 0
    metrics.record_sid_hit(sid_hit)

    if not history_sids:
        raise HTTPException(
            status_code=400,
            detail="历史商品均无对应 SID，请检查输入 ASIN"
        )

    # 2. 模型推理 → 候选 SID
    start_model = time.time()
    candidate_sids = recommender.predict(history_sids)
    model_ms = (time.time() - start_model) * 1000
    metrics.record_model_inference(model_ms)

    logger.info("recommend_debug", history_sids=history_sids, candidate_sids=candidate_sids)

    # 3. SID → ASIN
    candidate_asins = sid_svc.sids_to_asins(candidate_sids)
    logger.info("recommend_sid_to_asin", candidate_asins=candidate_asins, count=len(candidate_asins))
    if not candidate_asins:
        metrics.record_recommend_empty()
        raise HTTPException(
            status_code=500,
            detail="模型未生成有效候选商品，请重试"
        )

    # 4. ES 批量回查商品详情
    start_es = time.time()
    products = await es_client.get_products_by_asins(candidate_asins[: req.top_k])
    es_ms = (time.time() - start_es) * 1000
    metrics.record_es_query(es_ms)

    # 5. 保持模型打分顺序排序
    order = {asin: i for i, asin in enumerate(candidate_asins)}
    products.sort(key=lambda p: order.get(p["asin"], 999))

    if not products:
        metrics.record_recommend_empty()

    result = RecommendResponse(
        user_id=req.user_id,
        recommendations=[ProductInfo(**p) for p in products],
        total=len(products),
    )

    # 6. 写入缓存
    await cache_svc.set_recommend_cache(
        req.user_id, history_hash, result.model_dump()
    )

    logger.info(
        "recommend_done",
        user_id=req.user_id,
        returned=len(products),
        model_ms=round(model_ms, 2),
        es_ms=round(es_ms, 2),
    )

    return result
