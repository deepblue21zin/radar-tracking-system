# REQ-SAFETY-POLICY

## 목적

stale data, malformed frame, empty detection, overrun, dropped frame에서 어떻게 fail-safe로 동작할지를 정책으로 명시한다.

핵심 원칙:

- "아무 것도 안 나가게 막는다"도 유효한 정책이다.
- 다만 그 정책이 언제 발동하고, 언제 복구되는지 근거와 기준이 있어야 한다.

## Safety Requirements

| REQ ID | Condition | Detection Rule | Host Action | STM32 Action | Resume Allowed? | Status |
|---|---|---|---|---|---|---|
| REQ-SAFE-001 | `EMPTY_SCENE_VALID` | parser healthy + `frame_age_ms <= 100` + detections 0 | `RESUME` 허용 | normal heartbeat 유지 | Yes | Planned |
| REQ-SAFE-002 | `STALE_DATA` | `frame_age_ms > 100` | `RESUME` 금지, `ALARM` 또는 송신 중단 | timeout stop | No | Planned |
| REQ-SAFE-003 | `MALFORMED_FRAME_BURST` | 최근 1 s 동안 `parse_failures delta > 0` 또는 burst threshold 초과 | `ALARM`, health degrade | stop or hold slow | No | Planned |
| REQ-SAFE-004 | `OVERRUN` | ring buffer overflow / queue overwrite count 증가 | degraded mode, latest-only 유지 | hold safe command | Prefer No | Planned |
| REQ-SAFE-005 | `DROPPED_FRAME_HIGH` | 최근 1 s dropped frame rate threshold 초과 | `SLOW` 또는 `ALARM` | slow or stop | Prefer No | Planned |
| REQ-SAFE-006 | startup / shutdown | valid stream absent | STOP default | STOP default | No | Partial |
| REQ-SAFE-007 | transport timeout | host packet miss `> timeout_ms` | send nothing or unhealthy state | force stop | No | Implemented on STM32 side |

## Policy Table

| Scenario | Health Bits | Host Control Policy | STM32 Policy | Recovery Rule |
|---|---|---|---|---|
| no person, parser healthy | `EMPTY_SCENE_VALID` | `RESUME` 가능 | last valid resume command accepted | next healthy frame |
| person detected, healthy | none or domain-specific object bits | `SLOW/STOP/ALARM` by control logic | obey packet | next evaluated frame |
| parser stale | `STALE_DATA` + `SENSOR_UNHEALTHY` | `RESUME` 금지 | timeout stop | N consecutive healthy frames |
| malformed frame burst | `MALFORMED_FRAME_BURST` + `SENSOR_UNHEALTHY` | `ALARM` | immediate stop or hold stop | burst clear + cooldown |
| dropped frame high | `DROPPED_FRAME_HIGH` | degrade to slow or stop | hold safe command | dropped rate back below threshold |
| overrun | `OVERRUN` | latest-only + control inhibit | hold safe command | overrun counter stable |

## Current Evidence

현재 코드에 이미 있는 안전 단서:

- malformed frame discard + resync counter
- dropped frame estimate
- timeout stop
- emergency stop event 처리

현재 부족한 점:

- host control path가 `EMPTY_SCENE_VALID`와 `SENSOR_UNHEALTHY`를 구분하지 않음
- health gate가 없어 unhealthy 상황에서도 clear-after-N-frames로 `RESUME` 가능
- overrun/dropped burst가 control inhibit로 직접 연결되지 않음

## Recommended Health Gate

host side control transmit 전 아래 gate를 통과해야 한다.

| Check | Threshold | Fail Action |
|---|---|---|
| `frame_age_ms` | `> 100 ms` | `ALARM` or suppress transmit |
| `parse_failures_delta` | `> 0` within short window | mark parser degraded |
| `resync_rate` | threshold 초과 | mark sensor unhealthy |
| `dropped_frame_burst` | threshold 초과 | inhibit resume |
| `buffer_overrun_count` | `> 0` recent window | degraded / stop |

## Recommended Recovery Policy

| Item | Requirement |
|---|---|
| stale recovery | healthy frame 3개 연속 확인 후 clear |
| malformed burst recovery | cooldown window 후 clear |
| dropped frame recovery | recent window rate 정상화 후 clear |
| overrun recovery | queue/buffer utilization 정상화 후 clear |

## Verification Plan

1. UART cable detach / reconnect
2. malformed packet injection
3. artificial delay insertion to trigger stale data
4. forced burst drop in replay or parser shim
5. timeout stop validation on STM32 periodic task

## Portfolio Messaging

- "레이더가 비어 있으면 resume"가 아니라
- "레이더가 건강할 때만 empty scene을 valid로 인정하고, unhealthy면 무조건 safe state로 간다"라고 설명할 수 있어야 한다.
