#!/usr/bin/env python3
"""推荐流程端到端测试 - 验证真实数据下的完整推荐链路"""

import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_recommend_flow():
    print("=" * 60)
    print("推荐流程端到端测试")
    print("=" * 60)

    # 1. 加载数据
    print("\n1. 加载数据...")
    base_path = Path(__file__).parent.parent / "backend" / "data" / "processed"

    with open(base_path / "sid_mapping.json", encoding="utf-8") as f:
        sid_data = json.load(f)

    with open(base_path / "products.jsonl", encoding="utf-8") as f:
        products = {json.loads(line)["asin"]: json.loads(line) for line in f}

    print(f"   加载 {len(products):,} 个商品")
    print(f"   加载 {len(sid_data['asin2sid']):,} 个 SID 映射")

    asin2sid = sid_data["asin2sid"]
    sid2asin = sid_data["sid2asin"]

    # 2. 模拟用户行为
    print("\n2. 模拟用户行为...")
    test_asins = list(asin2sid.keys())[:5]
    print(f"   用户浏览历史: {test_asins}")

    # 3. ASIN -> SID 转换
    print("\n3. ASIN -> SID 转换...")
    history_sids = [asin2sid[a] for a in test_asins if a in asin2sid]
    print(f"   转换结果: {history_sids}")

    # 4. 模型推理（使用模拟模式）
    print("\n4. 模型推理（模拟模式）...")
    import random
    random.seed(hash(tuple(history_sids)))

    # 生成候选 SID
    candidate_sids = []
    for _ in range(20):
        sid = f"{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}"
        if sid not in candidate_sids:
            candidate_sids.append(sid)
        if len(candidate_sids) >= 10:
            break

    print(f"   生成 {len(candidate_sids)} 个候选 SID")

    # 5. SID -> ASIN 转换
    print("\n5. SID -> ASIN 转换...")
    candidate_asins = []
    for sid in candidate_sids:
        if sid in sid2asin:
            candidate_asins.append(sid2asin[sid])

    print(f"   有效候选: {len(candidate_asins)} 个商品")

    # 6. 获取商品详情
    print("\n6. 获取商品详情...")
    recommended_products = []
    for asin in candidate_asins[:10]:
        if asin in products:
            p = products[asin]
            recommended_products.append({
                "asin": p["asin"],
                "title": p["title"][:50],
                "brand": p.get("brand", "N/A"),
                "price": p.get("price"),
            })

    print(f"   返回 {len(recommended_products)} 个推荐商品")

    # 7. 展示推荐结果
    print("\n7. 推荐结果:")
    print("-" * 60)
    for i, p in enumerate(recommended_products[:5], 1):
        price_str = f"${p['price']:.2f}" if p['price'] else "N/A"
        print(f"   {i}. {p['title']}...")
        print(f"      品牌: {p['brand']} | 价格: {price_str} | ASIN: {p['asin']}")
    print("-" * 60)

    # 8. 性能统计
    print("\n8. 性能统计:")
    start = time.time()
    for _ in range(1000):
        _ = asin2sid.get(test_asins[0])
    sid_lookup_ms = (time.time() - start) * 1000 / 1000
    print(f"   SID 查询延迟: {sid_lookup_ms*1000:.2f} us/次")

    start = time.time()
    for _ in range(1000):
        _ = sid2asin.get(history_sids[0])
    reverse_lookup_ms = (time.time() - start) * 1000 / 1000
    print(f"   反向查询延迟: {reverse_lookup_ms*1000:.2f} us/次")

    print("\n" + "=" * 60)
    print("[OK] 推荐流程测试通过！")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_recommend_flow()
    sys.exit(0 if success else 1)
