# Radar SW Requirements Package

이 폴더는 레이더 SW를 "실험용 알고리즘 프로젝트"가 아니라 "양산형 임베디드 SW 후보 아키텍처"로 설명하기 위한 요구사항 명세 패키지다.

목표:
- RTOS/주기 task 구조를 명시적으로 설명한다.
- 성능을 평균값뿐 아니라 worst-case/P95 기준으로 비교 가능하게 만든다.
- 입출력 계약과 health/status bit를 문서화한다.
- stale data, malformed frame, overrun, dropped frame에 대한 fail-safe 정책을 명시한다.

바로 보기:
- [REQ HTML Portal](./index.html)
- [REQ-RTOS-TASK-ARCHITECTURE](./REQ-RTOS-TASK-ARCHITECTURE.md)
- [REQ-PERFORMANCE-BENCHMARK](./REQ-PERFORMANCE-BENCHMARK.md)
- [REQ-INTERFACE-CONTRACT](./REQ-INTERFACE-CONTRACT.md)
- [REQ-SAFETY-POLICY](./REQ-SAFETY-POLICY.md)

## Package Summary

| Domain | Intent | Current State | Main Gap |
|---|---|---|---|
| RTOS task architecture | Radar Rx / Parse / Track / Control / HealthMonitor를 주기 task로 분리 | Partial | priority/period/queue depth/WCET 표와 FreeRTOS reference skeleton 부재 |
| Performance benchmark | avg/max/p95 latency, fps, drop, CPU, memory를 before/after로 비교 | Partial | summary가 avg 중심이고 CPU/RAM/alloc 계측 부재 |
| Interface contract | radar input, tracking output, health/status, control packet 계약 명시 | Partial | EMPTY_SCENE와 SENSOR_UNHEALTHY 구분 부족 |
| Safety policy | stale/malformed/overrun/dropped 시 fail-safe 정책 정의 | Partial | host health gate와 제어 차단 규칙 부재 |

## Current Evidence Already Present

- 파이프라인 구조 설명: [`docs/architecture.md`](../architecture.md)
- 런타임 실행/운영 설명: [`README.md`](../../README.md)
- 실패 모드 초안: [`docs/FMEA.md`](../FMEA.md)
- 실시간 파이프라인 구현: [`src/parser/runtime_pipeline.py`](../../src/parser/runtime_pipeline.py)
- 제어 패킷 계약: [`src/communication/control_protocol.py`](../../src/communication/control_protocol.py)
- STM32 timeout/periodic receiver example: [`src/communication/stm32_control_rx_example.c`](../../src/communication/stm32_control_rx_example.c)

## Recommended Portfolio Positioning

이 프로젝트는 현재 Python host 기반 실시간 레이더 파이프라인이지만, 아래 항목을 명세화하면 자동차 SW 포트폴리오에서 다음처럼 설명할 수 있다.

- "실시간 radar perception host prototype를 설계했고, 이를 RTOS task 구조와 fail-safe 정책으로 추상화했다."
- "고정 길이 packet, CRC, timeout stop, bounded buffer, parser health counter를 설계했다."
- "양산형 전환 시 필요한 task period/priority/WCET/queue depth 요구사항을 정의했다."

## Reading Order

1. [`REQ-RTOS-TASK-ARCHITECTURE.md`](./REQ-RTOS-TASK-ARCHITECTURE.md)
2. [`REQ-INTERFACE-CONTRACT.md`](./REQ-INTERFACE-CONTRACT.md)
3. [`REQ-SAFETY-POLICY.md`](./REQ-SAFETY-POLICY.md)
4. [`REQ-PERFORMANCE-BENCHMARK.md`](./REQ-PERFORMANCE-BENCHMARK.md)
