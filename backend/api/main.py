from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routers import recommend, products, behavior
from api.middleware.logging_middleware import LoggingMiddleware, metrics
from services.sid_service import SIDService
from services.cache_service import CacheService
from services.embedding_service import EmbeddingService
from services.vector_service import VectorService
from es_client.client import ESClient
from models.recommender_inference import RecommenderInference
from config.settings import settings

_sid_svc = SIDService()
_es_client = ESClient()
_recommender = RecommenderInference()
_cache_svc = CacheService()
_embedding_svc = EmbeddingService()
_vector_svc = VectorService(embedding_svc=_embedding_svc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _sid_svc.initialize()
    await _cache_svc.initialize()
    _recommender.load(list(_sid_svc.sid2asin.keys()))
    _embedding_svc.load()
    await _vector_svc.initialize()
    app.state.sid_svc = _sid_svc
    app.state.es_client = _es_client
    app.state.recommender = _recommender
    app.state.cache_svc = _cache_svc
    app.state.embedding_svc = _embedding_svc
    app.state.vector_svc = _vector_svc
    yield
    await _vector_svc.close()
    await _cache_svc.close()
    await _es_client.close()


app = FastAPI(
    title="个性化商品推荐系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 中间件
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(recommend.router, prefix="/api/v1", tags=["推荐"])
app.include_router(products.router, prefix="/api/v1", tags=["商品"])
app.include_router(behavior.router, prefix="/api/v1", tags=["行为"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def get_metrics():
    """获取系统指标"""
    return metrics.get_stats()
