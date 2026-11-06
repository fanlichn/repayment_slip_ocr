#!/usr/bin/env python3
"""Reproducible benchmark for POST /ocr_url using only the standard library."""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_manifest(path: Path) -> list[dict]:
    cases = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        case = json.loads(raw)
        if not case.get("id") or not case.get("url"):
            raise ValueError(f"{path}:{number}: id/url required")
        case.setdefault("expect", {})
        cases.append(case)
    if not cases:
        raise ValueError("manifest is empty")
    return cases


def post_case(base: str, case: dict, mode: str, run: int, timeout: float) -> dict:
    body = json.dumps({"image_url": case["url"]}).encode("utf-8")
    request = urllib.request.Request(
        f"{base.rstrip('/')}/ocr_url",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    status = 0
    response_body = b""
    error = ""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_body = exc.read()
        error = str(exc)
    except Exception as exc:  # benchmark must retain failed samples
        error = repr(exc)
    elapsed_ms = (time.perf_counter() - started) * 1000

    parsed = {}
    if response_body:
        try:
            parsed = json.loads(response_body)
        except Exception:
            error = error or "invalid_json"
    expected = case.get("expect") or {}
    mismatches = {
        key: {"expected": value, "actual": parsed.get(key)}
        for key, value in expected.items()
        if parsed.get(key) != value
    }
    return {
        "mode": mode,
        "case_id": case["id"],
        "run": run,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 3),
        "field_count": len(expected),
        "field_matches": len(expected) - len(mismatches),
        "accuracy": (
            round((len(expected) - len(mismatches)) / len(expected), 6)
            if expected
            else 1.0
        ),
        "mismatches": json.dumps(mismatches, ensure_ascii=False, sort_keys=True),
        "error": error,
        "response": json.dumps(parsed, ensure_ascii=False, sort_keys=True),
    }


def print_summary(rows: list[dict]) -> None:
    for mode in sorted({row["mode"] for row in rows}):
        selected = [row for row in rows if row["mode"] == mode]
        elapsed = [row["elapsed_ms"] for row in selected if row["status"] == 200]
        if not elapsed:
            print(f"{mode}: no successful requests")
            continue
        elapsed_sorted = sorted(elapsed)
        p95_index = min(len(elapsed_sorted) - 1, int(len(elapsed_sorted) * 0.95))
        wall_seconds = sum(elapsed) / 1000 if mode == "serial" else None
        print(
            f"{mode}: n={len(selected)} ok={len(elapsed)} "
            f"mean_ms={statistics.fmean(elapsed):.1f} "
            f"p50_ms={statistics.median(elapsed):.1f} "
            f"p95_ms={elapsed_sorted[p95_index]:.1f} "
            f"mean_accuracy={statistics.fmean(row['accuracy'] for row in selected):.4f}"
            + (f" summed_request_seconds={wall_seconds:.2f}" if wall_seconds else "")
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--serial", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--concurrent-requests", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output", type=Path, default=Path("ocr_benchmark.csv"))
    args = parser.parse_args()
    cases = load_manifest(args.manifest)

    for index in range(args.warmup):
        for case in cases:
            result = post_case(args.base, case, "warmup", index + 1, args.timeout)
            if result["status"] != 200:
                raise RuntimeError(
                    f"warmup failed for {case['id']}: {result['status']} {result['error']}"
                )

    rows = []
    for run in range(1, args.serial + 1):
        for case in cases:
            rows.append(post_case(args.base, case, "serial", run, args.timeout))

    concurrent_wall = 0.0
    if args.concurrent_requests > 0:
        jobs = [
            (cases[index % len(cases)], index + 1)
            for index in range(args.concurrent_requests)
        ]
        concurrent_started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.concurrency
        ) as executor:
            futures = [
                executor.submit(
                    post_case, args.base, case, "concurrent", run, args.timeout
                )
                for case, run in jobs
            ]
            rows.extend(future.result() for future in futures)
        concurrent_wall = time.perf_counter() - concurrent_started

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print_summary(rows)
    if args.concurrent_requests > 0:
        print(
            f"concurrent_wall_seconds={concurrent_wall:.3f} "
            f"throughput_rps={args.concurrent_requests / concurrent_wall:.4f}"
        )
    print(f"csv={args.output}")
    return 0 if all(row["status"] == 200 and row["accuracy"] == 1.0 for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
