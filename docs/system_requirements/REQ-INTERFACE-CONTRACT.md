# REQ-INTERFACE-CONTRACT

## 목적

레이더 입력, 내부 추적 결과, health 상태, STM32 제어 패킷의 계약을 명시한다. 핵심은 `EMPTY_SCENE_VALID`와 `SENSOR_UNHEALTHY`를 같은 의미로 다루지 않는 것이다.

## Contract Rules

- unit은 가능한 한 SI 단위를 사용한다.
- endian은 명시한다.
- malformed 조건은 필드별로 정의한다.
- "데이터 없음"과 "센서 이상"은 상태 bit로 분리한다.

## REQ-IF-001 RadarInputFrame

내부 파이프라인 기준 입력 frame 계약:

| Field | Type | Unit | Valid Range | Endian / Source | Malformed Condition |
|---|---|---|---|---|---|
| `magic_word` | bytes[8] | n/a | fixed | TLV packet header | magic mismatch |
| `packet_bytes` | uint32 | bytes | `0 < len <= max_buffer_size` | little-endian header | length <= 0 or > buffer |
| `frame_number` | uint32 | count | monotonic non-negative | parsed TLV header | backward jump without reset policy |
| `num_obj` | uint16 | count | `>= 0` | parsed TLV header | arrays inconsistent with count |
| `num_tlv` | uint16 | count | `>= 1` | parsed TLV header | zero or decode mismatch |
| `sub_frame_number` | uint32 | index | implementation-defined | parsed TLV header | invalid subframe when mode fixed |
| `points[].x/y/z` | float | m | finite | point TLV | NaN / inf |
| `points[].v` | float | m/s | finite | point TLV | NaN / inf |
| `points[].range` | float | m | `>= 0` | derived / parser output | negative |
| `points[].snr` | float | dB or raw unit | finite | parser output | missing / NaN |
| `points[].noise` | float | raw unit | finite | parser output | missing / NaN |

## REQ-IF-002 TrackingOutput

추적 결과는 최소 아래 필드를 제공해야 한다.

| Field | Type | Unit | Meaning | Status |
|---|---|---|---|---|
| `track_id` | int | n/a | stable object identity | Partial |
| `x`, `y`, `z` | float | m | current estimated position | Implemented |
| `vx`, `vy` | float | m/s | planar velocity | Implemented |
| `confidence` | float | 0..1 | track confidence | Partial |
| `state` | enum | n/a | tentative / confirmed / lost / static / moving | Planned |
| `age_frames` | int | frames | track age | Planned |
| `missed_count` | int | frames | consecutive miss count | Planned |
| `source` | enum | n/a | track or cluster fallback | Planned |

## REQ-IF-003 HealthStatus

health/status는 최소 아래 bit를 가져야 한다.

| Bit | Name | Meaning | Resume Allowed? | Current State |
|---|---|---|---|---|
| `0x0001` | `EMPTY_SCENE_VALID` | parser healthy + 최근 frame 정상 + detections 0개 | Yes | Planned |
| `0x0002` | `SENSOR_UNHEALTHY` | parser or transport health degraded | No | Planned |
| `0x0004` | `STALE_DATA` | 최근 frame age가 threshold 초과 | No | Planned |
| `0x0008` | `PARSER_DEGRADED` | parse_fail/resync가 burst threshold 초과 | No | Planned |
| `0x0010` | `DROPPED_FRAME_HIGH` | 최근 dropped rate가 임계 초과 | Prefer No | Planned |
| `0x0020` | `OVERRUN` | buffer/queue overrun 발생 | Prefer No | Planned |
| `0x0040` | `MALFORMED_FRAME_BURST` | malformed frame 연속 발생 | No | Planned |

핵심 정책:

- `EMPTY_SCENE_VALID`는 "사람이 없다"는 의미다.
- `SENSOR_UNHEALTHY`는 "레이더를 신뢰할 수 없다"는 의미다.
- 두 상태는 동시에 참이 되면 안 된다.

## REQ-IF-004 ControlPacket

현재 구현 기준 packet:

| Field | Size | Type | Meaning | Current |
|---|---:|---|---|---|
| header | 2 B | fixed | `0xAA55` | Implemented |
| sequence | 1 B | uint8 | packet sequence | Implemented |
| command | 1 B | enum | STOP/SLOW/RESUME/ALARM | Implemented |
| speed_ratio_pct | 1 B | uint8 | 0..100 % | Implemented |
| event | 1 B | enum | CLEAR / APPROACHING / IN_ZONE / STOPPED / ESTOP | Implemented |
| flags | 1 B | bitfield | inside zone / approaching / changed | Implemented |
| zone_distance_cm | 2 B | uint16 | distance or unavailable sentinel | Implemented |
| closing_speed_cms | 2 B | int16 | signed closing speed | Implemented |
| crc8 | 1 B | uint8 | payload CRC | Implemented |

총 길이: 12 B

### Recommended production extension

| Field | Recommendation |
|---|---|
| `version` | packet version을 명시적으로 추가하거나 reserved bit로 버전 관리 |
| `health_flags` | `EMPTY_SCENE_VALID` / `SENSOR_UNHEALTHY` 등 safety bit 전송 |
| `timeout_policy_ms` | host heartbeat miss 시 STM32가 stop하는 시간 명시 |
| `reserved` | future ABI compatibility 용 비트 예약 |

## Timeout Policy

| Item | Requirement |
|---|---|
| Host heartbeat | `<= 200 ms` 간격으로 유지 권장 |
| STM32 timeout stop | packet 미수신 `> timeout_ms` 시 speed 0 |
| ALARM command | `EMERGENCY_STOP` 또는 unhealthy burst에서 최우선 |
| Boot behavior | valid packet 수신 전까지 STOP 유지 |

## Traceability To Current Code

| Area | File | Evidence |
|---|---|---|
| pipeline contract | `docs/architecture.md` | parsed frame / cluster / track / control output 설명 |
| control packet encoding | `src/communication/control_protocol.py` | fixed packet, flags, CRC8 |
| STM32 receiver | `src/communication/stm32_control_rx_example.c` | parser, timeout stop, emergency stop |

## Recommended Next Implementation

1. health bitfield를 internal runtime result에 추가
2. `EMPTY_SCENE_VALID` vs `SENSOR_UNHEALTHY` 분리
3. control packet revision strategy 명시
4. tracking output에 `age_frames`, `missed_count`, `state` 추가
