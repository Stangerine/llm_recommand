import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.embedding_service import EmbeddingService


class TestEmbeddingServiceSimulation:
    """Test embedding service in simulation mode (no model loaded)."""

    def setup_method(self):
        self.svc = EmbeddingService()

    def test_sim_vector_deterministic(self):
        """Same text produces same vector."""
        v1 = EmbeddingService._sim_vector("hello world")
        v2 = EmbeddingService._sim_vector("hello world")
        assert v1 == v2

    def test_sim_vector_different_texts(self):
        """Different texts produce different vectors."""
        v1 = EmbeddingService._sim_vector("hello")
        v2 = EmbeddingService._sim_vector("world")
        assert v1 != v2

    def test_sim_vector_normalized(self):
        """Simulation vectors are unit length."""
        vec = EmbeddingService._sim_vector("test text")
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_sim_vector_dimension(self):
        """Simulation vectors have correct dimension."""
        vec = EmbeddingService._sim_vector("test")
        assert len(vec) == 768

    def test_encode_simulation(self):
        """encode() works in simulation mode."""
        vectors = self.svc.encode(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 768
        assert len(vectors[1]) == 768

    def test_encode_empty(self):
        """encode() returns empty list for empty input."""
        assert self.svc.encode([]) == []

    def test_encode_query_simulation(self):
        """encode_query() works in simulation mode."""
        vec = self.svc.encode_query("test query")
        assert len(vec) == 768

    def test_is_available_false(self):
        """is_available() returns False when model not loaded."""
        assert self.svc.is_available() is False
