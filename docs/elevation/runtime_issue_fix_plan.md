# Runtime Issue Fix Plan

기준 시점: 2026-03-16

이 문서는 현재 실제 운영 중인 파이프라인

`TLV Parsing -> Filter -> DBSCAN -> Kalman Tracking -> Visualization`

에서 확인된 문제와, 각 문제를 어떤 순서로 해결하면 좋은지 정리한 실행 계획서다.

---

## 1. 지금 확인된 상태 요약

### 1.1 현재 환경/의존성 상태
- 현재 확인한 Python 버전: `3.13.7`
- 현재 import 확인 결과:
  - `pyserial`: 설치됨
  - `numpy`: 설치됨
  - `filterpy`: pip 설치본이 아니라 `src/filterpy-master` fallback 경로에서 로드됨
  - `scikit-learn`: 설치 안 됨

### 1.2 최근 로그 기준 관측된 증상
- `evidence/runtime_logs/frames_20260315_170410.csv`
  - 약 `53.24초` 동안 `342 frame` 기록
  - 실효 FPS 약 `6.42`
  - 마지막 누적 상태:
    - `parse_failures = 81`
    - `resync_events = 1401`
    - `dropped_frames_estimate = 193`
  - `avg_pipeline_latency_ms ≈ 24.0`
  - `max_pipeline_latency_ms ≈ 4929.7`
- 같은 프레임 로그에서 `raw_points == filtered_points`가 `342/342` 프레임으로 확인됨
  - 즉, 현재 필터는 코드상 연결돼 있지만 최근 캡처에서는 사실상 점을 거의 못 줄이고 있음
- 같은 프레임 로그에서 `tracks > clusters`가 `208/342` 프레임으로 확인됨
  - 평균 `clusters ≈ 3.114`
  - 평균 `tracks ≈ 4.529`
  - 즉, 트래커 출력이 현재 scene 대비 과하게 유지되거나 쪼개질 가능성이 있음

### 1.3 지금 가장 먼저 해결해야 하는 순서
1. DBSCAN 실행 환경 정상화
2. TLV parser 안정화
3. filter를 실제로 점을 줄이는 상태로 튜닝
4. Kalman tracker lifecycle / association 정책 튜닝

이 순서를 추천하는 이유는 다음과 같다.
- `scikit-learn`이 없으면 DBSCAN 자체가 불안정하거나 비활성화될 수 있다.
- parser가 불안정하면 뒤 단계의 filter / tracking 품질 평가가 왜곡된다.
- filter가 점을 거의 줄이지 못하면 DBSCAN/Tracker에 불필요한 점이 그대로 들어간다.
- tracker는 입력 품질(parser/filter/cluster)에 가장 크게 영향을 받는다.

---

## 2. DBSCAN 문제와 해결 방법

## 현재 문제
- `src/cluster/dbscan_cluster.py`는 `numpy + scikit-learn`이 있어야 동작한다.
- 현재 환경에서는 `scikit-learn`이 없어서 `cluster_points()` 호출 시 `ImportError`가 발생한다.
- `src/plot_dbscan.py`도 같은 이유로 현재 환경에서 직접 실행 실패한다.

## 가장 안전한 설치 방법

현재 프로젝트 `README.md`는 Python `3.10` 또는 `3.11` 환경을 권장한다.
현재 사용 중인 Python `3.13.7`은 프로젝트 권장 범위를 벗어나 있으므로, 가장 안전한 방법은 새 환경을 만드는 것이다.

### 권장 방법: 새 conda 환경 생성 후 requirements 설치

