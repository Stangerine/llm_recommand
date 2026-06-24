"""Batch embed all products into Milvus.

Usage:
    cd backend
    python scripts/build_embeddings.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from services.embedding_service import EmbeddingService
from services.vector_service import VectorService


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text).strip()


def load_products(path: str) -> list[dict]:
    """Load products from jsonl file."""
    products = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                products.append(json.loads(line))
    return products


def main():
    products_path = Path(settings.products_path)
    if not products_path.exists():
        print(f"[ERROR] Products file not found: {products_path}")
        sys.exit(1)

    print(f"Loading products from {products_path}...")
    products = load_products(str(products_path))
    print(f"Loaded {len(products)} products")

    # clean descriptions
    for p in products:
        if p.get("description"):
            p["description"] = strip_html(p["description"])

    # init services
    embedding_svc = EmbeddingService()
    embedding_svc.load()  # sync load

    vector_svc = VectorService(embedding_svc=embedding_svc)

    # drop and recreate collection for idempotent re-run
    from pymilvus import MilvusClient
    client = MilvusClient(uri=settings.milvus_uri)
    if client.has_collection(settings.milvus_collection):
        client.drop_collection(settings.milvus_collection)
        print(f"Dropped existing collection: {settings.milvus_collection}")
    del client

    # initialize fresh collection
    import asyncio
    asyncio.run(vector_svc.initialize())

    # batch insert
    batch_size = 500
    total = len(products)
    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = products[i : i + batch_size]
        vector_svc.insert_batch(batch)
        done = min(i + batch_size, total)
        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        print(f"  [{done}/{total}] ({rate:.0f} products/sec)")

    elapsed = time.time() - start_time
    print(f"\nDone! Embedded {total} products in {elapsed:.1f}s")
    print(f"Collection: {settings.milvus_collection}")
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Dimension: {settings.embedding_dim}")


if __name__ == "__main__":
    main()
