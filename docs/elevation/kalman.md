# Kalman Elevation Board

기준 시점: 2026-03-14

## 현재 목표
- 단일 객체 continuity 안정화
- multi-object에서도 track id를 최대한 유지
- ID switch / fragmentation / false track를 측정 가능한 상태로 만들기
- 제어 이벤트에 쓸 수 있는 안정적인 track 출력 확보

## 구현 및 REQ 목록

### 핵심 구조
- ~~`MultiObjectKalmanTracker` baseline 구현~~
- ~~2D constant velocity state 모델 구현~~
- ~~predict / update 루프 구현~~
- ~~Euclidean distance gate 구현~~
- ~~greedy association 구현~~
- ~~track 생성 / 유지 / 삭제 정책 구현~~
- ~~`min_hits`, `max_misses` 파라미터화~~
- ~~runner 실시간 파이프라인과 연결~~

### 운영/로그
- ~~콘솔에서 `tracks` 수 확인 가능~~
- ~~run summary에 `avg_tracks` 기록~~
- tracker latency 전용 기록
- ID switch count 자동 집계
- fragmentation count 자동 집계
- false track count 자동 집계
- continuity ratio 계산

### 품질 개선
- Hungarian assignment 비교 검토
- Mahalanobis gate 검토
- `Q`, `R` 튜닝 시트 작성
- velocity measurement 활용 여부 검토
- confidence 설계 개선

### 테스트/재현성
- 단일 객체 60초 continuity 테스트
- 2객체 교차 시나리오 테스트
- 일시 미검출 후 재획득 테스트
- track create/delete edge case 테스트

## 이번 달 필수 완료
- 단일 객체 ID switch 측정
- `association_gate`, `max_misses`, `min_hits` 1차 튜닝
- 2객체 시나리오 로그 1건 이상 확보
- `evidence/tracker_metrics.csv` 생성

## 남겨야 할 증거
- `evidence/tracker_metrics.csv`
- track id timeline 그래프
- 단일 객체 continuity 결과
- 교차 시나리오 실패 사례 메모

## 다음 업데이트 때 추가할 것
- Hungarian 비교 결과
- Mahalanobis gate 검토 결과
- ID switch / fragmentation 자동 metric

## 업데이트 로그
- 2026-03-14: 현재 tracker baseline 구현 상태 기준 완료 항목 취소선 정리
- 2026-03-14: association / metric 중심 backlog 재정리
