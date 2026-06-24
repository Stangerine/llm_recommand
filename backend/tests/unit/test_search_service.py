import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.search_service import SearchService


@pytest.fixture
def mock_es_client():
    client = AsyncMock()
    client.search_products = AsyncMock(return_value=[
        {
            "asin": "B001",
            "title": "Safety Gloves Industrial",
            "description": "Heavy duty safety gloves",
            "category": "Industrial > Safety",
            "brand": "TestBrand",
            "price": 29.99,
            "rating": 4.5,
        },
        {
            "asin": "B002",
            "title": "Safety Helmet",
            "description": "Industrial safety helmet",
            "category": "Industrial > Safety",
            "brand": "TestBrand2",
            "price": 49.99,
            "rating": 4.3,
        },
    ])
    client.get_products_by_asins = AsyncMock(return_value=[
        {
            "asin": "B001",
            "title": "Safety Gloves Industrial",
            "brand": "TestBrand",
        }
    ])
    return client


@pytest.fixture
def search_service(mock_es_client):
    return SearchService(mock_es_client)


@pytest.mark.asyncio
async def test_search_returns_results(search_service, mock_es_client):
    results = await search_service.search("safety gloves")
    assert len(results) == 2
    assert results[0]["asin"] == "B001"
    mock_es_client.search_products.assert_called_once_with("safety gloves", size=20, category=None)


@pytest.mark.asyncio
async def test_search_with_category(search_service, mock_es_client):
    results = await search_service.search("gloves", category="Safety")
    assert len(results) == 2
    mock_es_client.search_products.assert_called_once_with("gloves", size=20, category="Safety")


@pytest.mark.asyncio
async def test_search_with_custom_size(search_service, mock_es_client):
    results = await search_service.search("test", size=5)
    mock_es_client.search_products.assert_called_once_with("test", size=5, category=None)


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
