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
        """Connect to Milvus and ensure collections exist."""
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=settings.milvus_uri)

            # 确保 products 集合存在
            if self._client.has_collection(settings.milvus_collection):
                self._client.load_collection(settings.milvus_collection)
                self._available = True
                count = self._client.get_collection_stats(settings.milvus_collection)
                print(f"[OK] Milvus collection loaded: {settings.milvus_collection} ({count})")
            else:
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

            # 确保 sid_mapping 集合存在
            if self._client.has_collection(settings.milvus_sid_collection):
                self._client.load_collection(settings.milvus_sid_collection)
                sid_count = self._client.get_collection_stats(settings.milvus_sid_collection)
                print(f"[OK] Milvus collection loaded: {settings.milvus_sid_collection} ({sid_count})")
            else:
                self._create_sid_collection()

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

    # ── 商品查询方法 ──────────────────────────────────────────

    _PRODUCT_FIELDS = ["asin", "title", "description", "category", "brand", "price", "rating", "rating_count"]

    def get_by_asin(self, asin: str) -> dict | None:
        """单个商品查询"""
        if not self.is_available():
            return None
        try:
            results = self._client.query(
                collection_name=settings.milvus_collection,
                filter=f'asin == "{asin}"',
                output_fields=self._PRODUCT_FIELDS,
                limit=1,
            )
            return results[0] if results else None
        except Exception:
            return None

    def get_by_asins(self, asins: list[str]) -> list[dict]:
        """批量商品查询，分批处理避免表达式过长"""
        if not self.is_available() or not asins:
            return []
        all_results = []
        batch_size = 100
        for i in range(0, len(asins), batch_size):
            batch = asins[i:i + batch_size]
            escaped = [f'"{a}"' for a in batch]
            filter_expr = f'asin in [{", ".join(escaped)}]'
            try:
                results = self._client.query(
                    collection_name=settings.milvus_collection,
                    filter=filter_expr,
                    output_fields=self._PRODUCT_FIELDS,
                )
                all_results.extend(results)
            except Exception:
                continue
        return all_results

    def list_products(
        self, page: int = 1, page_size: int = 20, category: str | None = None
    ) -> tuple[list[dict], int]:
        """分页查询商品列表，返回 (products, total)"""
        if not self.is_available():
            return [], 0
        try:
            filter_expr = None
            if category:
                filter_expr = f'category like "%{category}%"'

            # 查询总数
            count_results = self._client.query(
                collection_name=settings.milvus_collection,
                filter=filter_expr,
                output_fields=["asin"],
            )
            total = len(count_results)

            # 分页查询
            offset = (page - 1) * page_size
            results = self._client.query(
                collection_name=settings.milvus_collection,
                filter=filter_expr,
                output_fields=self._PRODUCT_FIELDS,
                offset=offset,
                limit=page_size,
            )
            return results, total
        except Exception:
            return [], 0

    def count_products(self, category: str | None = None) -> int:
        """统计商品总数"""
        if not self.is_available():
            return 0
        try:
            filter_expr = None
            if category:
                filter_expr = f'category like "%{category}%"'
            results = self._client.query(
                collection_name=settings.milvus_collection,
                filter=filter_expr,
                output_fields=["asin"],
            )
            return len(results)
        except Exception:
            return 0

    # ── SID 集合支持 ─────────────────────────────────────────

    @staticmethod
    def _build_sid_schema():
        from pymilvus import CollectionSchema, FieldSchema, DataType

        fields = [
            FieldSchema("asin", DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema("sid", DataType.VARCHAR, max_length=32),
            FieldSchema("dummy_vector", DataType.FLOAT_VECTOR, dim=1),  # Milvus Lite 要求至少一个向量字段
        ]
        return CollectionSchema(fields=fields, enable_dynamic_field=False)

    def _create_sid_collection(self):
        """创建 SID 映射集合"""
        from pymilvus import MilvusClient

        schema = self._build_sid_schema()
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="dummy_vector",
            index_type="FLAT",
            metric_type="COSINE",
        )
        self._client.create_collection(
            collection_name=settings.milvus_sid_collection,
            schema=schema,
            index_params=index_params,
        )
        self._client.load_collection(settings.milvus_sid_collection)
        print(f"[OK] Milvus collection created: {settings.milvus_sid_collection}")

    def create_sid_collection(self):
        """创建 SID 集合（外部调用）"""
        if not self.is_available():
            raise RuntimeError("VectorService not available")
        if self._client.has_collection(settings.milvus_sid_collection):
            self._client.drop_collection(settings.milvus_sid_collection)
        self._create_sid_collection()

    def drop_sid_collection(self):
        """删除 SID 集合"""
        if self._client and self._client.has_collection(settings.milvus_sid_collection):
            self._client.drop_collection(settings.milvus_sid_collection)
            print(f"[OK] Dropped collection: {settings.milvus_sid_collection}")

    def insert_sid_batch(self, mappings: list[dict]):
        """批量插入 SID 映射 [{"asin": "...", "sid": "..."}]"""
        if not self.is_available():
            raise RuntimeError("VectorService not available")
        # 添加虚拟向量字段以满足 Milvus Lite 要求
        rows = []
        for m in mappings:
            row = {**m, "dummy_vector": [0.0]}
            rows.append(row)
        self._client.insert(
            collection_name=settings.milvus_sid_collection,
            data=rows,
        )

    def get_all_sids(self) -> list[dict]:
        """查询全部 SID 映射（构建脚本用）"""
        if not self.is_available():
            return []
        try:
            results = self._client.query(
                collection_name=settings.milvus_sid_collection,
                output_fields=["asin", "sid"],
            )
            # 移除可能存在的 dummy_vector 字段
            for r in results:
                r.pop("dummy_vector", None)
            return results
        except Exception:
            return []

    def get_sids_by_asins(self, asins: list[str]) -> list[dict]:
        """批量查询 SID 映射"""
        if not self.is_available() or not asins:
            return []
        all_results = []
        batch_size = 100
        for i in range(0, len(asins), batch_size):
            batch = asins[i:i + batch_size]
            escaped = [f'"{a}"' for a in batch]
            filter_expr = f'asin in [{", ".join(escaped)}]'
            try:
                results = self._client.query(
                    collection_name=settings.milvus_sid_collection,
                    filter=filter_expr,
                    output_fields=["asin", "sid"],
                )
                # 移除可能存在的 dummy_vector 字段
                for r in results:
                    r.pop("dummy_vector", None)
                all_results.extend(results)
            except Exception:
                continue
        return all_results

    async def close(self):
        """Release resources."""
        if self._client:
            try:
                self._client.release_collection(settings.milvus_collection)
            except Exception:
                pass
            self._client = None
            self._available = False
