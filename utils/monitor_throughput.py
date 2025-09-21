#!/usr/bin/env python

"""Continuous Celery/Redis throughput monitor.

Polls queue depths and task metadata to report ingestion progress,
including completed counts, failures, fallback backlog, and active
vs. waiting tasks on each queue.

Configuration is pulled from the Docling config to reuse the Redis URL
and queue names.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

try:
    import redis
except ImportError:
    print(
        "Redis client is required. Install with: pip install redis",
        file=sys.stderr,
    )
    sys.exit(1)


def _load_config(config_path: str | None) -> Tuple[str, Dict[str, str]]:
    repo_root = os.getcwd()
    os.environ.setdefault("PYTHONPATH", repo_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from docling_service.config import Config

    cfg = Config(config_path) if config_path else Config()
    redis_url = cfg.get_redis_url()
    vlm_cfg = cfg.get_section("vlm_fallback") or {}
    queues = {
        "standard": "celery",
        "vlm": vlm_cfg.get("queue_name", "vlm_pdf"),
    }
    return redis_url, queues


def _format_delta(seconds: float) -> str:
    if seconds < 0:
        return "-"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _sample(redis_client: redis.Redis, batch_id: str, queues: Dict[str, str]) -> Dict[str, any]:
    batch_key = f"docling_batch:{batch_id}"
    batch_data_raw = redis_client.get(batch_key)
    if not batch_data_raw:
        raise ValueError(f"Batch {batch_id} not found in Redis")
    batch_data = json.loads(batch_data_raw)

    meta_key = f"docling_batch:{batch_id}:meta"
    task_meta_raw = redis_client.hgetall(meta_key)
    now = time.time()

    active_counts = defaultdict(int)
    oldest_elapsed = defaultdict(float)
    for payload in task_meta_raw.values():
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        mode = data.get("mode", "standard")
        active_counts[mode] += 1
        started = data.get("started_at")
        if started:
            try:
                elapsed = now - float(started)
                oldest_elapsed[mode] = max(oldest_elapsed.get(mode, 0), elapsed)
            except (TypeError, ValueError):
                pass

    queue_depths = {}
    for label, queue in queues.items():
        queue_depths[label] = redis_client.llen(queue)

    return {
        "batch": batch_data,
        "active_counts": dict(active_counts),
        "oldest_elapsed": {
            mode: _format_delta(seconds)
            for mode, seconds in oldest_elapsed.items()
        },
        "queue_depths": queue_depths,
    }


def _print_snapshot(snapshot: Dict[str, any], *, tick: int) -> None:
    batch = snapshot["batch"]
    active = snapshot["active_counts"]
    elapsed = snapshot["oldest_elapsed"]
    queues = snapshot["queue_depths"]
    completed = batch.get("completed_count", 0)
    total = batch.get("total_files", 0)
    success = batch.get("success_count", 0)
    failures = batch.get("failure_count", 0)
    fallback_pending = batch.get("fallback_pending", 0)
    status = batch.get("status")
    print(
        f"[{time.strftime('%H:%M:%S')}] tick {tick} | status={status} | "
        f"completed={completed}/{total} (success={success}, failures={failures}) | "
        f"fallback_pending={fallback_pending}"
    )
    print(
        "    queues: "
        + ", ".join(f"{name}={depth}" for name, depth in queues.items())
        + " | active: "
        + ", ".join(f"{mode}={count}" for mode, count in active.items())
    )
    if elapsed:
        print(
            "    longest running: "
            + ", ".join(f"{mode}~{delta}" for mode, delta in elapsed.items())
        )
    print()


def _discover_active_batches(redis_client: redis.Redis) -> List[Tuple[str, Dict[str, Any]]]:
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for key in redis_client.scan_iter('docling_batch:*'):
        if key.endswith(':tasks') or key.endswith(':meta'):
            continue
        payload = redis_client.get(key)
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        status = data.get('status')
        if status in {"RUNNING", "PENDING"}:
            batch_id = key.split(':', 1)[1]
            candidates.append((batch_id, data))
    return candidates


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor batch throughput and queue depth")
    parser.add_argument("batch_id", nargs="?", help="ID of the batch to monitor (auto-detect if omitted)")
    parser.add_argument(
        "--config",
        help="Optional path to config YAML (defaults to auto-detected config)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between samples (default: 60)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    redis_url, queues = _load_config(args.config)
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    chosen_batch = args.batch_id
    if not chosen_batch:
        try:
            candidates = _discover_active_batches(redis_client)
        except redis.RedisError as exc:
            print(f"Failed to discover batches: {exc}", file=sys.stderr)
            return 1

        if not candidates:
            print("No active batches found. Specify a batch ID explicitly.", file=sys.stderr)
            return 1
        if len(candidates) > 1:
            print("Multiple active batches detected:", file=sys.stderr)
            for batch_id, data in candidates:
                print(
                    f"  {batch_id} -> status={data.get('status')} completed={data.get('completed_count', 0)}/{data.get('total_files', 0)}",
                    file=sys.stderr,
                )
            print("Please re-run with the desired batch ID.", file=sys.stderr)
            return 1
        chosen_batch = candidates[0][0]

    print(
        f"Monitoring batch {chosen_batch} every {args.interval}s\n"
        f"Queues: {queues}\nRedis: {redis_url}\n"
    )

    tick = 0
    try:
        while True:
            tick += 1
            snapshot = _sample(redis_client, chosen_batch, queues)
            _print_snapshot(snapshot, tick=tick)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopping monitor.")
        return 0
    except Exception as exc:
        print(f"Monitor failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
