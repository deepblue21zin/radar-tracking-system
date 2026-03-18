# Tracking / DBSCAN 발표용 차별화 계획

기준 시점: 2026-03-15

## 1. 왜 이 문서가 필요한가
지금 구조를 냉정하게 보면,

- `DBSCAN`은 `scikit-learn`
- `Kalman Filter`는 `FilterPy`

를 사용하고 있다.

이건 잘못이 아니다.
현업에서도 수학 라이브러리, 최적화 라이브러리, 검증된 오픈소스를 쓰는 건 아주 일반적이다.

문제는 `우리가 무엇을 직접 설계했는지`를 설명하지 못할 때 생긴다.

즉 발표에서 중요한 건

- 알고리즘 이름을 말하는 것

보다,

- 그 알고리즘을 `레이더 실시간 추적 문제`에 맞게 어떻게 바꿨는지
- 어떤 근거로 튜닝했는지
- 무엇이 baseline이고 무엇이 우리 개선인지

를 보여주는 것이다.

## 2. 지금 상태를 정직하게 평가하면

### 2.1 DBSCAN
현재 [dbscan_cluster.py](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/cluster/dbscan_cluster.py)는 다음 수준이다.

- `scikit-learn`의 `DBSCAN` 호출
- feature는 `(x, y)` 또는 `(x, y, v)` 선택
- clustering 결과를 centroid / mean velocity / size / confidence로 요약

즉 지금 단계에서 정직하게 말하면:

`DBSCAN 알고리즘 자체를 구현한 것은 아니다.`

대신 아직 말할 수 있는 것은 있다.

- radar point를 cluster measurement로 바꾸는 파이프라인을 연결했다
- feature 선택과 cluster-level output format은 우리가 정했다

하지만 발표에서 강하게 가져가려면 더 필요하다.

### 2.2 Kalman / Tracking
현재 [kalman_tracker.py](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/tracking/kalman_tracker.py)는 다음 수준이다.

- `FilterPy`의 `KalmanFilter` 사용
- 2D constant velocity model 구성
- predict / update 루프 구성
- distance gate + greedy association
- track 생성 / 삭제 / `min_hits`, `max_misses` 정책

즉 지금 단계에서 정직하게 말하면:

`Kalman 수식 계산은 FilterPy를 활용했고, tracker 구조와 상태 관리 로직은 우리가 구성했다.`

이건 DBSCAN보다 한 단계 더 "우리 작업"이 이미 들어가 있다.
왜냐하면 tracker 성능은 필터 수식만으로 결정되지 않고,

- 어떤 state를 쓰는지
- 어떤 measurement를 넣는지
- 어떻게 association 하는지
- 언제 track를 살리고 죽이는지

가 더 크게 작용하기 때문이다.

## 3. 발표에서 이렇게 말하면 된다

### 3.1 말해도 되는 표현
- `DBSCAN core implementation은 sklearn을 사용했고, 우리는 레이더용 feature engineering, parameter tuning, cluster 후처리, 평가 지표 설계를 담당했다.`
- `Kalman filter 수식 계산은 FilterPy를 사용했고, 우리는 radar-specific state model, gating, association, lifecycle, runtime evaluation을 설계했다.`
- `핵심 기여는 라이브러리 사용 자체가 아니라, 레이더 실시간 추적 문제에 맞는 시스템 엔지니어링과 튜닝이다.`

### 3.2 피해야 하는 표현
- `DBSCAN을 직접 구현했다`
- `Kalman filter를 처음부터 전부 구현했다`
- `추적 알고리즘을 완전히 새로 만들었다`

이건 면접에서 바로 꼬일 수 있다.

## 4. 발표에서 "우리 기여"로 만들기 위한 핵심 전략
핵심은 아래 3개다.

### 전략 1. baseline과 개선판을 분리한다
지금 상태를 `baseline`으로 명확히 둔다.

그 다음,

- baseline DBSCAN
- tuned DBSCAN
- baseline tracker
- tuned tracker

를 비교한다.

그러면 발표에서 이렇게 말할 수 있다.

`처음에는 라이브러리 기본 형태로 시작했고, 이후 레이더 특성에 맞게 우리가 직접 튜닝 및 구조 개선을 수행했다.`

### 전략 2. 레이더 도메인 지식을 반영한다
그냥 라이브러리 호출이 아니라, `레이더 데이터 특성`을 코드에 녹여야 한다.

예:

- 거리별 point density 차이
- velocity 신뢰도 차이
- SNR/noise 기반 quality 차이
- frame drop / partial miss 상황

