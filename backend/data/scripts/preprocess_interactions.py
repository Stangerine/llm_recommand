from collections import defaultdict
import json
from pathlib import Path


def process_interactions(
    raw_path: str,
    output_path: str,
    min_seq_len: int = 5,
    max_seq_len: int = 50,
):
    """整理为按时间排序的用户行为序列，过滤冷启动用户。"""
    user_actions = defaultdict(list)
    with open(raw_path) as f:
        for line in f:
            rec = json.loads(line)
            user_actions[rec["user_id"]].append({
                "asin": rec["parent_asin"],
                "timestamp": rec["timestamp"],
            })

    results = []
    for uid, actions in user_actions.items():
        actions.sort(key=lambda x: x["timestamp"])
        seq = [a["asin"] for a in actions]
        if len(seq) < min_seq_len:
            continue
        results.append({
            "user_id": uid,
            "sequence": seq[-max_seq_len:],
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"[OK] 有效用户数: {len(results)}")


if __name__ == "__main__":
    import sys

    raw_path = sys.argv[1] if len(sys.argv) > 1 else "./data/raw/Industrial_and_Scientific.jsonl"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "./data/processed/user_interactions.jsonl"
    process_interactions(raw_path, output_path)
