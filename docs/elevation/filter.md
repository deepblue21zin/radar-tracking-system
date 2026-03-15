# Filter Elevation Board

기준 시점: 2026-03-14

## 현재 목표
- DBSCAN 전에 불필요한 point를 최대한 줄이기
- ROI / threshold를 통해 실시간성과 안정성을 동시에 확보
- 작업영역만 남기는 filter 전략 정리

## 구현 및 REQ 목록

### 핵심 구조
- ~~parser output dict-of-arrays -> point list 변환 구현~~
- ~~SNR threshold filter 구현~~
- ~~noise upper bound filter 구현~~
- ~~range gate(`min_range`, `max_range`) 구현~~
- ~~z gate(`z_min`, `z_max`) 구현~~
- ~~runner와 preprocess 단계 연결~~

### 운영/로그
- ~~raw point 수 / filtered point 수 콘솔 로그 반영~~
- ~~run summary에 `avg_raw_points`, `avg_filtered_points` 기록~~
- filter ratio(`filtered/raw`) 계산 및 기록
- scenario별 filter 설정값 문서화
- filter 전/후 시각화 자동 저장

### 품질 개선
- static clutter 제거 전략 추가
- range-dependent threshold 설계
- 작업영역 ROI preset 정의
- conveyor zone 전용 ROI preset 정의
- velocity 기반 pre-filter 검토

### 테스트/재현성
- 단일 객체 시나리오 filter 전/후 비교
- 2객체 시나리오 filter 전/후 비교
- 저 SNR 환경 filter 효과 비교
- false reject / over-filter 사례 정리

## 이번 달 필수 완료
- 현재 filter 설정으로 60초 baseline 확보
- 작업영역 고정 ROI preset 1개 정리
- `avg_raw_points -> avg_filtered_points` 감소 효과 기록
- over-filter 발생 사례 1건 이상 정리

## 남겨야 할 증거
- `evidence/runtime_logs/run_summary.csv`
- filter 전/후 point 수 비교표
- `experiments/` 시각화 이미지
- ROI 실험 결과 메모

## 다음 업데이트 때 추가할 것
- static clutter map
- adaptive threshold
- filter ratio summary

## 업데이트 로그
- 2026-03-14: 현재 `noise_filter.py` 기준 완료 항목 정리
- 2026-03-14: ROI/실시간성 실험 관점 backlog 추가