```bash
conda create -n mmwave_env python=3.11 -y
conda activate mmwave_env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 최소 설치만 하고 싶을 때

```bash
python -m pip install numpy==1.26.4 scikit-learn==1.5.2
```

### 장기적으로는 같이 설치하는 것이 좋은 패키지

```bash
python -m pip install pyserial==3.5 numpy==1.26.4 scikit-learn==1.5.2 filterpy==1.4.5 matplotlib==3.9.2
```

## 왜 Python 3.11 환경을 권장하나
- 현재 프로젝트 문서와 `requirements.txt`가 사실상 `3.10/3.11` 계열을 기준으로 관리되고 있다.
- 현재는 `filterpy`도 pip 설치본이 아니라 `src/filterpy-master` fallback으로 로드되고 있다.
- 즉, 지금 환경은 "일부는 설치, 일부는 vendor fallback, 일부는 미설치" 상태다.
- 새 환경을 만들고 `requirements.txt`로 맞추면 DBSCAN과 tracker 환경을 훨씬 일관되게 평가할 수 있다.

## 설치 후 바로 확인할 것

```bash
python - <<'PY'
from src.cluster.dbscan_cluster import cluster_points
pts = [
    {'x':0.0,'y':0.0,'z':0.0,'v':0.0,'snr':10.0,'noise':1.0,'range':1.0},
    {'x':0.1,'y':0.1,'z':0.0,'v':0.0,'snr':10.0,'noise':1.0,'range':1.0},
    {'x':0.2,'y':0.0,'z':0.0,'v':0.0,'snr':10.0,'noise':1.0,'range':1.0},
    {'x':0.1,'y':-0.1,'z':0.0,'v':0.0,'snr':10.0,'noise':1.0,'range':1.0},
]
print(cluster_points(pts, eps=0.5, min_samples=2))
PY
```

## 해결 완료 기준
- `cluster_points()` 더미 데이터 테스트 통과
- `tlv_parse_runner.py` 실행 중 DBSCAN 관련 `ImportError` 경고 없음
- 실시간 로그에서 `clusters=` 값이 계속 찍힘

---

## 3. Filter 문제와 해결 방법

## 현재 문제
- 현재 filter는 `SNR`, `noise`, `range`, `z` 게이트만 적용한다.
- 최근 로그에서는 `raw_points == filtered_points`가 전 프레임에서 동일하게 나왔다.
- 즉, 코드상 연결은 되어 있지만 현재 파라미터/전략으로는 실제 정제 효과가 거의 없다.

## 왜 이런 일이 생기나
- 현재 `snr_threshold=8.0`이 scene에 비해 너무 낮을 수 있다.
- `max_noise`, `max_range`, `z_min`, `z_max`가 실험에서 거의 안 쓰였을 가능성이 있다.
- 현재 filter에는 `x/y ROI`, `static clutter`, `velocity` 기반 reject가 없다.
- 그래서 작업영역 밖 점, 벽/바닥/레일 주변 점, 정지 clutter가 그대로 DBSCAN에 들어간다.

## 가장 먼저 바꿔야 할 것

### 3.1 filter 효과를 숫자로 먼저 보이게 만들기
지금은 `raw_points`, `filtered_points` 개수는 남지만, 왜 안 줄었는지 판단 정보가 부족하다.

추가 추천 로그:
- `filter_ratio = filtered / raw`
- frame별 `snr` 최소/평균/상위 percentile
- frame별 `range` 최소/최대
- 선택 샘플의 `(x, y, z, snr, noise)`

최소 KPI:
- `avg_filtered_points < avg_raw_points`
- 단일 객체 시나리오에서 clutter가 줄어드는지 시각적으로 확인

적용 상태:
- 2026-03-17 기준 `filter_ratio`, `snr/range` 통계, sample preview 로그를 runner/frame CSV에 반영했다.

### 3.2 x/y ROI gate 추가
현재 filter에는 `z`만 있고 `x/y` 작업영역 제한이 없다.

추천 파라미터:
- `x_min`, `x_max`
- `y_min`, `y_max`

이유:
- 레이더는 실제 작업영역 밖 반사점이 많다.
- DBSCAN 전에 공간 ROI를 잘라주는 것이 가장 효과가 크다.

예시 전략:
- 측정 대상이 rail 우측/전방이라면
  - `x`: 관심 영역 폭만 남기기
  - `y`: 너무 가까운 점/너무 먼 점 제거

### 3.3 static clutter 제거 규칙 추가
현재는 정적인 배경점이 그대로 남을 가능성이 크다.

간단한 1차 규칙:
- `abs(v) < v_min` 이면서
- 특정 ROI 안의 고정 배경점이면 제거

주의:
- 실제 타깃도 순간적으로 속도가 0에 가까울 수 있으므로, velocity만으로 바로 버리면 안 된다.
- `SNR + 위치 + 속도`를 함께 보는 게 안전하다.

적용 상태:
- 2026-03-17 기준 near-front keepout, right-rail keepout, `abs(v) < v_min` + low/moderate SNR 기반 static clutter reject를 1차로 반영했다.

### 3.4 range-dependent threshold 검토
먼 거리로 갈수록 SNR/노이즈 분포가 달라질 수 있다.

추천 방식:
- near / mid / far 구간으로 나누고
- 구간별 `snr_threshold`, `max_noise`를 다르게 적용

예시:
- `0~2m`: 느슨한 SNR
- `2~5m`: 중간
- `5m 이상`: 더 강한 threshold

## 권장 수정 순서
1. 현재 scene에서 `snr`, `noise`, `range` 분포를 1회 수집
2. `x/y ROI` 먼저 추가
3. `snr_threshold`를 8.0에서 단계적으로 올려 보기
4. `max_noise` 제한 추가
5. 필요 시 velocity/static clutter rule 추가

## 검증 방법
- 같은 장면에서 다음 3개를 비교한다:
  - raw point 수
  - filtered point 수
  - cluster 수 안정성
- 목표:
  - raw 대비 filtered가 눈에 띄게 줄어야 한다
  - single-object에서 cluster가 불안정하게 늘어나면 안 된다
  - over-filter로 타깃 자체가 사라지면 안 된다

## 해결 완료 기준
- `raw != filtered`가 대부분 프레임에서 발생
- 단일 객체에서 clutter가 확실히 감소
- filter 적용 후 DBSCAN cluster 수 분산이 줄어듦

---

## 4. TLV Parser 문제와 해결 방법

## 현재 문제
- 최근 로그에서 `parse_failures`, `resync_events`, `dropped_frames_estimate`가 높다.
- 프레임 로그 첫 부분에 `frame_number=3356` 뒤에 `1, 2, 3...`로 이어지는 비정상적인 시작 패턴이 보인다.
- 이는 startup 시점 버퍼 정리 부족, resync 정책의 과도한 손실, fail reason 세분화 부족 가능성을 시사한다.

## 가장 먼저 의심되는 지점

### 4.1 runner는 config 후 `data_port.reset_input_buffer()`를 하지 않는다
- `live_rail_viewer.py`는 `send_config()` 후 잠깐 대기한 뒤 `data_port.reset_input_buffer()`를 호출한다.
- `tlv_parse_runner.py`는 현재 그 단계가 없다.
- 따라서 startup 직후 stale byte / 중간 패킷 조각이 남아서 첫 프레임이 뒤틀릴 가능성이 있다.

즉시 추천 수정:
- `tlv_parse_runner.py`에서도
  - `send_config(cli_port, config_path)`
  - `time.sleep(0.2)`
  - `data_port.reset_input_buffer()`
  순서를 추가해 viewer와 동일하게 맞춘다.

### 4.2 fail reason이 너무 뭉뚱그려져 있다
지금은 `parse_failures` 한 숫자만 올라가므로 원인을 나눠서 보기 어렵다.

추천 fail taxonomy:
- `no_magic_word`
- `invalid_total_packet_len`
- `incomplete_packet`
- `next_header_magic_mismatch`
- `invalid_num_tlv`
- `tlv_len_invalid`
- `type1_missing_when_num_obj_gt_0`
- `struct_unpack_error`

이렇게 나누면 실제로 문제가
- serial sync인지
- packet 손상인지
- parser 로직 문제인지
빨리 구분된다.

### 4.3 invalid packet 시 shift 정책이 너무 보수적이다
현재 `read_frame()`는 invalid packet 길이가 나오면 `1 byte`만 밀고 다시 본다.

이 방식의 문제:
- 잡음이 많은 경우 resync가 매우 느려질 수 있다.
- 한 번 틀어진 뒤 복구에 불필요하게 많은 프레임이 손실될 수 있다.

추천 개선:
- 현재 위치 이후의 다음 `MAGIC_WORD`를 buffer 안에서 다시 검색해서
- 찾으면 그 위치까지 한 번에 shift
- 못 찾으면 마지막 7바이트만 남기고 버리기

### 4.4 1회 read -> 1회 parse 구조의 병목 가능성
현재는 읽고 나서 complete packet이 있어도 한 프레임씩만 처리한다.

추천 개선:
- `while buffer has complete packet` 형태로
- 한 번 append 후 가능한 만큼 연속 파싱
- backlog를 줄여 frame gap / dropped estimate를 완화

## 추천 수정 순서
1. startup 후 `data_port.reset_input_buffer()` 추가
2. fail reason counter 세분화
3. resync 시 다음 magic word jump 방식으로 개선
4. 가능한 complete packet을 한 번에 여러 개 파싱하는 구조로 개선
5. 실패 시 raw dump 몇 바이트 저장 기능 추가

## 검증 방법
- 동일한 cfg / 포트 / duration으로 60초 3회 반복
- 비교 항목:
  - `parse_failures`
  - `resync_events`
  - `dropped_frames_estimate`
  - `avg_parser_latency_ms`
  - `avg_fps`
- 목표:
  - `parse_failures`, `resync_events`, `dropped_frames_estimate` 모두 크게 감소
  - 첫 프레임 번호가 비정상 jump 없이 시작

## 해결 완료 기준
- 60초 run에서 startup anomaly 재발 없음
- `parse_failures`와 `resync_events`가 baseline 대비 유의미하게 감소
- `dropped_frames_estimate`가 현저히 감소

---

## 5. Kalman Tracking 문제와 해결 방법

## 현재 문제
- 최근 로그에서 reported track 수가 cluster 수보다 큰 경우가 많다.
- 이는 다음 중 하나일 가능성이 있다.
  - stale track가 오래 남음
  - cluster fragmentation이 track 증가로 이어짐
  - association gate가 느슨함
  - lifecycle 정책이 scene에 비해 보수적이지 않음

주의:
- 현재 캡처된 run의 정확한 실행 인자(`report_miss_tolerance`, `max_misses`)는 frame CSV에 저장되지 않았으므로,
  최종 원인 판단 전에 실제 run 인자를 함께 기록하는 것이 좋다.

## 현재 구현의 한계
- state model: 2D constant velocity
- gate: Euclidean distance
- association: greedy nearest-first
- lifecycle: `min_hits`, `max_misses`, `report_miss_tolerance`

이 baseline은 시작점으로는 좋지만, 실제 scene이 복잡해질수록 아래 문제가 생기기 쉽다.
- ID switch
- fragmentation
- false track
- cluster 수보다 많은 stale/over-split track 표시

## 가장 먼저 바꿔야 할 것

### 5.1 run 인자와 track 품질 metric을 같이 남기기
현재는 `avg_tracks`는 기록되지만,
- `association_gate`
- `max_misses`
- `min_hits`
- `report_miss_tolerance`
조합과 결과를 한 번에 비교하기 어렵다.

추천:
- `evidence/tracker_metrics.csv`를 따로 만들고
- run별 parameter + ID metric + ghost metric을 함께 저장

### 5.2 lifecycle을 tentative / confirmed로 나누기
현재도 `min_hits`가 있지만 상태 머신이 명시적이지 않다.

추천 상태:
- `tentative`
- `confirmed`
- `deleted`

추천 정책:
- 생성 직후는 `tentative`
- 연속 hit가 일정 횟수 이상일 때만 `confirmed`
- miss가 누적되면 `deleted`

효과:
- 단발성 잡음으로 track가 바로 화면에 나타나는 현상 감소
- 발표/시연 화면에서 false track 감소

### 5.3 gate를 더 보수적으로 시작해보기
지금은 `association_gate=1.5`가 baseline이다.

추천 1차 sweep:
- `0.8`
- `1.0`
- `1.2`
- `1.5`

같이 볼 파라미터:
- `max_misses = 2, 3, 4`
- `min_hits = 2, 3`
- `report_miss_tolerance = 0`

### 5.4 cluster confidence / size를 measurement noise에 반영
현재 tracker는 모든 측정에 같은 `R`을 쓴다.

추천 개선:
- cluster size가 작고 confidence가 낮으면 `R`을 크게
- cluster가 크고 안정적이면 `R`을 작게

효과:
- 품질이 나쁜 cluster에 tracker가 과하게 끌려가는 문제를 줄일 수 있다.

### 5.5 중기적으로는 association 개선 검토
현재 greedy association은 간단하지만, 객체가 가까워지면 ID switch에 취약하다.

중기 후보:
- Hungarian assignment
- Mahalanobis gate
- velocity-aware association

바로 여기까지 갈 필요는 없고, 먼저 lifecycle + gate + metric 정리부터 하는 것이 현실적이다.

## 추천 수정 순서
1. track metric CSV 추가
2. run 인자 기록 강화
3. `association_gate`, `max_misses`, `min_hits` sweep
4. tentative/confirmed 상태머신 추가
5. adaptive `R` 적용
6. 필요 시 Hungarian / Mahalanobis 검토

## 검증 방법
- 단일 객체 60초
- 2객체 분리
- 교차
- 일시 미검출 후 재획득

측정할 것:
- `avg_tracks`
- `tracks > clusters` 프레임 비율
- ID switch count
- fragmentation count
- false track count

## 해결 완료 기준
- `tracks > clusters` 비율 감소
- 단일 객체에서 continuity 향상
- 2객체 상황에서 ID 유지 개선
- 발표/시각화 화면에서 ghost track 감소

---

## 6. 바로 실행할 실무 체크리스트

### 오늘 바로 할 것
1. Python `3.11` 환경 생성 후 `pip install -r requirements.txt`
2. `tlv_parse_runner.py`에 `send_config()` 이후 `data_port.reset_input_buffer()` 추가
3. filter에 `x/y ROI` 파라미터 설계
4. 60초 baseline을 다시 1회 수집

### 그 다음 할 것
1. parser fail reason 세분화
2. filter ratio / point distribution 기록 추가
3. tracker parameter sweep
4. `evidence/parser_benchmark.csv`, `evidence/tracker_metrics.csv` 생성

---

## 7. 한 줄 결론

현재 파이프라인은 "전체 연결은 되어 있지만",
- DBSCAN 환경은 완전히 정리되지 않았고
- parser는 안정성이 부족하며
- filter는 실효성이 낮고
- tracker는 품질 튜닝이 아직 필요하다.

가장 좋은 전략은

`환경 정상화 -> parser 안정화 -> filter 실효화 -> tracker 튜닝`

순서로 가는 것이다.