이런 걸 반영하면 "실제 문제 해결"이 된다.

### 전략 3. 수치와 로그로 증명한다
말만 하면 약하다.

반드시 아래처럼 남겨야 한다.

- baseline vs tuned 비교표
- FPS 변화
- cluster separation success rate
- ID switch 감소
- continuity ratio 증가

## 5. DBSCAN 파트에서 꼭 변형해야 하는 것

### 5.1 Feature engineering
현재는 `(x, y)` 또는 `(x, y, v)`만 쓴다.

이걸 아래처럼 발전시키는 게 좋다.

#### A. velocity scaling
속도를 그냥 좌표와 같은 비중으로 넣으면 안 맞을 수 있다.

예:

```text
feature = [x, y, alpha_v * v]
```

여기서 `alpha_v`를 우리가 직접 튜닝한다.

이건 발표에서 말하기 좋다.

- `DBSCAN 자체는 라이브러리를 사용했지만, 레이더 속도 특성을 반영하기 위해 velocity scaling을 직접 설계했다.`

#### B. range-aware feature
가까운 거리와 먼 거리의 point 밀도가 다를 수 있다.

그래서:

- near zone
- mid zone
- far zone

별로 clustering 기준을 다르게 가져갈 수 있다.

### 5.2 Adaptive `eps`
지금은 `eps`가 고정이다.

발전 방향:

- `0~2m`: 작은 `eps`
- `2~4m`: 중간 `eps`
- `4m 이상`: 큰 `eps`

이렇게 하면 거리별 density 차이를 반영할 수 있다.

발표 문장:

`고정 eps 대신 거리 구간별 adaptive eps를 적용해 과분할과 병합 문제를 완화했다.`

### 5.3 Cluster 후처리 규칙
DBSCAN 결과를 그대로 tracker에 넘기지 말고, 후처리를 넣는 게 좋다.

예:

- cluster size가 너무 작으면 제거
- cluster extent가 너무 크면 이상 cluster로 분류
- cluster 내부 속도 분산이 너무 크면 분할 후보로 표시

이건 아주 좋은 "우리 로직"이 된다.

### 5.4 Confidence 재설계
지금 confidence는 사실상 `point count` 기반이다.

발전 방향:

- size
- 평균 snr
- noise 수준
- range

를 합쳐 confidence를 만든다.

그러면 tracker 쪽에서도 더 의미 있게 쓸 수 있다.

### 5.5 DBSCAN 파트 발표용 목표
최소한 아래까지 가면 충분히 말할 수 있다.

- velocity scaling 추가
- adaptive `eps` 또는 zone preset 추가
- cluster reject/merge/split rule 일부 추가
- baseline vs tuned 비교표 확보

## 6. Kalman / Tracking 파트에서 꼭 변형해야 하는 것

### 6.1 FilterPy는 남겨도 된다
이건 먼저 명확히 하자.

`FilterPy를 쓰는 것 자체는 문제 아니다.`

현업에서도 Kalman 수식을 다 손으로 다시 구현하는 게 핵심이 아니다.
더 중요한 건 그 위 로직이다.

발표 포인트:

- 수식 엔진은 검증된 라이브러리를 사용
- 하지만 state model, gating, association, lifecycle, control trigger는 직접 설계

### 6.2 Track lifecycle 상태머신
지금은 `hits`, `misses`만 있다.

발전 방향:

- `tentative`
- `confirmed`
- `deleted`

상태를 나눈다.

의미:

- 처음 잡힌 객체는 tentative
- 몇 프레임 유지되면 confirmed
- miss가 길어지면 deleted

이건 발표에서 아주 좋은 포인트다.

### 6.3 Association 개선
지금은 greedy association이다.

발전 방향:

- cost matrix 구성
- gated matching
- Hungarian 비교
- Mahalanobis gate 비교

여기서 중요한 건 "무조건 Hungarian 구현"이 아니다.
비교 실험을 해서 `왜 현재 방식 또는 개선 방식이 더 적합한지` 보여주는 것이다.

### 6.4 Adaptive noise model
지금 `Q`, `R`은 거의 고정값이다.

발전 방향:

- cluster confidence가 낮으면 `R` 증가
- cluster size가 크고 안정적이면 `R` 감소
- 속도 변화가 큰 구간은 `Q` 증가

이런 식으로 tracker를 데이터 품질에 반응하게 만들 수 있다.

### 6.5 Reacquire / hold 정책
컨베이어벨트 제어까지 생각하면 아주 중요하다.

예:

