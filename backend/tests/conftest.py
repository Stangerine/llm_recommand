import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Mock settings for testing"""
    monkeypatch.setattr("config.settings.settings.sid_mapping_path", "./test_data/sid_mapping.json")
    monkeypatch.setattr("config.settings.settings.products_path", "./test_data/products.jsonl")
    monkeypatch.setattr("config.settings.settings.es_host", "http://localhost:9200")
    monkeypatch.setattr("config.settings.settings.redis_host", "localhost")


@pytest.fixture
def mock_sid_service():
    """Mock SID service"""
    svc = MagicMock()
    svc.asin2sid = {
        "B001": "1_2_3_4",
        "B002": "5_6_7_8",
        "B003": "9_10_11_12",
    }
    svc.sid2asin = {v: k for k, v in svc.asin2sid.items()}
    svc.asins_to_sids = lambda asins: [svc.asin2sid[a] for a in asins if a in svc.asin2sid]
    svc.sids_to_asins = lambda sids: [svc.sid2asin[s] for s in sids if s in svc.sid2asin]
    return svc


@pytest.fixture
def mock_es_client():
    """Mock ES client"""
    client = AsyncMock()
    client.get_products_by_asins = AsyncMock(return_value=[
        {
            "asin": "B001",
            "title": "Test Product 1",
            "description": "Test description",
            "category": "Industrial > Safety",
            "brand": "TestBrand",
            "price": 29.99,
            "rating": 4.5,
            "rating_count": 100,
        }
    ])
    client.search_products = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_recommender():
    """Mock recommender"""
    rec = MagicMock()
    rec.predict = MagicMock(return_value=["1_2_3_4", "5_6_7_8", "9_10_11_12"])
    return rec


@pytest.fixture
def mock_cache_service():
    """Mock cache service"""
    cache = AsyncMock()
    cache.get_recommend_cache = AsyncMock(return_value=None)
    cache.set_recommend_cache = AsyncMock(return_value=True)
    return cache
