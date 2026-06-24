import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _has_pymilvus() -> bool:
    try:
        import pymilvus  # noqa: F401
        return True
    except ImportError:
        return False


from services.vector_service import VectorService


class TestVectorServiceUnavailable:
    """Test vector service when Milvus is not available."""

    def setup_method(self):
        self.svc = VectorService()

    def test_is_available_false_when_not_initialized(self):
        assert self.svc.is_available() is False

    def test_search_returns_empty_when_unavailable(self):
        result = self.svc.search([0.1] * 768, top_k=5)
        assert result == []

    def test_insert_raises_when_unavailable(self):
        with pytest.raises(RuntimeError, match="not available"):
            self.svc.insert_batch([{"asin": "B001"}])


@pytest.mark.skipif(
    not _has_pymilvus(),
    reason="pymilvus not installed",
)
class TestVectorServiceWithMock:
    """Test vector service with mocked Milvus client."""

    def setup_method(self):
        self.mock_embedding = MagicMock()
        self.mock_embedding.encode = MagicMock(return_value=[[0.1] * 768])
        self.svc = VectorService(embedding_svc=self.mock_embedding)

    @patch("pymilvus.MilvusClient")
    def test_search_returns_results(self, mock_milvus_cls):
        mock_client = MagicMock()
        mock_milvus_cls.return_value = mock_client
        mock_client.has_collection.return_value = True
        mock_client.get_collection_stats.return_value = {"row_count": 100}

        mock_client.search.return_value = [[
            {"id": "B001", "distance": 0.95, "entity": {"title": "Test", "category": "Safety"}},
        ]]

        import asyncio
        asyncio.run(self.svc.initialize())

        results = self.svc.search([0.1] * 768, top_k=5)
        assert len(results) == 1
        assert results[0]["asin"] == "B001"
        assert results[0]["score"] == 0.95

    @patch("pymilvus.MilvusClient")
    def test_insert_batch_calls_client(self, mock_milvus_cls):
        mock_client = MagicMock()
        mock_milvus_cls.return_value = mock_client
        mock_client.has_collection.return_value = True
        mock_client.get_collection_stats.return_value = {"row_count": 0}

        import asyncio
        asyncio.run(self.svc.initialize())

        products = [{"asin": "B001", "title": "Test", "description": "Desc", "category": "Cat", "brand": "B", "price": 10.0, "rating": 4.0, "rating_count": 5}]
        self.svc.insert_batch(products)

        mock_client.insert.assert_called_once()
        call_args = mock_client.insert.call_args
        assert call_args.kwargs["collection_name"] == "products"
        assert len(call_args.kwargs["data"]) == 1
        assert call_args.kwargs["data"][0]["asin"] == "B001"
