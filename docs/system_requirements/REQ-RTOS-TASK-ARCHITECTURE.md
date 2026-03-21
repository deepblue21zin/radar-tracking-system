# REQ-RTOS-TASK-ARCHITECTURE

## 목적

레이더 SW를 RTOS 기반 양산 구조로 설명하기 위해, task period, priority, queue depth, worst-case latency, buffer size 요구사항을 명시한다.

현재 구현은 Python host runtime이지만, 아래 요구사항은 STM32/FreeRTOS 또는 동등한 RTOS로 이식할 때 기준이 되는 target architecture다.

## Current Baseline

현재 코드에서 이미 확인되는 실무형 요소:

- 고정 크기 byte buffer 기반 UART frame reader: `MMWaveSerialReader(max_buffer_size=2**17)`
- latest snapshot only viewer buffer
- 10 ms periodic control loop 예제

아직 없는 요소:

- FreeRTOS task/queue 정의
- priority/period/WCET trace 표
- overflow policy와 health monitor task의 명시적 분리

## Task-Level Requirements

| REQ ID | Task | Trigger / Period | Priority | Queue / Buffer | Target WCET | Status | Verification |
|---|---|---:|---:|---|---:|---|---|
| REQ-RTOS-001 | `RadarRxTask` | event-driven (UART DMA HT/TC or ISR notify) | 5 | ring buffer 16 KB minimum | <= 1 ms | Planned | DMA callback timestamp + enqueue time |
| REQ-RTOS-002 | `FrameParseTask` | 20 ms periodic or frame-ready event | 4 | frame queue depth 2 | <= 3 ms | Partial | parser latency log + max/p95 summary |
| REQ-RTOS-003 | `TrackTask` | 20 ms periodic | 3 | cluster queue depth 2 | <= 5 ms | Partial | pipeline latency decomposition |
| REQ-RTOS-004 | `ControlTxTask` | 10 ms periodic | 4 | control queue depth 4 | <= 1 ms | Partial | tx timestamp + timeout stop validation |
| REQ-RTOS-005 | `HealthMonitorTask` | 100 ms periodic | 2 | health event queue depth 8 | <= 0.5 ms | Planned | fault injection + health status transition log |
| REQ-RTOS-006 | Viewer / Debug path | best effort only | 1 or host thread | latest snapshot only | n/a | Partial | dropped render does not block control |
| REQ-RTOS-007 | Post-init allocation | startup 이후 dynamic allocation 금지 | n/a | bounded static objects only | 0 alloc | Planned | allocator hook / heap trace |

## Recommended FreeRTOS Reference Mapping

| Task | Responsibility | Input | Output | Failure Containment |
|---|---|---|---|---|
| `RadarRxTask` | UART DMA buffer 수집, magic-word 경계까지 raw byte 확보 | UART DMA ISR notify | raw ring buffer | overflow 시 oldest discard + health event |
| `FrameParseTask` | TLV header 검증, packet length 검증, point decode | raw ring buffer | parsed frame queue | malformed frame discard + parse_fail counter |
| `TrackTask` | preprocess, DBSCAN, tracker, control candidate 결정 | parsed frame queue | track/control queue | empty frame와 unhealthy frame 구분 |
| `ControlTxTask` | safety gate 통과 후 MCU packet 송신 | control queue | UART packet | timeout/health bad 시 STOP or ALARM |
| `HealthMonitorTask` | stale/resync/drop/overrun 상태 평가 | counters + timestamps | health status bitfield | degraded state broadcast |

## Bounded Buffer Rules

| Item | Requirement |
|---|---|
| UART raw buffer | 16 KB minimum, overwrite-oldest policy documented |
| Parsed frame queue | depth 2, newest frame 우선 |
| Cluster/track queue | depth 2, 늦은 consumer는 old frame drop 허용 |
| Control queue | depth 4, latest command wins but STOP has highest priority |
| Health queue | depth 8, duplicate event coalescing 허용 |

## Reference Timing Budget

| Stage | Target Budget |
|---|---:|
| UART ingest + ring push | 1 ms |
| TLV parse + frame validation | 3 ms |
| preprocess + cluster + track | 5 ms |
| control decision + packet encode | 1 ms |
| health monitor evaluation | 0.5 ms |
| end-to-end decision latency budget | 20 ms nominal / 30 ms max target |

## Traceability To Current Code

| Current Evidence | File | Interpretation |
|---|---|---|
| fixed-size byte buffer | `src/parser/runtime_pipeline.py` | RTOS의 bounded ring buffer로 치환 가능한 구조 |
| latest-only snapshot buffer | `src/visualization/live_rail_viewer.py` | debug consumer는 queue depth 1 정책을 이미 따름 |
| periodic timeout stop | `src/communication/stm32_control_rx_example.c` | `ControlTxTask` + `HealthMonitorTask`의 핵심 fail-safe 단서 |

## Recommended Next Implementation

1. `src/communication/` 아래에 `freertos_radar_app_skeleton.c/.h` 추가
2. `RadarRxTask`, `FrameParseTask`, `ControlTxTask` skeleton 생성
3. queue depth, task priority, timeout constants를 헤더에 명시
4. startup 이후 allocation 금지 여부를 검증하는 hook 추가
