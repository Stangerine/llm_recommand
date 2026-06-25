"""商品搜索延迟压测脚本 — 测试 keyword / hybrid 模式"""
import requests
import time
import statistics
import sys
import json

BASE = "http://localhost:8000/api/v1"
RUNS_PER_QUERY = 5
TIMEOUT = 30

# 100 个真实工业/科学领域搜索词
QUERIES = [
    # 工具类
    "power drill", "cordless drill", "impact driver", "angle grinder",
    "circular saw", "jigsaw", "reciprocating saw", "table saw",
    "drill bit set", "socket wrench", "torque wrench", "adjustable wrench",
    "screwdriver set", "hex key set", "pliers", "wire cutter",
    "measuring tape", "laser level", "stud finder", "multimeter",
    "soldering iron", "heat gun", "electric motor", "hydraulic pump",
    # 安全防护
    "safety glasses", "safety gloves", "welding helmet", "hard hat",
    "ear protection", "respirator mask", "safety vest", "steel toe boots",
    "face shield", "work gloves", "cut resistant gloves", "nitrile gloves",
    # 紧固件与五金
    "steel screws", "stainless bolts", "hex nuts", "washers set",
    "anchor bolts", "rivets", "cotter pins", "spring clips",
    "hose clamp", "cable tie", "zip tie", "wire connector",
    # 电气
    "circuit breaker", "LED light bulb", "electrical wire", "outlet box",
    "toggle switch", "dimmer switch", "GFCI outlet", "extension cord",
    "power strip", "transformer", "relay module", "fuse holder",
    # 管道与流体
    "PVC pipe", "copper fitting", "ball valve", "gate valve",
    "pressure gauge", "flow meter", "pipe clamp", "hose fitting",
    # 材料
    "aluminum sheet", "steel plate", "copper wire", "brass rod",
    "nylon sheet", "acrylic rod", "rubber gasket", "silicone sealant",
    # 实验室
    "pipette tip", "microscope slide", "test tube rack", "beaker set",
    "lab thermometer", "pH meter", "centrifuge tube", "petri dish",
    # 清洁与维护
    "industrial cleaner", "degreaser", "rust remover", "lubricant spray",
    "thread tape", "pipe sealant", "adhesive glue", "epoxy resin",
]

def run_latency_test(mode: str, queries: list[str]) -> list[float]:
    """测试指定模式的搜索延迟，返回所有有效延迟(ms)"""
    latencies = []
    errors = 0
    for i, q in enumerate(queries):
        for _ in range(RUNS_PER_QUERY):
            start = time.perf_counter()
            try:
                r = requests.get(
                    f"{BASE}/products/search",
                    params={"q": q, "mode": mode, "size": 10},
                    timeout=TIMEOUT,
                )
                elapsed = (time.perf_counter() - start) * 1000
                if r.status_code == 200:
                    latencies.append(elapsed)
                else:
                    errors += 1
            except Exception:
                errors += 1
        # 进度
        if (i + 1) % 20 == 0:
            print(f"  [{mode}] {i+1}/{len(queries)} queries done", file=sys.stderr)
    if errors:
        print(f"  [{mode}] {errors} errors", file=sys.stderr)
    return latencies


def percentile(data: list[float], p: float) -> float:
    """计算百分位数"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def print_stats(mode: str, latencies: list[float]):
    """打印统计结果"""
    if not latencies:
        print(f"\n{mode}: no successful requests")
        return
    print(f"\n{'=' * 50}")
    print(f"  Mode: {mode}")
    print(f"{'=' * 50}")
    print(f"  Queries    = {len(QUERIES)}")
    print(f"  Runs/query = {RUNS_PER_QUERY}")
    print(f"  Samples    = {len(latencies)}")
    print(f"  Errors     = {len(QUERIES) * RUNS_PER_QUERY - len(latencies)}")
    print(f"  ---")
    print(f"  Avg        = {statistics.mean(latencies):.1f} ms")
    print(f"  Median     = {statistics.median(latencies):.1f} ms")
    print(f"  P90        = {percentile(latencies, 90):.1f} ms")
    print(f"  P95        = {percentile(latencies, 95):.1f} ms")
    print(f"  P99        = {percentile(latencies, 99):.1f} ms")
    print(f"  Min        = {min(latencies):.1f} ms")
    print(f"  Max        = {max(latencies):.1f} ms")
    print(f"  Stddev     = {statistics.stdev(latencies):.1f} ms" if len(latencies) > 1 else "")


def main():
    # 预热
    print("Warming up...", file=sys.stderr)
    for q in QUERIES[:5]:
        requests.get(f"{BASE}/products/search", params={"q": q, "mode": "keyword", "size": 10}, timeout=TIMEOUT)

    all_results = {}

    for mode in ["keyword", "hybrid"]:
        print(f"\nTesting {mode}...", file=sys.stderr)
        latencies = run_latency_test(mode, QUERIES)
        all_results[mode] = latencies
        print_stats(mode, latencies)

    # 输出 JSON 结果
    output = {
        "total_products": 116351,
        "queries_count": len(QUERIES),
        "runs_per_query": RUNS_PER_QUERY,
        "results": {}
    }
    for mode, latencies in all_results.items():
        if latencies:
            output["results"][mode] = {
                "samples": len(latencies),
                "avg_ms": round(statistics.mean(latencies), 1),
                "median_ms": round(statistics.median(latencies), 1),
                "p90_ms": round(percentile(latencies, 90), 1),
                "p95_ms": round(percentile(latencies, 95), 1),
                "p99_ms": round(percentile(latencies, 99), 1),
                "min_ms": round(min(latencies), 1),
                "max_ms": round(max(latencies), 1),
            }

    result_path = "data/processed/search_latency_results.json"
    with open(result_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {result_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
