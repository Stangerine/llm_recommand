import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.search_service import SearchService, _rrf_fusion


# ── fixtures ──────────────────────────────────────────────────

@pytest.fixture
def mock_es_client():
    client = AsyncMock()
    client.search_products = AsyncMock(return_value=[
        {"asin": "B001", "title": "Safety Gloves", "description": "Heavy duty"},
        {"asin": "B002", "title": "Safety Helmet", "description": "Industrial"},
    ])
    client.get_products_by_asins = AsyncMock(return_value=[
        {"asin": "B001", "title": "Safety Gloves", "brand": "TestBrand"},
    ])
    return client


@pytest.fixture
def mock_embedding_svc():
    svc = MagicMock()
    svc.encode_query = MagicMock(return_value=[0.1] * 768)
    return svc


@pytest.fixture
def mock_vector_svc():
    svc = MagicMock()
    svc.is_available = MagicMock(return_value=True)
    svc.search = MagicMock(return_value=[
        {"asin": "B003", "title": "Vector Result", "score": 0.95},
        {"asin": "B001", "title": "Safety Gloves (vec)", "score": 0.88},
    ])
    return svc


@pytest.fixture
def search_service(mock_es_client, mock_embedding_svc, mock_vector_svc):
    return SearchService(mock_es_client, mock_embedding_svc, mock_vector_svc)


# ── RRF fusion unit ───────────────────────────────────────────

def test_rrf_fusion_merges_both_lists():
    es = [{"asin": "A", "title": "A-es"}, {"asin": "B", "title": "B-es"}]
    vec = [{"asin": "C", "title": "C-vec"}, {"asin": "A", "title": "A-vec"}]
    fused = _rrf_fusion(es, vec, k=60, limit=3)
    assert len(fused) == 3
    # A appears in both lists — should rank highest
    assert fused[0]["asin"] == "A"


def test_rrf_fusion_handles_empty_vector():
    es = [{"asin": "A"}, {"asin": "B"}]
    fused = _rrf_fusion(es, [], limit=2)
    assert len(fused) == 2


# ── keyword mode ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_keyword_search(search_service, mock_es_client):
    results, mode = await search_service.search("gloves", mode="keyword")
    assert mode == "keyword"
    assert len(results) == 2
    mock_es_client.search_products.assert_called_once_with("gloves", size=20, category=None)


@pytest.mark.asyncio
async def test_keyword_search_with_category(search_service, mock_es_client):
    await search_service.search("gloves", mode="keyword", category="Safety")
    mock_es_client.search_products.assert_called_once_with("gloves", size=20, category="Safety")


# ── vector mode ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vector_search(search_service, mock_vector_svc, mock_embedding_svc):
    results, mode = await search_service.search("test", mode="vector")
    assert mode == "vector"
    assert len(results) == 2
    assert results[0]["asin"] == "B003"
    mock_embedding_svc.encode_query.assert_called_once_with("test")
    mock_vector_svc.search.assert_called_once()


@pytest.mark.asyncio
async def test_vector_search_unavailable(search_service, mock_vector_svc):
    mock_vector_svc.is_available.return_value = False
    with pytest.raises(RuntimeError, match="Vector search not available"):
        await search_service.search("test", mode="vector")


# ── hybrid mode (default) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_hybrid_search(search_service):
    results, mode = await search_service.search("gloves")
    assert mode == "hybrid"
    assert len(results) <= 20  # respects size limit


@pytest.mark.asyncio
async def test_hybrid_falls_back_to_keyword_when_vector_unavailable(
    search_service, mock_vector_svc
):
    mock_vector_svc.is_available.return_value = False
    mock_vector_svc.search.return_value = []
    results, mode = await search_service.search("gloves")
    # hybrid degraded to keyword
    assert mode == "keyword"


# ── get_by_asins ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_by_asins(search_service, mock_es_client):
    results = await search_service.get_by_asins(["B001"])
    assert len(results) == 1
    assert results[0]["asin"] == "B001"
    mock_es_client.get_products_by_asins.assert_called_once_with(["B001"])


@pytest.mark.asyncio
async def test_get_by_asins_empty(search_service, mock_es_client):
    mock_es_client.get_products_by_asins = AsyncMock(return_value=[])
    results = await search_service.get_by_asins(["INVALID"])
    assert len(results) == 0
