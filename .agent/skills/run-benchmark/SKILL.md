---
name: run-benchmark
description: Run the SENTINEL red-team and benign benchmark suites and generate the benchmark report
---

# Running the SENTINEL Benchmark

## Quick Run

```bash
# From the sentinel/ root directory:
python tests/red_team/run_benchmark.py
```

Output will look like:
```
============================================================
  SENTINEL RED-TEAM BENCHMARK
============================================================
[1/2] Running 150 attack prompts …
[2/2] Running 150 benign prompts …

============================================================
  RESULTS
============================================================
  Detection Rate:       81.3%
  Bypass Rate:          18.7%
  False Positive Rate:   2.4%
  P99 Latency (attack): 68.2ms
  P99 Latency (benign): 59.1ms
============================================================

  Report saved → benchmark_report.json
```

## Pytest Integration

```bash
# Run all benchmark tests
pytest tests/red_team/ -v --tb=short

# Run with asyncio mode
pytest tests/red_team/ -v --asyncio-mode=auto
```

## Interpreting Results

| Metric | Target | Action if failing |
|--------|--------|-------------------|
| Detection Rate | ≥ 70% | Add more attack patterns to InjectionScout / increase FAISS index |
| Bypass Rate    | ≤ 30% | Review agent thresholds; check pattern coverage |
| False Positive | ≤ 10% | Raise lower_threshold in default policy |
| P99 Latency    | ≤ 80ms | Profile agents with `asyncio.to_thread` offloading |

## Extending the Benchmark

Add new attack prompts to `ATTACK_PROMPTS` in `tests/red_team/run_benchmark.py`:

```python
ATTACK_PROMPTS += [
    "Your new attack vector here",
    "Another adversarial example",
]
```

Add benign prompts to `BENIGN_PROMPTS` to improve false-positive measurement.

## Loading HuggingFace Dataset

To bootstrap the FAISS index with the full 50k attack dataset:

```python
from datasets import load_dataset
from sentinel.storage.faiss_manager import FAISSManager
import asyncio

async def load():
    ds = load_dataset("deepset/prompt-injections", split="train")
    texts = [row["text"] for row in ds]
    fm = FAISSManager()
    await fm.bulk_load(texts)
    print(f"Loaded {fm.vector_count} vectors")

asyncio.run(load())
```
