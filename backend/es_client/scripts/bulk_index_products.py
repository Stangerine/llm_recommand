import json
from pathlib import Path

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings


def bulk_index(
    es_host: str | None = None,
    index_name: str | None = None,
    products_path: str | None = None,
    sid_mapping_path: str | None = None,
    batch_size: int = 500,
):
    es_host = es_host or settings.es_host
    index_name = index_name or settings.es_index_name
    products_path = products_path or settings.products_path
    sid_mapping_path = sid_mapping_path or settings.sid_mapping_path

    es = Elasticsearch(es_host)

    with open(sid_mapping_path, encoding="utf-8") as f:
        sid_map = json.load(f)["asin2sid"]

    def gen_actions():
        with open(products_path, encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                yield {
                    "_index": index_name,
                    "_id": p["asin"],
                    "_source": {**p, "sid": sid_map.get(p["asin"], "")},
                }

    success, failed = bulk(es, gen_actions(), chunk_size=batch_size, raise_on_error=False)
    print(f"[OK] 导入成功: {success} | 失败: {len(failed)}")


if __name__ == "__main__":
    bulk_index()
