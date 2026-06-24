import pytest
from httpx import AsyncClient
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api.main import app


@pytest.mark.asyncio
async def test_health():
    """健康检查接口返回 200"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics():
    """指标接口返回统计数据"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "recommend_request_total" in data
    assert "sid_hit_rate" in data


@pytest.mark.asyncio
async def test_behavior_endpoint():
    """行为上报接口正常工作"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/behavior",
            json={
                "user_id": "test_user",
                "asin": "B001XXXXX",
                "action_type": "click",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_recommend_requires_history():
    """推荐接口要求至少一个历史 ASIN"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/recommend",
            json={
                "user_id": "test_user",
                "history_asins": [],
                "top_k": 5,
            },
        )
    assert resp.status_code == 422  # Validation error: min_length=1


@pytest.mark.asyncio
async def test_recommend_invalid_asins_returns_400():
    """无效 ASIN 返回 400"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/recommend",
            json={
                "user_id": "test_user",
                "history_asins": ["INVALID_ASIN_XYZ"],
            },
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_search_requires_query():
    """搜索接口要求查询参数"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/products/search")
    assert resp.status_code == 422  # Missing required query param


@pytest.mark.asyncio
async def test_product_not_found():
    """不存在的商品返回 404"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/products/NONEXISTENT")
    assert resp.status_code == 404
