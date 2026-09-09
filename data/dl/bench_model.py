"""
Phase 6a: 模型服务压测
对 /rank（DeepFM 精排）与 /embed（双塔召回）做并发请求，输出 P50/P95/P99 延迟。
用法: python bench_model.py [并发数] [每线程请求数]
"""

import json
import sys
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8000"
CONCURRENCY = int(sys.argv[1]) if len(sys.argv) > 1 else 8
REQS_PER_THREAD = int(sys.argv[2]) if len(sys.argv) > 2 else 50


def bench_rank():
    """DeepFM 精排: 68 个候选的批量打分（平均候选池大小）"""
    body = json.dumps({"pairs": [[11488, 2454, 0.5, 0.3, 0.2, 1.0]] * 68}).encode()
    lat = []
    for _ in range(REQS_PER_THREAD):
        req = urllib.request.Request(BASE + "/rank", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        lat.append((time.perf_counter() - t0) * 1000)
    return lat


def bench_embed():
    """双塔召回: 用户向量 + Faiss Top-100"""
    body = b'{"user_id": 11488}'
    lat = []
    for _ in range(REQS_PER_THREAD):
        req = urllib.request.Request(BASE + "/embed", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        lat.append((time.perf_counter() - t0) * 1000)
    return lat


def percentile(lat, p):
    lat = sorted(lat)
    return lat[min(len(lat) - 1, int(len(lat) * p / 100))]


def run(name, fn):
    print(f"压测 {name}：并发 {CONCURRENCY} × 每线程 {REQS_PER_THREAD} 请求 ...")
    results = []

    def worker():
        results.extend(fn())

    threads = [threading.Thread(target=worker) for _ in range(CONCURRENCY)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = time.perf_counter() - t0
    n = len(results)
    print(f"  共 {n} 请求, 吞吐 {n / total:.1f} req/s")
    print(f"  P50={percentile(results, 50):.1f}ms  P90={percentile(results, 90):.1f}ms  "
          f"P95={percentile(results, 95):.1f}ms  P99={percentile(results, 99):.1f}ms")
    return {"n": n, "qps": round(n / total, 1),
            "p50": round(percentile(results, 50), 1),
            "p95": round(percentile(results, 95), 1),
            "p99": round(percentile(results, 99), 1)}


if __name__ == "__main__":
    out = {}
    out["rank_deepfm"] = run("DeepFM 精排 /rank (68 候选)", bench_rank)
    out["embed_tower"] = run("双塔召回 /embed (Top-100)", bench_embed)
    with open("bench_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("结果已保存 bench_results.json")
