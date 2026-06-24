"""
输出格式 sid_mapping.json:
{
  "asin2sid": { "B001XXXXX": "12_5_3_7", ... },
  "sid2asin": { "12_5_3_7": "B001XXXXX", ... }
}
SID 格式：RQ-VAE 各层 codebook 索引以 "_" 连接
"""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.rqvae_encoder import RQVAEEncoder


def build_sid_mapping(
    products_path: str,
    rqvae_ckpt: str,
    output_path: str,
    batch_size: int = 256,
):
    encoder = RQVAEEncoder(ckpt_path=rqvae_ckpt)
    asin2sid, sid2asin = {}, {}

    with open(products_path) as f:
        products = [json.loads(l) for l in f]

    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        texts = [f"{p['title']} {p['description'][:200]}" for p in batch]
        sids = encoder.encode_batch(texts)

        for p, sid in zip(batch, sids):
            asin2sid[p["asin"]] = sid
            sid2asin.setdefault(sid, p["asin"])  # SID 碰撞取首个商品

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"asin2sid": asin2sid, "sid2asin": sid2asin}, f, indent=2)

    print(f"✅ 总商品: {len(asin2sid)} | 唯一SID: {len(sid2asin)}")


if __name__ == "__main__":
    products_path = sys.argv[1] if len(sys.argv) > 1 else "./data/processed/products.jsonl"
    rqvae_ckpt = sys.argv[2] if len(sys.argv) > 2 else "./models/checkpoints/rqvae"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "./data/processed/sid_mapping.json"
    build_sid_mapping(products_path, rqvae_ckpt, output_path)
