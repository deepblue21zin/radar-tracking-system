# DBSCAN Elevation Board

기준 시점: 2026-03-14

## 현재 목표
- point cloud를 안정적인 객체 cluster로 변환
- single-object에서는 1 cluster 유지
- multi-object에서는 병합/과분할을 줄이기
- tracker 입력 품질을 안정화

## 구현 및 REQ 목록

### 핵심 구조
- ~~`cluster_points()` baseline 구현~~
- ~~`(x, y)` feature clustering 구현~~
- ~~옵션으로 `(x, y, v)` feature clustering 구현~~
- ~~cluster centroid / mean velocity / size / confidence 출력 구현~~
- ~~runner 실시간 파이프라인과 연결~~

### 운영/로그
- ~~콘솔에서 `clusters` 수 확인 가능~~
- ~~run summary에 `avg_clusters` 기록~~
- noise point count 자동 기록
- single-object 1 cluster ratio 계산
- 2객체 separation success rate 계산
- DBSCAN latency를 파트 전용 CSV로 정리

### 품질 개선
- velocity feature scaling 추가
- 거리별 adaptive `eps` 검토
- scene preset별 `eps`, `min_samples` 표 정리
- confidence를 point count 외 지표까지 반영
- false cluster 사례 분류

### 테스트/재현성
- parameter sweep 자동화
- on/off velocity feature 비교 실험
- 단일 객체 / 2객체 / 교차 시나리오 비교
- far range / low SNR 사례 정리

## 이번 달 필수 완료
- baseline `eps`, `min_samples` 후보 3세트 확보
- 단일 객체 1 cluster 유지율 측정
- 2객체 분리 성공률 측정
- `evidence/dbscan_param_sweep.csv` 생성

## 남겨야 할 증거
- `evidence/dbscan_param_sweep.csv`
- raw vs clustered 이미지
- single / multi-object 비교표
- velocity feature on/off 결과

## 다음 업데이트 때 추가할 것
- noise ratio logging
- adaptive eps
- confidence 개선

## 업데이트 로그
- 2026-03-14: baseline clustering 구현 상태를 기준으로 완료 항목 취소선 정리
- 2026-03-14: 현재 남은 핵심 backlog를 KPI 중심으로 재정리
