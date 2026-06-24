#!/usr/bin/env python3
"""数据验证脚本 - 检查所有数据文件的完整性"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def validate_data():
    print("=" * 60)
    print("数据验证报告")
    print("=" * 60)

    base_path = Path(__file__).parent.parent / "backend" / "data" / "processed"

    # 1. 检查文件存在性
    files = {
        "products.jsonl": base_path / "products.jsonl",
        "user_interactions.jsonl": base_path / "user_interactions.jsonl",
        "sid_mapping.json": base_path / "sid_mapping.json",
    }

    print("\n1. 文件检查:")
    all_exist = True
    for name, path in files.items():
        if path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            print(f"   [OK] {name}: {size_mb:.1f} MB")
        else:
            print(f"   [FAIL] {name}: 不存在")
            all_exist = False

    if not all_exist:
        print("\n[FAIL] 数据文件缺失，请运行数据处理脚本")
        return False

    # 2. 验证 products.jsonl
    print("\n2. 商品数据验证:")
    with open(files["products.jsonl"], encoding="utf-8") as f:
        products = [json.loads(line) for line in f]

    print(f"   商品总数: {len(products):,}")

    # 检查字段完整性
    required_fields = ["asin", "title", "description", "category", "brand"]
    products_with_missing = []
    for p in products:
        missing = [field for field in required_fields if not p.get(field)]
        if missing:
            products_with_missing.append((p["asin"], missing))

    if products_with_missing:
        print(f"   [WARN] {len(products_with_missing)} 个商品缺少字段")
    else:
        print(f"   [OK] 所有商品字段完整")

    # 统计有价格和评分的商品
    with_price = sum(1 for p in products if p.get("price") and p["price"] > 0)
    with_rating = sum(1 for p in products if p.get("rating"))
    print(f"   有价格商品: {with_price:,} ({with_price/len(products)*100:.1f}%)")
    print(f"   有评分商品: {with_rating:,} ({with_rating/len(products)*100:.1f}%)")

    # 3. 验证 user_interactions.jsonl
    print("\n3. 用户行为数据验证:")
    with open(files["user_interactions.jsonl"], encoding="utf-8") as f:
        interactions = [json.loads(line) for line in f]

    print(f"   有效用户数: {len(interactions):,}")

    seq_lengths = [len(i["sequence"]) for i in interactions]
    print(f"   平均序列长度: {sum(seq_lengths)/len(seq_lengths):.1f}")
    print(f"   最短序列: {min(seq_lengths)}")
    print(f"   最长序列: {max(seq_lengths)}")

    # 4. 验证 sid_mapping.json
    print("\n4. SID 映射验证:")
    with open(files["sid_mapping.json"], encoding="utf-8") as f:
        sid_data = json.load(f)

    asin2sid = sid_data["asin2sid"]
    sid2asin = sid_data["sid2asin"]

    print(f"   ASIN->SID 映射数: {len(asin2sid):,}")
    print(f"   唯一 SID 数: {len(sid2asin):,}")

    # 检查映射一致性
    product_asins = {p["asin"] for p in products}
    mapped_asins = set(asin2sid.keys())
    coverage = len(product_asins & mapped_asins) / len(product_asins) * 100
    print(f"   映射覆盖率: {coverage:.1f}%")

    # 5. 数据一致性检查
    print("\n5. 数据一致性检查:")
    interactions_flat = set()
    for i in interactions:
        interactions_flat.update(i["sequence"])

    valid_interactions = interactions_flat & product_asins
    print(f"   行为序列中的有效 ASIN: {len(valid_interactions):,}/{len(interactions_flat):,}")

    # 6. 样本数据展示
    print("\n6. 样本数据:")
    print("   商品样本:")
    for p in products[:3]:
        print(f"     - {p['asin']}: {p['title'][:40]}...")

    print("   用户行为样本:")
    for i in interactions[:3]:
        print(f"     - {i['user_id']}: {len(i['sequence'])} 个商品")

    print("\n" + "=" * 60)
    print("[OK] 数据验证完成！所有数据文件正常")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = validate_data()
    sys.exit(0 if success else 1)
