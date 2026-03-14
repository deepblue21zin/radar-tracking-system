# Runtime Logging and ROI Plan

## 1. 이 문서의 목적
이 문서는 두 가지를 정리한다.

1. 현재 실행 시 어떤 로그가 어디에 남는지
2. ROI와 실시간성 실험을 어떤 순서로 진행하면 되는지

## 2. 현재 로그는 어떻게 남는가

### 2.1 콘솔 로그
`src/parser/tlv_parse_runner.py`를 실행하면 실시간으로 아래 로그가 출력된다.

프레임 로그 예시:

```text
frame=123 packet=2848B raw=87 filtered=51 clusters=3 tracks=2 parser_ms=2.41 pipe_ms=7.88
```

의미:

- `frame`: 레이더 frame number
- `packet`: 이번 프레임 packet 크기(byte)
- `raw`: 파서가 꺼낸 raw point 수
- `filtered`: 전처리 후 남은 point 수
- `clusters`: DBSCAN cluster 수
- `tracks`: tracker 출력 수
- `parser_ms`: UART read + frame parse 시간
- `pipe_ms`: filter + DBSCAN + tracker 처리 시간

성능 로그 예시:

```text
[PERF] fps=14.8 window=1.01s
```

의미:

- 최근 약 1초 구간에서 실제 처리한 FPS

실행 종료 시 요약 로그 예시:

```text
[SUMMARY] frames=300 avg_fps=14.92 avg_packet=2860.4B avg_parser_ms=2.31 parse_failures=0 resyncs=1 dropped_est=0
```

### 2.2 파일 로그
이제 실행할 때마다 기본적으로 CSV 로그가 자동 저장된다.

저장 위치:

- 프레임별 로그: `evidence/runtime_logs/frames_YYYYMMDD_HHMMSS.csv`
- 실행 요약 로그: `evidence/runtime_logs/run_summary.csv`

즉, 이제는 `실행할 때마다 자동 기록된다`.

단, 아래 옵션을 쓰면 끌 수 있다.

```bash
--disable-file-log
```

## 3. CSV에는 무엇이 기록되는가

### 3.1 프레임별 로그
프레임 로그에는 아래가 기록된다.

- `run_id`
- `scenario`
- `roi_tag`
- `wall_time`
- `elapsed_sec`
- `frame_number`
- `frame_gap`
- `packet_bytes`
- `num_obj`
- `num_tlv`
- `sub_frame_number`
- `raw_points`
- `filtered_points`
- `clusters`
- `tracks`
- `parser_latency_ms`
- `pipeline_latency_ms`
- `parse_failures_so_far`
- `resync_events_so_far`
- `dropped_frames_estimate_so_far`

이 로그는 `한 프레임 단위`로 자세히 보는 용도다.

### 3.2 실행 요약 로그
`run_summary.csv`에는 실행 1회당 1줄이 추가된다.

주요 컬럼:

- `run_id`
- `started_at`, `ended_at`, `duration_sec`
- `scenario`, `roi_tag`
- `frames_processed`
- `avg_fps`
- `avg_packet_bytes`
- `avg_num_obj`
- `avg_raw_points`
- `avg_filtered_points`
- `avg_clusters`
- `avg_tracks`
- `avg_parser_latency_ms`
- `avg_pipeline_latency_ms`
- `bytes_received`
- `parse_failures`
- `resync_events`
- `invalid_packet_events`
- `dropped_frames_estimate`

이 로그는 `실험 비교표`를 만들 때 핵심이다.

## 4. ROI 실험을 왜 해야 하는가
ROI는 `필요한 영역만 보겠다`는 뜻이다.

ROI를 줄이면 보통 아래 효과를 기대할 수 있다.

- packet 크기 감소
- point 수 감소
- DBSCAN 연산량 감소
- tracking 안정성 개선
- FPS 상승 가능

하지만 ROI를 잘못 잡으면 아래 문제가 생긴다.

- 필요한 객체가 잘림
- 추적이 끊김
- 제어 대상이 ROI 밖으로 나가면 miss 발생

그래서 ROI 실험은 감으로 하면 안 되고, `숫자 기반`으로 해야 한다.

## 5. 현업 기준 ROI 적용 우선순위

### 5.1 1순위: 센서 출력량 자체를 줄이는 ROI
가장 효과가 크다.

이 경우:

- packet 크기 자체가 줄어든다
- UART 부담도 줄어든다
- parser 이전 단계부터 이득이 생긴다

### 5.2 2순위: 파싱 후 software ROI
파싱은 다 한 뒤, filter 단계에서 작업영역만 남기는 방식이다.