- 1~2프레임 놓쳐도 바로 삭제하지 않음
- ROI 안에서 다시 나타나면 같은 객체 후보로 관리
- 제어 이벤트는 `confirmed track`가 `N`프레임 안정적일 때만 발생

이건 단순 추적을 넘어서 `실제 제어 시스템 로직`에 가깝다.

### 6.6 Tracking 파트 발표용 목표
최소한 아래까지 가면 충분히 강하게 말할 수 있다.

- tentative / confirmed 상태머신 추가
- gate/association 튜닝
- adaptive `R` 또는 `Q` 일부 적용
- continuity / ID switch 지표 정리

## 7. 발표에서 가장 강한 포인트는 "제어 연결 로직"이다
DBSCAN과 Kalman이 라이브러리 기반이어도, 마지막 제어 정책은 거의 항상 우리 설계다.

예:

- track가 ROI A에 진입
- 속도 범위가 조건 만족
- `confirmed` 상태가 3프레임 이상 유지
- 그때 conveyor stop / pass / sort 이벤트 발생

이 부분은 라이브러리가 대신 안 해준다.

즉 최종 발표에서는 이렇게 구조화하면 좋다.

1. 센서 입력 안정화는 TLV parser가 담당
2. point를 객체 후보로 바꾸는 것은 tuned DBSCAN이 담당
3. 객체 continuity는 tuned tracker가 담당
4. 실제 공장 이벤트 판단은 우리가 설계한 control logic이 담당

## 8. 4주 실행 계획

### Week 1. Baseline 고정
- 현재 DBSCAN / tracker를 baseline으로 확정
- baseline 수치 측정
  - `avg_fps`
  - cluster count
  - track count
  - ID switch
  - continuity

산출물:

- `baseline_dbscan_tracker_metrics.csv`
- baseline 시연 영상 또는 로그

### Week 2. DBSCAN 차별화
- velocity scaling 추가
- adaptive `eps` 또는 zone preset 추가
- cluster reject rule 추가

산출물:

- `dbscan_param_sweep.csv`
- baseline vs tuned cluster 결과 비교표

### Week 3. Tracker 차별화
- tentative / confirmed state 추가
- association/gate 튜닝
- adaptive `R` 검토

산출물:

- `tracker_metrics.csv`
- baseline vs tuned tracker 비교표

### Week 4. 제어/발표 정리
- stable track 기반 제어 이벤트 설계
- 데모 시나리오 완성
- 발표용 "우리가 바꾼 점" 슬라이드 정리

산출물:

- control event log
- 발표 비교 슬라이드

## 9. 파트별로 지금 당장 손대면 좋은 코드 위치

### DBSCAN
수정 시작점:
[dbscan_cluster.py](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/cluster/dbscan_cluster.py)

우선순위:

1. velocity scaling 계수 추가
2. cluster confidence 재설계
3. adaptive `eps` 실험 구조 추가

### Tracker
수정 시작점:
[kalman_tracker.py](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/tracking/kalman_tracker.py)

우선순위:

1. track 상태머신 추가
2. gate/association metric 로깅 추가
3. adaptive noise model 실험

## 10. 발표 슬라이드에서 쓸 수 있는 구조

### 슬라이드 1. Baseline
- sklearn DBSCAN
- FilterPy Kalman
- 기본 실시간 파이프라인 연결 완료

### 슬라이드 2. 문제점
- 고정 `eps`에서 과분할/병합 발생
- greedy association에서 ID switch 발생
- 제어용으로는 track 안정성 부족

### 슬라이드 3. 우리가 한 개선
- velocity scaling + adaptive `eps`
- cluster confidence / reject rule 추가
- tentative-confirmed lifecycle
- tuned gate / adaptive noise
- stable track 기반 control trigger

### 슬라이드 4. 결과
- cluster 품질 개선
- ID switch 감소
- continuity 향상
- 제어 이벤트 안정화

## 11. 한 줄 결론
발표에서 중요한 건 `라이브러리를 썼는가`가 아니라,

`라이브러리를 baseline으로 두고, 실제 레이더 문제에 맞게 무엇을 직접 설계하고 수치로 증명했는가`

다.

즉 너희 팀은 이렇게 가져가면 된다.

- DBSCAN core는 라이브러리 사용
- Kalman 수식 엔진도 라이브러리 사용
- 하지만 feature engineering, adaptive tuning, association, lifecycle, control logic, KPI 검증은 직접 설계

이 수준까지 가면 발표와 면접에서 충분히 강하게 말할 수 있다.
