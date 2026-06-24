from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class EmbeddingService:
    """bge-base-en-v1.5 embedding service with simulation fallback."""

    def __init__(self):
        self._model = None
        self._available = False

    def load(self):
        """Load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                settings.embedding_model,
                device=settings.model_device if settings.model_device != "cuda" else "cpu",
            )
            self._available = True
            print(f"[OK] Embedding model loaded: {settings.embedding_model}")
        except Exception as e:
            print(f"[WARN] Embedding model load failed: {e}, using simulation mode")
            self._model = None
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Batch encode texts into normalized vectors."""
        if not texts:
            return []
        if self._model is not None:
            embeddings = self._model.encode(
                texts,
                batch_size=settings.embedding_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.tolist()
        # simulation: deterministic random vectors seeded by text hash
        return [self._sim_vector(t) for t in texts]

    def encode_query(self, query: str) -> list[float]:
        """Encode a single query string."""
        if self._model is not None:
            embedding = self._model.encode(
                [query],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding[0].tolist()
        return self._sim_vector(query)

    @staticmethod
    def _sim_vector(text: str) -> list[float]:
        """Generate a deterministic pseudo-vector for simulation."""
        rng = random.Random(hash(text))
        vec = [rng.gauss(0, 1) for _ in range(settings.embedding_dim)]
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec]