이 경우:

- UART 부담은 그대로
- 하지만 DBSCAN/tracker 계산량은 줄일 수 있다

### 5.3 3순위: 번갈아 ROI 수집
예를 들어 위/아래를 교대로 받는 방식이다.

장점:

- 순간 packet 크기 감소 가능

단점:

- 각 영역의 실제 업데이트 주파수가 떨어진다
- tracking continuity가 흔들릴 수 있다
- 제어 반응속도가 나빠질 수 있다

따라서 MVP 단계에서는 보통 1순위와 2순위를 먼저 본다.

## 6. ROI 실험 계획표

### 실험 A. Baseline
- ROI 없음 또는 현재 기본 설정
- 목표: 현재 avg packet / avg fps / avg parser ms 기준선 확보

### 실험 B. 작업영역 고정 ROI
- 실제 컨베이어 또는 관심영역만 포함
- 목표: packet 감소량, FPS 증가량 확인

### 실험 C. range gate 강화
- 가까운 clutter, 너무 먼 point 제외
- 목표: raw/filtered point 감소와 tracking 영향 확인

### 실험 D. z 또는 y축 분리 ROI
- 위/아래 또는 높이 방향 분리
- 목표: 특정 시나리오에서만 의미 있는지 확인

### 실험 E. 교차 ROI 수집
- 위 프레임은 상단, 다음 프레임은 하단
- 목표: 정말 UART 병목이 심할 때만 실험

## 7. 각 ROI 실험에서 꼭 봐야 할 숫자
실험마다 최소 아래 숫자를 비교해야 한다.

- `avg_fps`
- `avg_packet_bytes`
- `avg_parser_latency_ms`
- `avg_pipeline_latency_ms`
- `avg_raw_points`
- `avg_filtered_points`
- `avg_clusters`
- `parse_failures`
- `dropped_frames_estimate`

추적 품질도 같이 봐야 한다.

- ID switch
- false track
- continuity

즉 FPS만 좋아지고 tracking이 망가지면 실패다.

## 8. 15 FPS 목표를 맞추기 위한 추천 순서

### Step 1. 지금 baseline을 60초 측정
먼저 바꾸지 말고 현재 상태를 측정한다.

권장 예시:

```bash
python src/parser/tlv_parse_runner.py ^
  --cli-port COM6 ^
  --data-port COM5 ^
  --config path\\to\\profile.cfg ^
  --duration 60 ^
  --scenario baseline ^
  --roi-tag full_frame
```

### Step 2. packet 크기부터 본다
`avg_packet_bytes`가 크면 UART 병목일 수 있다.

### Step 3. point 수를 본다
`avg_raw_points`, `avg_filtered_points`가 많으면 후단 계산량이 문제일 수 있다.

### Step 4. 고정 ROI 적용
가장 먼저 검토할 ROI는 작업영역 고정 ROI다.

### Step 5. filter 강화
- `snr_threshold`
- `min_range`
- `max_range`
- 필요 시 `z gate`

를 조정해서 불필요한 point를 줄인다.

### Step 6. 그다음에야 교차 ROI 검토
이건 마지막 카드다.

## 9. 실험 결과 해석 예시

### 좋은 경우
- `avg_packet_bytes` 감소
- `avg_fps` 증가
- `avg_parser_latency_ms` 유지 또는 감소
- `clusters`, `tracks` 품질 유지

이 경우 ROI가 실제로 도움이 된 것이다.

### 나쁜 경우
- `avg_packet_bytes`는 줄었는데 track continuity가 나빠짐
- `avg_fps`는 올랐는데 false track 증가
- dropped frame은 줄었는데 ID switch 증가

이 경우 ROI가 너무 공격적이거나, 중요 영역을 잘랐을 가능성이 크다.

## 10. 추천 운영 방식
- 모든 실험은 `--scenario`, `--roi-tag`를 붙여서 실행한다.
- 한 실험은 최소 60초 이상 측정한다.
- 동일한 사람 이동 시나리오로 3회 반복 측정한다.
- `run_summary.csv`를 기준으로 먼저 비교하고, 이상한 run만 frame CSV를 자세히 본다.

## 11. 한 줄 결론
ROI는 좋은 최적화 방법이지만, `어디서 줄일지`와 `무엇이 실제 병목인지`를 구분하는 게 핵심이다.

이제 이 프로젝트는 실행할 때마다 자동으로 로그가 남으므로, 감으로 튜닝하지 말고 `baseline -> 고정 ROI -> filter 강화 -> 마지막에 교차 ROI` 순서로 실험하면 된다.
