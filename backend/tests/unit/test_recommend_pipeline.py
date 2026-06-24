import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.recommend_pipeline import RecommendPipeline


@pytest.fixture
def mock_sid_service():
    svc = MagicMock()
    svc.asin2sid = {"B001": "1_2_3_4", "B002": "5_6_7_8", "B003": "9_10_11_12"}
    svc.sid2asin = {v: k for k, v in svc.asin2sid.items()}
    svc.asins_to_sids = MagicMock(return_value=["1_2_3_4", "5_6_7_8"])
    svc.sids_to_asins = MagicMock(return_value=["B001", "B002", "B003"])
    return svc


@pytest.fixture
def mock_es_client():
    client = AsyncMock()
    client.get_products_by_asins = AsyncMock(return_value=[
        {"asin": "B001", "title": "Product 1", "price": 10.0},
        {"asin": "B002", "title": "Product 2", "price": 20.0},
        {"asin": "B003", "title": "Product 3", "price": 30.0},
    ])
    return client


@pytest.fixture
def mock_recommender():
    rec = MagicMock()
    rec.predict = MagicMock(return_value=["1_2_3_4", "5_6_7_8", "9_10_11_12"])
    return rec


@pytest.fixture
def pipeline(mock_sid_service, mock_es_client, mock_recommender):
    return RecommendPipeline(mock_sid_service, mock_es_client, mock_recommender)


@pytest.mark.asyncio
async def test_recommend_returns_products(pipeline, mock_sid_service, mock_recommender, mock_es_client):
    result = await pipeline.recommend(["B001", "B002"], top_k=3)

    assert len(result) == 3
    assert result[0]["asin"] == "B001"
    mock_sid_service.asins_to_sids.assert_called_once_with(["B001", "B002"])
    mock_recommender.predict.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_respects_top_k(pipeline, mock_es_client):
    mock_es_client.get_products_by_asins = AsyncMock(return_value=[
        {"asin": "B001", "title": "Product 1"},
    ])
    result = await pipeline.recommend(["B001"], top_k=1)
    assert len(result) <= 1


@pytest.mark.asyncio
async def test_recommend_raises_on_empty_sids(pipeline, mock_sid_service):
    mock_sid_service.asins_to_sids = MagicMock(return_value=[])

    with pytest.raises(ValueError, match="历史商品均无对应 SID"):
        await pipeline.recommend(["INVALID_ASIN"])


@pytest.mark.asyncio
async def test_recommend_raises_on_empty_candidates(pipeline, mock_recommender, mock_sid_service):
    mock_recommender.predict = MagicMock(return_value=[])
    mock_sid_service.sids_to_asins = MagicMock(return_value=[])

    with pytest.raises(ValueError, match="模型未生成有效候选"):
        await pipeline.recommend(["B001"])


@pytest.mark.asyncio
async def test_recommend_preserves_order(pipeline, mock_es_client):
    # 返回的顺序应该与候选ASIN顺序一致
    mock_es_client.get_products_by_asins = AsyncMock(return_value=[
        {"asin": "B003", "title": "Product 3"},
        {"asin": "B001", "title": "Product 1"},
        {"asin": "B002", "title": "Product 2"},
    ])

    result = await pipeline.recommend(["B001"], top_k=3)
    # 验证排序
    asins = [p["asin"] for p in result]
    assert asins == ["B001", "B002", "B003"]
