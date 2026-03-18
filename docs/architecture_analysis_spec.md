# Radar Tracking System 아키텍처 분석 명세서

> 참고: 이 문서는 `2026-03-02` 기준 초기 분석 스냅샷이다.  
> 현재 실행 구조는 `README.md`, `docs/architecture.md`, `docs/doxygen_overview.md`, `docs/study/study_runtime_pipeline_and_control.md`를 우선 참고한다.

## 1. 문서 목적
현재 `radar-tracking-system`의 폴더 구조와 초기 코드 상태를 기준으로,
- 모듈 경계
- 데이터 흐름
- 의존성
- 구조적 리스크
- 우선 개선 과제
를 명확히 정의한다.

기준 시점: 2026-03-02

## 2. 분석 범위
분석 대상:
- `docs/architecture.md`
- `docs/FMEA.md`
- `docs/performance_log.md`
- `src/parser/tlv_parse_runner.py`
- `src/parser/tlv_packet_parser.py`
- `src/filter/noise_filter.py`
- `src/tracking/tracker_utils.c`
- `src/tracking/tracker_utils.h`
- `src/communication/stm32_uart_tx.c`

비분석 대상:
- `experiments/*.png`, `evidence/latency_graph.png` (placeholder 파일)

## 3. 현재 아키텍처 요약
시스템은 파이프라인 구조를 목표로 한다.
1. Parser: TLV 바이너리 프레임 파싱 (실시간 UART 스트리밍)
2. Filter: 노이즈 제거
3. Tracking: 클러스터링 + 상태추정
4. Communication: STM32 송신

현재 상태는 "프로젝트 스캐폴드 + 실시간 parser 연결" 단계다.

## 4. 모듈별 상세 분석

### 4.1 Parser (`src/parser`)
구성:
- `tlv_packet_parser.py`: TLV 헤더/매직워드 기반 저수준 파싱
- `tlv_parse_runner.py`: UART 버퍼링, 프레임 경계 탐지, 실시간 프레임 출력

강점:
- `IWR6843-Read-Data-Python-MMWAVE-SDK-main` 구조를 반영해 실시간 수신 경로 확보
- 매직워드 동기화 + 패킷 길이 검증 포함
- GUI 의존성 없이 headless 실행 가능

리스크/이슈:
- `pyserial` 런타임 의존성 필요
- TLV type 1, 7 중심 파싱(다른 TLV 확장은 추가 필요)
- 프레임 드롭/지연 메트릭 로깅은 아직 미구현

### 4.2 Filter (`src/filter`)
구성:
- `noise_filter.py`: SNR threshold 필터 1개 함수

강점:
- 최소 기능으로 인터페이스가 단순함

리스크/이슈:
- 거리/속도/공간 연속성 기반 필터 미구현
- 파서 출력과의 타입 계약 고정 필요

### 4.3 Tracking (`src/tracking`)
구성:
- `tracker_utils.c/.h`: TI tracking utility 코드 일부

강점:
- SDK 계열 트래킹 유틸 참조로 튜닝 파라미터 구조 존재

리스크/이슈:
- TI SDK/RTOS 헤더 의존성이 강해 현재 레포 단독 빌드 불가
- Python parser 파이프라인과 직접 연결된 adapter 없음

### 4.4 Communication (`src/communication`)
구성:
- `stm32_uart_tx.c`: 전송 함수 스텁

강점:
- STM32 송신 인터페이스 시작점 확보

리스크/이슈:
- 패킷 포맷/CRC/재시도 정책 미정

### 4.5 Docs / Evidence
강점:
- 아키텍처/FMEA/성능 로그 기본 문서 존재

리스크/이슈:
- 성능 로그 자동 수집 경로 미구현
- evidence 이미지는 placeholder 상태

## 5. 데이터 흐름 명세 (As-Is)

### 5.1 논리 흐름
`Radar UART -> MMWaveSerialReader -> TLV packet parser -> points dict -> (미연결) filter -> (미연결) tracking -> (미연결) stm32 tx`

### 5.2 계약 현황
- 입력 계약: CLI/Data 포트 + cfg 파일
- 중간 계약: `ParsedFrame(frame_number, num_obj, points)`
- 출력 계약: 문서상 정의, 코드 미연결

## 6. 구조 적합성 평가

### 6.1 목표 구조 대비 적합도
- 폴더 구조 적합도: 높음
- Parser 실시간 적합도: 중상
- End-to-end 연결성: 낮음

### 6.2 핵심 병목
1. filter/tracking/communication 미연결
2. tracking 모듈의 TI SDK 종속
3. 성능 지표 수집 자동화 부재

## 7. 아키텍처 리스크 우선순위

### P0 (즉시)
1. parser 출력을 filter 입력으로 연결하는 파이프라인 엔트리 추가
2. `ParsedFrame -> Track` 데이터 모델 고정
3. frame drop/fps/latency 로깅 추가

### P1 (단기)
1. Filter 확장: SNR + 거리 + 속도 복합 규칙
2. Python baseline tracking(DBSCAN+Kalman) 추가
3. STM32 packet protocol 명세화

### P2 (중기)
1. 실제 실험 이미지/그래프 자동 저장
2. 회귀 테스트(파싱 정확도/성능) 추가

## 8. 즉시 실행 가능한 액션 체크리스트
- [x] parser를 실시간 UART 기반으로 교체
- [ ] parser -> filter -> tracking -> tx E2E 연결
- [ ] 성능 측정 스크립트 추가
- [ ] 통신 프로토콜 문서 추가

## 9. 결론
요청한 실시간 적합성 관점에서 parser는 개선되었다.
다음 단계의 핵심은 parser 이후 모듈을 연결해 실제 추적 파이프라인을 완성하는 것이다.
