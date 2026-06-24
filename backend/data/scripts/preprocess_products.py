import json
import re
import html
import pandas as pd
from pathlib import Path


def strip_html(text: str) -> str:
    """去除 HTML 标签并解码 HTML 实体"""
    if not text:
        return ""
    # 解码 HTML 实体 (&amp; &#160; 等)
    text = html.unescape(text)
    # 去除 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 合并多余空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_price(price) -> float | None:
    """清洗价格：去除 $ 符号，转换为 float，校验范围"""
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return round(float(price), 2) if 0 < price < 100000 else None
    if isinstance(price, str):
        # 去除 $ 和逗号
        price = price.replace("$", "").replace(",", "").strip()
        try:
            val = float(price)
            return round(val, 2) if 0 < val < 100000 else None
        except ValueError:
            return None
    return None


def clean_rating(rating) -> float | None:
    """清洗评分：归一化到 0-5 范围"""
    if rating is None:
        return None
    try:
        val = float(rating)
        if 0 <= val <= 5:
            return round(val, 1)
        return None
    except (ValueError, TypeError):
        return None


def clean_rating_count(count) -> int:
    """清洗评分数量"""
    if count is None:
        return 0
    try:
        val = int(count)
        return max(0, val)
    except (ValueError, TypeError):
        return 0


def clean_text(text: str, max_len: int = 2000) -> str:
    """清洗文本：去除 HTML、截断"""
    text = strip_html(text)
    return text[:max_len] if text else ""


def process_product_meta(raw_path: str, output_path: str):
    """清洗商品元数据，输出 products.jsonl"""
    records = []
    skipped = {"no_title": 0, "no_asin": 0, "bad_price": 0}

    with open(raw_path) as f:
        for line in f:
            item = json.loads(line)

            # 提取 ASIN (优先 parent_asin，兼容 asin)
            asin = item.get("parent_asin") or item.get("asin", "")
            if not asin or asin == "None":
                skipped["no_asin"] += 1
                continue

            # 提取并清洗标题
            title = strip_html(item.get("title", ""))
            if not title:
                skipped["no_title"] += 1
                continue

            # 清洗描述：拼接列表 → 去 HTML → 截断
            desc_list = item.get("description", [])
            if isinstance(desc_list, list):
                description = " ".join(desc_list)
            elif isinstance(desc_list, str):
                description = desc_list
            else:
                description = ""
            description = clean_text(description, max_len=2000)

            # 清洗分类：取第一层，用 > 拼接
            categories = item.get("category") or item.get("categories", [])
            if isinstance(categories, list) and categories:
                # 可能是 [["A", "B"]] 或 ["A", "B"]
                if isinstance(categories[0], list):
                    categories = categories[0]
                category = " > ".join(str(c) for c in categories if c)
            else:
                category = ""

            # 清洗品牌
            brand = strip_html(str(item.get("brand", "")))

            # 清洗价格
            price = clean_price(item.get("price"))

            # 清洗评分
            rating = clean_rating(item.get("average_rating") or item.get("rating"))
            rating_count = clean_rating_count(item.get("rating_number") or item.get("rating_count"))

            records.append({
                "asin": asin,
                "title": title,
                "description": description,
                "category": category,
                "brand": brand,
                "price": price,
                "rating": rating,
                "rating_count": rating_count,
            })

    df = pd.DataFrame(records).drop_duplicates(subset=["asin"])

    # 统计清洗结果
    null_price = df["price"].isna().sum()
    null_rating = df["rating"].isna().sum()
    empty_desc = (df["description"] == "").sum()
    empty_cat = (df["category"] == "").sum()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(output_path, orient="records", lines=True, force_ascii=False)

    print(f"[OK] 商品总数: {len(df)}")
    print(f"[INFO] 跳过: 无标题={skipped['no_title']}, 无ASIN={skipped['no_asin']}")
    print(f"[INFO] 空值统计: 价格={null_price}, 评分={null_rating}, 描述={empty_desc}, 分类={empty_cat}")


if __name__ == "__main__":
    import sys

    default_raw = str(Path(__file__).parent.parent.parent.parent / "meta_Industrial_and_Scientific" / "meta_Industrial_and_Scientific.json")
    raw_path = sys.argv[1] if len(sys.argv) > 1 else default_raw
    output_path = sys.argv[2] if len(sys.argv) > 2 else "./data/processed/products.jsonl"
    process_product_meta(raw_path, output_path)
