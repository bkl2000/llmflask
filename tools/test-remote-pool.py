#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Remote pool integration tests against a running LLMFlask server.

Usage:
    python3 tools/test-remote-pool.py
    python3 tools/test-remote-pool.py --host SERVER_IP --port 60010
    LLMFLASK_TEST_HOST=SERVER_IP python3 tools/test-remote-pool.py
"""

import argparse
import json
import os
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx is required. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


REQUEST_HEADERS = {"X-LLMFlask-Request": "1"}


@dataclass
class Result:
    passed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def parse_args():
    parser = argparse.ArgumentParser(description="Remote LLMFlask pool integration tests")
    parser.add_argument("--host", default=os.getenv("LLMFLASK_TEST_HOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.getenv("LLMFLASK_TEST_PORT", "5000"), type=int)
    return parser.parse_args()


def base_url(host, port):
    return f"http://{host}:{port}"


# --- test helpers ---

def api_get(base, path, timeout=10):
    resp = httpx.get(f"{base}{path}", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_delete(base, path, timeout=10):
    resp = httpx.delete(f"{base}{path}", headers=REQUEST_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_sse(base, path, method="POST", data=None, files=None, timeout=300):
    client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10))
    if files:
        with client.stream(
            method,
            f"{base}{path}",
            headers=REQUEST_HEADERS,
            data=data or {},
            files=files,
        ) as resp:
            resp.raise_for_status()
            return _parse_sse(resp)
    else:
        with client.stream(
            method, f"{base}{path}", headers=REQUEST_HEADERS, json=data or {}
        ) as resp:
            resp.raise_for_status()
            return _parse_sse(resp)


def _parse_sse(resp):
    events = []
    reader = resp.iter_lines()
    for line in reader:
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# --- tests ---

def test_server_alive(base, result):
    try:
        models = api_get(base, "/api/models")
        assert len(models) > 0, "No models available"
        result.passed.append("test_server_alive")
    except Exception as e:
        result.failed.append(("test_server_alive", str(e)))


def test_pool_list_empty(base, result):
    try:
        pools = api_get(base, "/api/pools")
        assert isinstance(pools, list), "Not a list"
        result.passed.append("test_pool_list_empty")
    except Exception as e:
        result.failed.append(("test_pool_list_empty", str(e)))


def test_pool_invalid_request(base, result):
    try:
        client = httpx.Client(timeout=10)
        resp = client.post(
            f"{base}/api/pool", headers=REQUEST_HEADERS, data={}
        )  # no request field, no file
        assert resp.status_code == 400
        result.passed.append("test_pool_invalid_request")
    except Exception as e:
        result.failed.append(("test_pool_invalid_request", str(e)))


def test_pool_show_nonexistent(base, result):
    try:
        client = httpx.Client(timeout=10)
        resp = client.get(f"{base}/api/pools/nonexistent-zzz")
        assert resp.status_code == 404
        result.passed.append("test_pool_show_nonexistent")
    except Exception as e:
        result.failed.append(("test_pool_show_nonexistent", str(e)))


def test_pool_create_small_csv(base, result):
    """Create a pool from samples/adr.csv and verify success."""
    try:
        sample = Path(__file__).resolve().parent.parent / "samples" / "adr.csv"
        assert sample.is_file(), f"Sample not found: {sample}"

        files = {"file": (sample.name, sample.read_bytes(), "text/csv")}
        data = {"request": "Count the rows in the CSV file. Write the count and a short summary to output/summary.txt.", "model": "ollama/qwen3:8b"}

        events = api_sse(base, "/api/pool", files=files, data=data)
        assert events, "No SSE events received"

        done = events[-1]
        assert done.get("status") == "done", f"Last event not 'done': {done.get('status')}"
        assert done.get("success"), f"Pool failed: {done.get('stderr', '')}"
        assert done.get("pool_name"), "No pool name in done event"

        # verify pool exists
        pool = api_get(base, f"/api/pools/{done['pool_name']}")
        assert pool["name"] == done["pool_name"]

        result.passed.append("test_pool_create_small_csv")
        return done["pool_name"]
    except Exception as e:
        result.failed.append(("test_pool_create_small_csv", str(e)))
        return None


def test_pool_rerun(base, pool_name, result):
    """Re-run an existing pool."""
    if not pool_name:
        result.skipped.append(("test_pool_rerun", "no pool from previous test"))
        return

    try:
        events = api_sse(base, f"/api/pools/{pool_name}/run", data={"model": "ollama/qwen3:8b"})
        assert events, "No SSE events"
        done = events[-1]
        assert done.get("status") == "done"
        assert done.get("success"), f"Re-run failed: {done.get('stderr', '')}"
        result.passed.append("test_pool_rerun")
    except Exception as e:
        result.failed.append(("test_pool_rerun", str(e)))


def test_pool_download(base, pool_name, result):
    """Download pool results and verify extraction."""
    if not pool_name:
        result.skipped.append(("test_pool_download", "no pool from previous test"))
        return

    try:
        client = httpx.Client(timeout=httpx.Timeout(120, connect=10), follow_redirects=True)
        resp = client.get(f"{base}/api/pools/{pool_name}/pack?download=1&without_input=1")
        resp.raise_for_status()
        assert len(resp.content) > 0, "Empty archive"

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "test.tar.gz"
            archive.write_bytes(resp.content)
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(path=tmp)
            # Find extracted pool directory
            dirs = [d for d in Path(tmp).iterdir() if d.is_dir()]
            assert dirs, f"No directory in archive. Contents: {list(Path(tmp).iterdir())}"
            extracted = dirs[0]
            assert (extracted / "scripts").is_dir(), f"scripts/ not in archive. Contents: {list(extracted.iterdir())}"

        result.passed.append("test_pool_download")
    except Exception as e:
        result.failed.append(("test_pool_download", str(e)))


def test_pool_debug(base, pool_name, result):
    """Test pool debug endpoint."""
    if not pool_name:
        result.skipped.append(("test_pool_debug", "no pool from previous test"))
        return

    try:
        info = api_get(base, f"/api/pools/{pool_name}/debug")
        assert "contents" in info, "debug missing contents"
        assert "scripts/main.py" in info["contents"] or any(k.startswith("scripts/") for k in info["contents"])
        result.passed.append("test_pool_debug")
    except Exception as e:
        result.failed.append(("test_pool_debug", str(e)))


def test_pool_delete_single(base, pool_name, result):
    """Delete a single pool."""
    if not pool_name:
        result.skipped.append(("test_pool_delete_single", "no pool from previous test"))
        return

    try:
        info = api_delete(base, f"/api/pools/{pool_name}")
        assert info.get("pool_name") == pool_name or info.get("status") == "deleted"
        result.passed.append("test_pool_delete_single")
    except Exception as e:
        result.failed.append(("test_pool_delete_single", str(e)))


def test_pool_create_large_csv(base, result):
    """Create a pool from samples/energy.csv."""
    try:
        sample = Path(__file__).resolve().parent.parent / "samples" / "energy.csv"
        assert sample.is_file(), f"Sample not found: {sample}"

        files = {"file": (sample.name, sample.read_bytes(), "text/csv")}
        data = {"request": "The CSV uses ; as delimiter. First 5 lines: Id;Datum;Zeit;IL1;UL1. Count the rows. Write results to output/summary.txt.", "model": "ollama/qwen3:8b"}

        events = api_sse(base, "/api/pool", files=files, data=data)
        assert events, "No SSE events"

        done = events[-1]
        # Debug: show all event statusses
        statuses = [e.get("status") for e in events]
        if done.get("status") != "done" or not done.get("success"):
            print(f"  DEBUG events: {statuses}", file=sys.stderr)
            if done.get("stderr"):
                print(f"  DEBUG stderr: {done['stderr'][:300]}", file=sys.stderr)
        if done.get("status") == "error":
            raise RuntimeError(done.get("message", "Unknown error"))
        assert done.get("status") == "done", f"Last event: {done.get('status')} ({done.get('message', '')})"
        assert done.get("success"), f"Pool failed: stderr={done.get('stderr', '').strip()}"
        assert done.get("duration_ms", 0) > 100, f"Too fast: {done.get('duration_ms')}ms"
        result.passed.append("test_pool_create_large_csv")
        return done["pool_name"]
    except Exception as e:
        result.failed.append(("test_pool_create_large_csv", str(e)))
        return None


def test_pool_remove_all(base, result):
    """Remove all pools via DELETE /api/pools."""
    try:
        info = api_delete(base, "/api/pools")
        assert "count" in info, "No count in response"

        pools = api_get(base, "/api/pools")
        assert pools == [], f"Pools still exist after remove all: {pools}"
        result.passed.append("test_pool_remove_all")
    except Exception as e:
        result.failed.append(("test_pool_remove_all", str(e)))


def main():
    args = parse_args()
    base = base_url(args.host, args.port)
    result = Result()

    print(f"=== LLMFlask Remote Pool Tests ===")
    print(f"   Server: {args.host}:{args.port}")
    print(f"   Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start = time.time()

    # Phase 1: connectivity + error handling
    print("--- Phase 1: Connectivity & Error Handling ---")
    test_server_alive(base, result)
    test_pool_list_empty(base, result)
    test_pool_invalid_request(base, result)
    test_pool_show_nonexistent(base, result)

    # Phase 2: lifecycle (small CSV)
    print("\n--- Phase 2: Pool Lifecycle (adr.csv) ---")
    pool_name = test_pool_create_small_csv(base, result)
    test_pool_rerun(base, pool_name, result)
    test_pool_download(base, pool_name, result)
    test_pool_debug(base, pool_name, result)
    test_pool_delete_single(base, pool_name, result)

    # Phase 3: large CSV
    print("\n--- Phase 3: Large CSV (energy.csv) ---")
    time.sleep(0.5)
    large_pool = test_pool_create_large_csv(base, result)

    # Phase 4: cleanup
    print("\n--- Phase 4: Cleanup ---")
    test_pool_remove_all(base, result)

    duration = time.time() - start

    # --- print summary ---
    print()
    print("=" * 50)
    print(f"Results: {len(result.passed)} passed, {len(result.failed)} failed, {len(result.skipped)} skipped")
    print(f"Duration: {duration:.0f}s")
    print("=" * 50)

    for name in result.passed:
        print(f"  [PASS] {name}")

    for name, msg in result.skipped:
        print(f"  [SKIP] {name}: {msg}")

    for name, msg in result.failed:
        print(f"  [FAIL] {name}: {msg}")

    if result.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
