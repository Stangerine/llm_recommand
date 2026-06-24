from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class VectorService:
    """Milvus vector store for product embeddings."""

    def __init__(self, embedding_svc=None):
        self._client = None
        self._collection = None
        self._available = False
        self._embedding_svc = embedding_svc

    async def initialize(self):
        """Connect to Milvus and ensure collection exists."""
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=settings.milvus_uri)

            if self._client.has_collection(settings.milvus_collection):
                self._client.load_collection(settings.milvus_collection)
                self._available = True
                count = self._client.get_collection_stats(settings.milvus_collection)
                print(f"[OK] Milvus collection loaded: {settings.milvus_collection} ({count})")
                return

            # create collection with schema and index params
            schema = self._build_schema()
            index_params = MilvusClient.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="FLAT",
                metric_type="COSINE",
            )
            self._client.create_collection(
                collection_name=settings.milvus_collection,
                schema=schema,
                index_params=index_params,
            )
            self._client.load_collection(settings.milvus_collection)
            self._available = True
            print(f"[OK] Milvus collection created: {settings.milvus_collection}")
        except Exception as e:
            print(f"[WARN] Milvus init failed: {e}, vector search disabled")
            self._client = None
            self._available = False

    @staticmethod
    def _build_schema():
        from pymilvus import CollectionSchema, FieldSchema, DataType

        fields = [
            FieldSchema("asin", DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema("title", DataType.VARCHAR, max_length=2048),
            FieldSchema("description", DataType.VARCHAR, max_length=4096),
            FieldSchema("category", DataType.VARCHAR, max_length=256),
            FieldSchema("brand", DataType.VARCHAR, max_length=256),
            FieldSchema("price", DataType.FLOAT),
            FieldSchema("rating", DataType.FLOAT),
            FieldSchema("rating_count", DataType.INT64),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=settings.embedding_dim),
        ]
        return CollectionSchema(fields=fields, enable_dynamic_field=False)

    def is_available(self) -> bool:
        return self._available and self._client is not None

    def insert_batch(self, products: list[dict]):
        """Insert products with embeddings in batch."""
        if not self.is_available():
            raise RuntimeError("VectorService not available")

        texts = [
            f"{p.get('title', '')} {p.get('description', '')[:200]}"
            for p in products
        ]
        embeddings = self._embedding_svc.encode(texts)

        rows = []
        for p, emb in zip(products, embeddings):
            rows.append({
                "asin": p["asin"],
                "title": p.get("title", ""),
                "description": (p.get("description", "") or "")[:4096],
                "category": p.get("category", ""),
                "brand": p.get("brand", ""),
                "price": float(p.get("price", 0) or 0),
                "rating": float(p.get("rating", 0) or 0),
                "rating_count": int(p.get("rating_count", 0) or 0),
                "embedding": emb,
            })

        self._client.insert(
            collection_name=settings.milvus_collection,
            data=rows,
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        category: str | None = None,
    ) -> list[dict]:
        """Search by cosine similarity."""
        if not self.is_available():
            return []

        filter_expr = None
        if category:
            filter_expr = f'category like "{category}"'

        results = self._client.search(
            collection_name=settings.milvus_collection,
            data=[query_vector],
            limit=top_k,
            output_fields=["asin", "title", "description", "category", "brand", "price", "rating", "rating_count"],
            filter=filter_expr,
        )

        hits = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            entity["asin"] = hit.get("id", entity.get("asin", ""))
            entity["score"] = hit.get("distance", 0)
            hits.append(entity)
        return hits

    def drop_collection(self):
        """Drop the collection (for rebuild)."""
        if self._client and self._client.has_collection(settings.milvus_collection):
            self._client.drop_collection(settings.milvus_collection)
            print(f"[OK] Dropped collection: {settings.milvus_collection}")

    async def close(self):
        """Release resources."""
        if self._client:
            try:
                self._client.release_collection(settings.milvus_collection)
            except Exception:
                pass
            self._client = None
            self._available = False
