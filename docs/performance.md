# OCR performance benchmark

The timing instrumentation is opt-in and writes only to the server log. It
does not add fields to the API response.

## Baseline environment

For the first run, keep the current worker and thread configuration unchanged:

```ini
[Service]
Environment=NIC_OCR_STAGE_TIMING_LOG=true
Environment=NIC_OCR_OCR_MAX_CONCURRENT_REQUESTS_PER_WORKER=1
Environment=NIC_OCR_CDM_ADAPTIVE_EARLY_STOP=false
Environment=NIC_OCR_FAST_PREPROCESSING=false
```

After editing the systemd unit:

```bash
sudo systemctl daemon-reload
sudo systemctl restart repayment-ocr
systemctl show repayment-ocr -p MainPID -p Environment
```

Do not set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
`OPENBLAS_NUM_THREADS`, `NIC_OCR_PADDLE_CPU_THREADS`, or
`NIC_OCR_OPENCV_THREADS` for the baseline unless they were already present.

For the optimized run, change
`NIC_OCR_CDM_ADAPTIVE_EARLY_STOP=true` and
`NIC_OCR_FAST_PREPROCESSING=true`, restart the service, and repeat the same
commands. This makes before/after comparable from one code revision.

## Sequential and concurrent requests

Run from the repository root:

```bash
python scripts/bench_ocr_url.py \
  --manifest scripts/commercial_benchmark.jsonl \
  --base http://127.0.0.1:8000 \
  --warmup 1 \
  --serial 5 \
  --concurrency 4 \
  --concurrent-requests 8 \
  --output benchmark-before.csv
```

The script exits with code 2 if an expected field changes. Keep the generated
CSV and the corresponding `repayment_ocr.log`.

## Per-core CPU, threads, and memory

Install `sysstat` if necessary, then collect these alongside the benchmark:

```bash
mpstat -P ALL 1 > mpstat-before.txt &
MPSTAT_PID=$!

WORKER_PID=$(pgrep -n -f 'uvicorn repayment_slip_ocr.main:app')
pidstat -t -u -r -p "$WORKER_PID" 1 > pidstat-before.txt &
PIDSTAT_PID=$!

python scripts/bench_ocr_url.py \
  --manifest scripts/commercial_benchmark.jsonl \
  --base http://127.0.0.1:8000 \
  --warmup 1 --serial 5 --concurrency 4 --concurrent-requests 8 \
  --output benchmark-before.csv

kill "$MPSTAT_PID" "$PIDSTAT_PID"
grep -E 'VmRSS|Threads' "/proc/$WORKER_PID/status"
```

Linux `top` reports one fully used logical core as roughly 100% for a process;
use `mpstat -P ALL` and `pidstat -t` before concluding that Paddle uses only
one core.

## Thread matrix

Change one configuration at a time and restart the service for every row.
Never compare runs from different images or machines.

1. One worker, Paddle threads 1, 2, then 4.
2. For each candidate, compare OpenCV threads 1 and 2 only if preprocessing is
   material in the timing log.
3. Only when the single-worker peak RSS leaves safe headroom, compare two
   workers with two Paddle threads each.

Example systemd environment for one matrix point:

```ini
Environment=NIC_OCR_PADDLE_CPU_THREADS=2
Environment=NIC_OCR_OPENCV_THREADS=1
Environment=OMP_NUM_THREADS=2
Environment=MKL_NUM_THREADS=2
Environment=OPENBLAS_NUM_THREADS=1
```

`workers × Paddle threads` should normally not exceed the four available CPU
cores. Two workers load two model copies, so RSS must be measured before that
configuration is accepted.

## Required comparison

Report, for both before and after:

- serial mean, p50, and p95 latency;
- concurrent wall time and throughput;
- per-core CPU and worker thread activity;
- peak RSS;
- field accuracy from the benchmark CSV;
- timing totals for `image_download`, `image_decode`, `image_preprocess`,
  `ocr_detection`, `ocr_recognition`, each `ocr_band_*`,
  `field_extraction`, and `result_assembly`.

Do not claim a production improvement from local development-machine results.
