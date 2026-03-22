# REQ-PERFORMANCE-BENCHMARK

## 목적

"동작한다" 수준이 아니라 "얼마나 빨라졌고, 얼마나 안정화됐는지"를 보여주기 위한 성능 요구사항과 benchmark 형식을 정의한다.

## Current Baseline

현재 summary에 이미 있는 항목:

- `avg_fps`
- `avg_parser_latency_ms`
- `avg_pipeline_latency_ms`
- `dropped_frames_estimate`
- `parse_failures`
- `resync_events`

현재 부족한 항목:

- `max_parser_latency_ms`
- `max_pipeline_latency_ms`
- `p95_parser_latency_ms`
- `p95_pipeline_latency_ms`
- host CPU %
- peak RSS / peak memory
- startup 이후 allocation count

## Performance Requirements

| REQ ID | Requirement | Current State | Status | Verification |
|---|---|---|---|---|
| REQ-PERF-001 | summary는 avg/max/p95 parser latency를 기록해야 한다 | avg only | Planned | `run_summary.csv` column check |
| REQ-PERF-002 | summary는 avg/max/p95 pipeline latency를 기록해야 한다 | avg only | Planned | `run_summary.csv` column check |
| REQ-PERF-003 | run report는 before/after benchmark 표를 포함해야 한다 | partial manual | Partial | `docs/perf_benchmark.md` update |
| REQ-PERF-004 | host benchmark는 CPU %와 peak RSS를 같이 기록해야 한다 | absent | Planned | psutil sampling or OS perf capture |
| REQ-PERF-005 | STM32 reference path는 startup 이후 dynamic allocation 0회를 목표로 한다 | not instrumented | Planned | heap hook / allocator counter |
| REQ-PERF-006 | viewer path는 runtime/control path를 block하지 않아야 한다 | worker split exists | Partial | parser-only vs viewer run comparison |
| REQ-PERF-007 | benchmark는 dropped/resync/parse_fail을 latency와 함께 본다 | partially logged | Partial | experiment report review |

## Required Benchmark Axes

| Category | Metric | Why |
|---|---|---|
| Throughput | `avg_fps` | 지속 처리 성능 |
| Latency | `avg_parser_ms`, `max_parser_ms`, `p95_parser_ms` | packet decode 안정성 |
| Latency | `avg_pipeline_ms`, `max_pipeline_ms`, `p95_pipeline_ms` | end-to-end responsiveness |
| Continuity | `parse_failures`, `resync_events`, `dropped_frames_estimate` | 실시간 신뢰성 |
| Utilization | `cpu_percent`, `peak_rss_mb` | host 부하 근거 |
| Embedded fit | `post_init_alloc_count`, `heap_peak_bytes` | 양산형 설계 적합성 |

## Benchmark Table Template

| Scenario | Before | After | Delta | Evidence |
|---|---:|---:|---:|---|
| Avg parser latency (ms) | TBD | TBD | TBD | `run_summary.csv` |
| Max parser latency (ms) | TBD | TBD | TBD | new summary field |
| P95 parser latency (ms) | TBD | TBD | TBD | new summary field |
| Avg pipeline latency (ms) | TBD | TBD | TBD | `run_summary.csv` |
| Max pipeline latency (ms) | TBD | TBD | TBD | new summary field |
| P95 pipeline latency (ms) | TBD | TBD | TBD | new summary field |
| Avg FPS | TBD | TBD | TBD | `run_summary.csv` |
| Dropped frame estimate | TBD | TBD | TBD | `run_summary.csv` |
| Parse failures | TBD | TBD | TBD | `run_summary.csv` |
| Resync events | TBD | TBD | TBD | `run_summary.csv` |
| CPU usage (%) | TBD | TBD | TBD | perf capture |
| Peak RSS (MB) | TBD | TBD | TBD | perf capture |
| Post-init alloc count | TBD | TBD | TBD | allocator hook |

## Recommended Code Changes

### 1. Summary columns to add

- `max_parser_latency_ms`
- `max_pipeline_latency_ms`
- `p95_parser_latency_ms`
- `p95_pipeline_latency_ms`
- `cpu_percent_avg`
- `peak_rss_mb`

### 2. Experiment report additions

- Before vs After delta table
- top 3 latency spikes
- parser health degradation note

### 3. STM32-oriented metrics

- startup 이후 `malloc/free` 호출 0회
- static queue / static task stack 사용 여부
- watchdog timeout or heartbeat miss count

## Recommended Verification Strategy

1. parser-only 60 s baseline
2. viewer enabled 60 s comparison
3. health gate enabled 60 s comparison
4. same scene replay with parameter-only change

## Portfolio Example Statement

- "parser avg latency를 줄였다"보다
- "avg parser latency 2.8 ms -> 1.9 ms, p95 pipeline latency 41 ms -> 19 ms, dropped frame estimate 23 -> 4, viewer enabled 상태에서도 avg FPS 9.2 -> 13.7로 개선"처럼 말할 수 있어야 한다.
