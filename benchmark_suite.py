#!/usr/bin/env python3
"""
Bộ kịch bản đo lường hiệu năng thực nghiệm toàn diện (Comprehensive Benchmark Suite)
Đánh giá năng lực cụm Microservice PDF Watermarking trên AWS theo nhiều mức tải đồng thời:
Concurrency = [2, 4, 8, 12, 16]
"""

import time
import json
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
import requests

from load_test import (
    DEFAULT_ALB_HOST,
    send_json_request,
    stats,
    stats_lock,
)

CONCURRENCY_LEVELS = [2, 4, 8, 12, 16]
DURATION_PER_TEST = 20  # 20 giây mỗi mức tải


def reset_stats():
    with stats_lock:
        stats["ok"] = 0
        stats["err"] = 0
        stats["hosts"].clear()
        stats["latencies"].clear()
        stats["host_events"].clear()
        stats["timeline"].clear()


def run_benchmark_level(base_url: str, concurrency: int, duration: int):
    reset_stats()
    start_t = time.time()
    end_t = start_t + duration

    def worker(worker_idx):
        counter = worker_idx * 100000
        with requests.Session() as s:
            while time.time() < end_t:
                counter += 1
                send_json_request(s, base_url, counter, stream_hosts=False)

    print(f"\n--- Đang chạy kiểm thử với Concurrency = {concurrency} ({duration}s) ---")
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for i in range(concurrency):
            executor.submit(worker, i)

    total_time = max(1.0, time.time() - start_t)
    with stats_lock:
        total_ok = stats["ok"]
        total_err = stats["err"]
        total_req = total_ok + total_err
        lats = list(stats["latencies"])
        hosts_dist = dict(stats["hosts"])

    sorted_lats = sorted(lats)
    n = len(sorted_lats)
    p50 = sorted_lats[int(n * 0.50)] if n else 0.0
    p90 = sorted_lats[int(n * 0.90)] if n else 0.0
    p95 = sorted_lats[int(n * 0.95)] if n else 0.0
    p99 = sorted_lats[int(n * 0.99)] if n else 0.0
    avg_lat = sum(lats) / n if n else 0.0
    min_lat = sorted_lats[0] if n else 0.0
    max_lat = sorted_lats[-1] if n else 0.0
    rps = total_ok / total_time

    worker_pcts = {}
    for h, cnt in sorted(hosts_dist.items()):
        worker_pcts[h] = {
            "requests": cnt,
            "pct": round((cnt / max(1, total_ok)) * 100, 2)
        }

    res = {
        "concurrency": concurrency,
        "duration_s": round(total_time, 1),
        "total_requests": total_req,
        "ok_requests": total_ok,
        "err_requests": total_err,
        "error_rate_pct": round((total_err / max(1, total_req)) * 100, 2),
        "rps": round(rps, 2),
        "latency_ms": {
            "mean": round(avg_lat, 1),
            "p50": round(p50, 1),
            "p90": round(p90, 1),
            "p95": round(p95, 1),
            "p99": round(p99, 1),
            "min": round(min_lat, 1),
            "max": round(max_lat, 1),
        },
        "worker_distribution": worker_pcts,
        "active_workers": len(hosts_dist),
    }

    print(f"  ✓ Xong: {total_ok} reqs | RPS: {rps:.2f} | Latency TB: {avg_lat:.1f}ms (p50: {p50:.1f}ms, p95: {p95:.1f}ms) | Lỗi: {total_err} (0.0%)")
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_ALB_HOST)
    parser.add_argument("--duration", type=int, default=DURATION_PER_TEST)
    parser.add_argument("--output", default="report/benchmark_summary.json")
    args = parser.parse_args()

    print("=" * 80)
    print("🚀 BẮT ĐẦU CHẠY BỘ KIỂM THỬ HIỆU NĂNG THEO MỨC TẢI (BENCHMARK SUITE)")
    print(f"🎯 Target ALB: {args.url}")
    print(f"📊 Các mức luồng: {CONCURRENCY_LEVELS}")
    print(f"⏱️  Thời gian mỗi mức: {args.duration}s")
    print("=" * 80)

    results = []
    for c in CONCURRENCY_LEVELS:
        r = run_benchmark_level(args.url, c, args.duration)
        results.append(r)
        time.sleep(2)  # Nghỉ 2s giữa các đợt

    suite_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "target_url": args.url,
        "benchmark_matrix": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(suite_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("📊 BẢNG TỔNG HỢP HIỆU NĂNG THỰC NGHIỆM ĐA TẢI:")
    print("=" * 80)
    print(f"{'Luồng':<8}{'Tổng Req':<12}{'RPS':<10}{'Lat TB (ms)':<14}{'p50 (ms)':<12}{'p95 (ms)':<12}{'Lỗi (%)':<10}")
    print("-" * 80)
    for row in results:
        lat = row["latency_ms"]
        print(f"{row['concurrency']:<8}{row['ok_requests']:<12}{row['rps']:<10.2f}{lat['mean']:<14.1f}{lat['p50']:<12.1f}{lat['p95']:<12.1f}{row['error_rate_pct']:<10.1f}")
    print("=" * 80)
    print(f"💾 Kết quả đã lưu tại: {args.output}")


if __name__ == "__main__":
    main()
