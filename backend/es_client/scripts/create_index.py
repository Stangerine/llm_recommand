import json
from pathlib import Path

from elasticsearch import Elasticsearch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings


def create_index():
    es = Elasticsearch(settings.es_host)
    mapping_path = Path(__file__).parent.parent / "mappings" / "products_mapping.json"

    with open(mapping_path) as f:
        mapping = json.load(f)

    if es.indices.exists(index=settings.es_index_name):
        print(f"[WARN] 索引 {settings.es_index_name} 已存在，跳过创建")
        return

    es.indices.create(index=settings.es_index_name, body=mapping)
    print(f"[OK] 索引 {settings.es_index_name} 创建成功")


if __name__ == "__main__":
    create_index()
