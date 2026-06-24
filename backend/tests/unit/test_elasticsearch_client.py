import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.fixture
def mock_es():
    with patch("es_client.client.AsyncElasticsearch") as mock:
        yield mock


@pytest.fixture
def es_client(mock_es):
    from es_client.client import ESClient
    client = ESClient()
    return client


@pytest.mark.asyncio
async def test_get_products_by_asins(es_client, mock_es):
    mock_es.return_value.mget = AsyncMock(return_value={
        "docs": [
            {"_source": {"asin": "B001", "title": "Product 1"}, "found": True},
            {"_source": {"asin": "B002", "title": "Product 2"}, "found": True},
            {"found": False},
        ]
    })

    result = await es_client.get_products_by_asins(["B001", "B002", "INVALID"])
    assert len(result) == 2
    assert result[0]["asin"] == "B001"
    assert result[1]["asin"] == "B002"


@pytest.mark.asyncio
async def test_search_products(es_client, mock_es):
    mock_es.return_value.search = AsyncMock(return_value={
        "hits": {
            "hits": [
                {"_source": {"asin": "B001", "title": "Safety Gloves"}},
                {"_source": {"asin": "B002", "title": "Safety Helmet"}},
            ]
        }
    })

    result = await es_client.search_products("safety", size=10)
    assert len(result) == 2
    assert result[0]["title"] == "Safety Gloves"


@pytest.mark.asyncio
async def test_search_products_with_category(es_client, mock_es):
    mock_es.return_value.search = AsyncMock(return_value={
        "hits": {"hits": [{"_source": {"asin": "B001", "title": "Gloves"}}]}
    })

    result = await es_client.search_products("gloves", category="Safety")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_close(es_client, mock_es):
    mock_es.return_value.close = AsyncMock()
    await es_client.close()
    mock_es.return_value.close.assert_called_once()
