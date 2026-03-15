# Elevation Board

## 목적
이 폴더는 `개발 진척 보드`다.

원칙:

- 이미 구현된 항목은 삭제하지 않는다.
- 완료된 항목은 `~~취소선~~`으로 남긴다.
- 새 요구사항이나 업데이트가 생기면 아래에 계속 추가한다.
- 실험 후에는 관련 파일에 결과와 다음 액션을 업데이트한다.

즉 이 폴더는 "무엇을 했는지"와 "무엇이 남았는지"를 동시에 보여주는 기록판이다.

## 사용 방법

### 1. 완료 처리
완료된 항목은 아래처럼 남긴다.

- ~~Magic word 기반 frame sync 구현~~

### 2. 미완료 항목
아직 남은 항목은 일반 bullet로 유지한다.

- parser fail reason 세분화

### 3. 새 요구사항 추가
새 요구사항은 기존 리스트 맨 아래나 `추가 backlog` 섹션에 계속 붙인다.

### 4. 실험 결과 반영
실험이 끝나면:

- 무엇을 바꿨는지
- 어떤 로그를 남겼는지
- 다음에 무엇을 할지

를 각 파트 문서에 적는다.

## 파트 문서
- `TLV_parsing.md`
- `filter.md`
- `DBSCAN.md`
- `kalman.md`

## 공통 운영 기준
- 기준 시점: 2026-03-14
- 우선순위: `MVP 15 FPS 달성 -> 안정성 확보 -> 품질 개선 -> 제어 연동`
- 실험 결과는 `evidence/`와 `docs/performance_log.md`에도 같이 반영한다.

## 공통 체크포인트
- `avg_fps`
- `avg_packet_bytes`
- `avg_parser_latency_ms`
- `avg_pipeline_latency_ms`
- `parse_failures`
- `resync_events`
- `dropped_frames_estimate`

## 한 줄 요약
이 폴더는 할 일을 "지우는" 문서가 아니라, `취소선으로 남기면서 발전을 추적하는 문서`다.
