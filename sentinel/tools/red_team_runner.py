"""
SENTINEL Red Team Runner
==========================
Takes a JSONL file of attack prompts, sends them through the full gateway API,
and produces a benchmark report on catch rates, false positives, etc.

Usage:
  python -m sentinel.tools.red_team_runner --dataset data/redteam_prompts.jsonl --endpoint http://localhost:8000
"""
import argparse
import asyncio
import json
import statistics
import time
from httpx import AsyncClient

async def run_benchmark(dataset_path: str, endpoint: str):
    print(f"Loading dataset from {dataset_path}")
    prompts = []
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                prompts.append(json.loads(line))
    except Exception as e:
        print(f"Error loading {dataset_path}: {e}")
        return

    print(f"Loaded {len(prompts)} prompts. Starting red team run against {endpoint}...")

    results = []
    latencies = []

    async with AsyncClient(timeout=30.0) as client:
        # Just loop sequentially to avoid overloading local box during benchmark
        for i, item in enumerate(prompts):
            prompt_text = item.get("prompt", "")
            expected_decision = item.get("expected_decision", "block")

            t0 = time.time()
            try:
                resp = await client.post(
                    f"{endpoint}/v1/chat",
                    json={"prompt": prompt_text},
                    headers={"X-Sentinel-Tenant": "tenant_benchmark"}
                )
                lat = (time.time() - t0) * 1000
                latencies.append(lat)

                if resp.status_code == 200:
                    data = resp.json()
                    decision = data.get("decision", "error").lower()
                else:
                    decision = "error"
                    print(f"Error for prompt {i}: {resp.status_code} - {resp.text}")

                results.append({
                    "prompt": prompt_text,
                    "expected": expected_decision.lower(),
                    "actual": decision,
                    "latency": lat
                })
            except Exception as e:
                print(f"Exception on prompt {i}: {e}")
                results.append({
                    "prompt": prompt_text,
                    "expected": expected_decision.lower(),
                    "actual": "error",
                    "latency": (time.time() - t0) * 1000
                })

            if (i+1) % 10 == 0:
                print(f"Processed {i+1}/{len(prompts)} prompts...")

    total = len(results)
    successes = sum(1 for r in results if r["actual"] == r["expected"])
    errors = sum(1 for r in results if r["actual"] == "error")
    accuracy = (successes / total) * 100 if total > 0 else 0

    print("\n" + "="*40)
    print("BENCHMARK REPORT")
    print("="*40)
    print(f"Total tests:   {total}")
    print(f"Errors:        {errors}")
    print(f"Matches:       {successes}")
    print(f"Accuracy:      {accuracy:.2f}%")
    if latencies:
        print(f"Avg Latency:   {statistics.mean(latencies):.2f} ms")
        print(f"P95 Latency:   {statistics.quantiles(latencies, n=20)[18]:.2f} ms")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--endpoint", default="http://localhost:8000", help="Gateway URL")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.dataset, args.endpoint))
