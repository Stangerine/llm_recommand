import pytest
from unittest.mock import AsyncMock, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.search_service import _rrf_fusion as rrf_fusion


class TestRRFFusion:
    """Test Reciprocal Rank Fusion logic."""

    def test_rrf_basic_merge(self):
        """RRF merges results from two sources correctly."""
        es = [
            {"asin": "A", "title": "A"},
            {"asin": "B", "title": "B"},
        ]
        vector = [
            {"asin": "B", "title": "B"},
            {"asin": "C", "title": "C"},
        ]
        result = rrf_fusion(es, vector, k=60, limit=3)
        asins = [r["asin"] for r in result]
        # B appears in both, should rank highest
        assert asins[0] == "B"
        assert len(result) == 3

    def test_rrf_score_calculation(self):
        """RRF score = sum(1/(k+rank+1)) for each source."""
        es = [{"asin": "A", "title": "A"}]  # rank 0
        vector = [{"asin": "A", "title": "A"}]  # rank 0
        result = rrf_fusion(es, vector, k=60, limit=1)
        expected = 1.0 / (60 + 1) + 1.0 / (60 + 1)
        assert abs(result[0]["rrf_score"] - expected) < 1e-9

    def test_rrf_preserves_product_info(self):
        """RRF preserves product fields from the source."""
        es = [{"asin": "A", "title": "ES Title", "price": 10.0}]
        vector = [{"asin": "A", "title": "Vector Title", "price": 10.0}]
        result = rrf_fusion(es, vector, limit=1)
        # ES result is added first, so it should be used
        assert result[0]["title"] == "ES Title"

    def test_rrf_empty_es(self):
        """RRF works when ES returns nothing."""
        es = []
        vector = [{"asin": "A", "title": "A"}, {"asin": "B", "title": "B"}]
        result = rrf_fusion(es, vector, limit=5)
        assert len(result) == 2

    def test_rrf_empty_vector(self):
        """RRF works when vector returns nothing."""
        es = [{"asin": "A", "title": "A"}]
        vector = []
        result = rrf_fusion(es, vector, limit=5)
        assert len(result) == 1

    def test_rrf_limit_respected(self):
        """RRF respects the limit parameter."""
        es = [{"asin": f"P{i}", "title": f"P{i}"} for i in range(20)]
        vector = [{"asin": f"P{i}", "title": f"P{i}"} for i in range(20)]
        result = rrf_fusion(es, vector, limit=5)
        assert len(result) == 5

    def test_rrf_ranking_order(self):
        """Higher ranked items in both lists get higher RRF scores."""
        es = [
            {"asin": "X", "title": "X"},  # rank 0 in ES
            {"asin": "Y", "title": "Y"},  # rank 1 in ES
        ]
        vector = [
            {"asin": "Y", "title": "Y"},  # rank 0 in vector
            {"asin": "X", "title": "X"},  # rank 1 in vector
        ]
        result = rrf_fusion(es, vector, k=60, limit=2)
        # Both appear in both lists at different ranks
        # X: 1/(60+1) + 1/(60+2) = 0.01639 + 0.01613 = 0.03252
        # Y: 1/(60+2) + 1/(60+1) = 0.01613 + 0.01639 = 0.03252
        # Equal scores, order preserved from es
        assert result[0]["asin"] in ("X", "Y")
        assert result[1]["asin"] in ("X", "Y")
