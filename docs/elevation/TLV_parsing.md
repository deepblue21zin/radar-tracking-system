# TLV Parsing Elevation Board

기준 시점: 2026-03-14

## 현재 목표
- UART TLV 스트림을 안정적으로 파싱
- `Type 1`, `Type 7`을 정확히 해석
- parser latency / failure / resync를 수치로 관리
- 실기기 10분 이상 안정 실행 근거 확보

## 구현 및 REQ 목록

### 핵심 구조
- ~~UART reader + byte buffer 구조 구현~~
- ~~magic word 기반 frame sync 구현~~
- ~~header에서 `total_packet_num_bytes`, `frame_number`, `num_det_obj`, `num_tlv`, `sub_frame_number` 해석 구현~~
- ~~`TLV type 1` detected points 파싱 구현~~
- ~~`TLV type 7` snr/noise 파싱 구현~~
- ~~parser 결과를 `ParsedFrame` 구조로 반환하도록 연결~~
- ~~직접 스크립트 실행 경로 보완~~

### 안정성
- ~~malformed TLV 길이 검증 및 fail 처리~~
- ~~unpack 예외 발생 시 fail 처리~~
- ~~기본 resync 동작 구현~~
- ~~`num_det_obj > 0`인데 `Type 1` payload가 없으면 frame fail 처리~~
- ~~cfg 적용 시 CLI 응답(`Done`/`Error`) 콘솔 확인 가능하도록 보강~~
- frame fail reason을 더 세분화해서 기록
- raw byte overflow 발생 여부 계측
- frame gap 원인 분류 로직 추가
- parser success rate를 parser 전용 CSV로 정리

### 성능/로그
- ~~실시간 콘솔 frame 로그 출력~~
- ~~1초 window FPS 로그 출력~~
- ~~실행 시 frame CSV 자동 저장~~
- ~~실행 시 run summary CSV 자동 저장~~
- ~~`packet_bytes`, `parser_latency_ms`, `parse_failures`, `resync_events`, `dropped_frames_estimate` 기록~~
- parser 전용 `parser_benchmark.csv` 정리
- p95 parser latency 계산 및 기록
- 장시간 실행(10분/20분) summary 누적

### 테스트/재현성
- good packet fixture 저장
- bad packet fixture 저장
- parser 단위 테스트 작성
- frame gap / partial frame / wrong length 재현 테스트 작성
- raw dump 샘플 확보

### 통합
- ~~filter 입력 계약 유지 (`x, y, z, v, range, snr, noise`)~~
- DBSCAN/Kalman과 연결된 상태에서 parser 병목 여부 확인
- sensor-side ROI 적용 전/후 packet 크기 비교

## 이번 달 필수 완료
- 10,000 frame 기준 parser success rate 측정
- 10분 연속 실행 로그 확보
- `avg_packet_bytes`, `avg_parser_latency_ms`, `parse_failures`, `resync_events` 정리
- corrupted frame 이후 복구 사례 1건 이상 확보
- `evidence/parser_benchmark.csv` 생성

## 남겨야 할 증거
- `evidence/runtime_logs/run_summary.csv`
- `evidence/runtime_logs/frames_*.csv`
- `evidence/parser_benchmark.csv`
- raw dump sample
- 정상/비정상 로그 캡처
- parser latency 그래프

## 다음 업데이트 때 추가할 것
- fail reason taxonomy
- parser benchmark 스크립트
- fixture 기반 unit test

## 업데이트 로그
- 2026-03-14: 현재 구현 상태를 기준으로 완료 항목 취소선 정리
- 2026-03-14: runtime CSV logging 연동 상태 반영
- 2026-03-15: `Type 1` 누락 frame fail 처리 반영
- 2026-03-15: cfg apply 응답 로그 출력 반영
