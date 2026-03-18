# DBSCAN / Filter Tuning and Tracking Result Study

## 1. 문서 목적

이 문서는 2026-03-18 기준으로 진행한 아래 작업을 한 번에 정리하기 위한 study note이다.

- `DBSCAN` 클러스터링을 거리 구간별 adaptive 방식으로 보완한 내용
- `filter` 파라미터를 조정하면서 로그가 어떻게 달라졌는지
- 객체 추정 결과가 어느 정도까지 안정화되었는지
- 사람이 레이더 정면에서 앞뒤로 왕복할 때 거리 추적이 실제로 어떻게 보였는지

핵심 질문은 다음과 같다.

1. 어떤 파라미터를 바꿨는가
2. 그 파라미터가 어디에 작용하는가
3. 로그 지표가 어떻게 변했는가
4. 현재 상태를 "객체 추정이 꽤 된다"고 볼 수 있는가

---

## 2. 이번 변경의 핵심

### 2.1 `src/cluster/dbscan_cluster.py`

기존 고정 `eps` DBSCAN에 거리 구간별 adaptive `eps`를 적용했다.

현재 기본 구조:

- `0.0 ~ 1.4m -> eps = 0.22`
- `1.4m 이상 -> eps = 0.45`
- `min_samples = 3`

추가 보완:

- adaptive band 경계에서 같은 물체가 둘로 쪼개지는 현상을 줄이기 위한 boundary merge
- adaptive band 바깥 점이 fallback으로 처리될 때 경고 가능 구조
- 기존 출력 필드 유지
  - `x`, `y`, `z`, `v`, `size`, `confidence`, `label`
- 추가 출력 필드
  - `range_band`, `eps_used`, `min_samples_used`, `boundary_merged`

### 2.2 `config/runtime_params.json`, `src/runtime_params.py`

공용 런타임 파라미터 기본값을 아래 방향으로 조정했다.

- `snr_threshold`
- `dbscan_min_samples`
- `dbscan_adaptive_eps_bands`
- `right_rail_padding`

최종적으로 현재 기준값으로 남긴 값:

```json
{
  "snr_threshold": 110.0,
  "max_range": 3.0,
  "dbscan_min_samples": 3,
  "dbscan_adaptive_eps_bands": [
    { "r_min": 0.0, "r_max": 1.4, "eps": 0.22 },
    { "r_min": 1.4, "r_max": null, "eps": 0.45 }
  ],
  "right_rail_padding": 0.05,
  "disable_near_front_keepout": false
}
```

### 2.3 `src/parser/runtime_pipeline.py`

기존 로그는 프레임 전체의 `filtered_range_min`, `filtered_range_max`만 남겼다.
이 방식은 "그 프레임에 남은 모든 점 중 최소/최대 거리"이므로, 사람 1명의 접근/이탈을 보기에는 한계가 있었다.

그래서 다음 컬럼을 새로 추가했다.

- `primary_cluster_label`
- `primary_cluster_range_m`
- `primary_cluster_size`
- `primary_cluster_confidence`
- `primary_track_id`
- `primary_track_range_m`
- `primary_track_confidence`

선정 기준:

- `primary_cluster`: 가장 가까운 cluster
- `primary_track`: 가장 가까운 track

텍스트 로그에도 다음과 같은 요약을 추가했다.

```text
primary_cluster={label=0, range=0.98m, size=11} primary_track={id=1, range=0.94m, hits=2}
```

---

## 3. 파라미터별 의미와 작용 방식

### 3.1 `snr_threshold`

역할:

- `noise_filter.preprocess_points()`에서 low-SNR point를 제거한다.

영향:

- 값을 낮추면 점이 많이 살아남는다.
- 값을 높이면 노이즈를 더 세게 제거하지만, 유효한 점도 같이 죽을 수 있다.

이번 실험 결론:

- `120`은 너무 강했다.
- `115`도 직전 최적점보다 과했다.
- `110`이 현재 로그 기준 가장 균형이 좋았다.

### 3.2 `dbscan_adaptive_eps_bands`

역할:

- 거리대별로 다른 `eps`를 적용한다.

의도:

- 가까운 거리에서는 `eps`를 너무 크게 쓰지 않아 과도한 병합을 줄임
- 먼 거리에서는 더 큰 `eps`로 성긴 점도 객체로 묶이게 함

현재 적용:

- near band `0.22`
- far band `0.45`

이번 실험 결론:

- far band `0.45`는 현재 정면 접근 실험에서 꽤 잘 작동했다.
- 현재 문제는 DBSCAN 자체보다는 filter 쪽 민감도가 더 큰 영향을 주는 경우가 많았다.

### 3.3 `dbscan_min_samples`

역할:

- cluster로 인정할 최소 point 수

영향:

- 너무 크면 점이 적은 프레임에서 cluster를 놓친다.
- 너무 작으면 노이즈 점도 cluster가 될 수 있다.

현재 값:

- `3`

판단:

- 현재 환경에서는 `4`보다 `3`이 안정적이었다.

### 3.4 `right_rail_padding`

역할:

- 우측 레일 keepout 박스의 여유 폭

영향:

- 값이 크면 레일 주변 점을 더 넓게 지운다.
- 값이 작아지면 레일 근처의 유효한 점이 더 살아남는다.

이번 실험 결론:

- `0.15`에서는 keepout 제거량이 과했다.
- `0.05`로 줄인 뒤 `filtered_points`, `clusters`, `tracks`가 눈에 띄게 회복됐다.

### 3.5 `disable_near_front_keepout`

역할:

- 레이더 바로 앞 박스를 keepout으로 쓸지 여부

이번 실험 결론:

- `near_front`를 꺼도 좋아지지 않았다.
- 오히려 `no_near_front_keepout` 실험에서는 전체 성능이 더 나빠졌다.
- 따라서 현재 문제의 주원인은 `near_front keepout`이 아니었다.

---

## 4. 실험 로그 비교

### 4.1 주요 실험 ID

- `20260318_213244`
- `20260318_215412`
- `20260318_221238`
- `20260318_222225`
- `20260318_223049`
- `20260318_225536`

### 4.2 실험별 변화 요약

| run_id | 설정 특징 | avg_filtered_points | avg_clusters | avg_tracks | 해석 |
| --- | --- | ---: | ---: | ---: | --- |
| `20260318_213244` | 점이 너무 많이 살아남던 상태 | 30.013 | 3.488 | 3.430 | 사람 1명을 3개 이상으로 자주 쪼갬 |
| `20260318_215412` | `snr_threshold=120`, adaptive 강화 | 11.753 | 2.131 | 2.077 | cluster 수는 줄었지만 과필터링 시작 |
| `20260318_221238` | `--disable-near-front-keepout` | 5.365 | 0.674 | 0.607 | 가장 나쁨, near-front가 원인 아님 확인 |
| `20260318_222225` | `snr_threshold=110`, `right_rail_padding=0.05` | 13.435 | 1.820 | 1.737 | 가장 균형 좋음 |
| `20260318_223049` | `snr_threshold=115` | 9.113 | 1.064 | 0.968 | 다시 과필터링 방향 |
| `20260318_225536` | `110` 유지 + primary target logging | 8.412 | 1.255 | 1.207 | 거리 추적 해석용 로그 확보 |

### 4.3 해석

실험 결과는 다음처럼 정리할 수 있다.

- 초기 상태는 `filtered_points`가 너무 많아 객체가 잘게 쪼개졌다.
- `120`은 cluster 수를 줄이긴 했지만 유효한 점까지 많이 죽였다.
- `near_front keepout`을 끈 실험은 실패였다.
- `110 + right_rail_padding=0.05` 조합이 가장 안정적이었다.
- `115`는 다시 다소 과한 값이었다.

즉 현재 기준 최적점은 다음과 같다.

- `snr_threshold = 110`
- `dbscan_min_samples = 3`
- near/far adaptive `eps = 0.22 / 0.45`
- `right_rail_padding = 0.05`
- `near_front keepout = on`

---

## 5. 객체 위치 추적 결과 정리

### 5.1 이전 방식의 한계

기존에는 아래 값으로만 거리 추세를 봤다.

- `filtered_range_min`
- `filtered_range_max`

하지만 이 값은 "프레임 전체 점 중 최소/최대 거리"라서, 사람 1명의 움직임과 배경/레일 반사가 섞이면 해석이 어렵다.

### 5.2 `primary_cluster_range_m`, `primary_track_range_m` 기준 결과

최신 로그 `20260318_225536` 기준:

- `primary_track_range_m`
  - 최소: `0.289 m`
  - 중앙값: `0.950 m`
  - 최대: `2.726 m`
- `primary_cluster_range_m`
  - 최소: `0.453 m`
  - 중앙값: `1.096 m`
  - 최대: `2.907 m`

이 값은 다음을 의미한다.

- 레이더 정면에서 매우 가까운 구간도 실제로 잡혔다.
- 약 3m 근처의 먼 구간도 실제로 잡혔다.
- 즉 거리 범위 자체는 꽤 잘 반영되었다.

### 5.3 "멀어졌다가 가까워졌다"가 잘 보였는가

이번 실험에서 사용자는 한 번만 접근/이탈한 것이 아니라, 레이더 정면에서 앞뒤로 반복 왕복했다.

그 기준으로 보면 `primary_track_range_m`은 꽤 그럴듯한 값을 보였다.

대표 예시:

- `11.85s -> 0.289m`
- `25.35s -> 2.726m`
- `30.45s -> 0.340m`
- `50.45s -> 2.710m`
- `54.85s -> 0.459m`
- `59.35s -> 2.701m`

해석:

- 거리 값이 엉망으로 무작위 점프한 것보다는
- 실제 반복 왕복 움직임을 꽤 잘 반영한 패턴으로 볼 수 있다.

다만 완전히 매끈한 단일 곡선은 아니다.

이유:

- `primary_track`은 "그 순간 가장 가까운 track"이다.
- track ID가 바뀌면 거리 곡선도 점프한다.
- 즉 "한 사람 한 track의 완전한 연속 궤적"이라기보다 "그 프레임에서 대표 대상의 거리"에 가깝다.

### 5.4 현재 수준에 대한 판단

현재 로그 기준으로는 다음처럼 평가할 수 있다.

- 거리 변화 감지: 꽤 잘 됨
- 객체 후보 생성: 실용적으로 쓸 만한 수준
- tracker 유지: 어느 정도 됨
- 완전히 안정적인 1인 1-track 고정: 아직 부족함

따라서 프로젝트 목적이

- 사람 접근 감지
- 위험 구간 진입 확인
- 컨베이어 감속 / 정지 트리거

라면, 현재 수준은 시연용/프로토타입용으로 충분히 의미가 있다.

---

## 6. 현재 결론

### 6.1 기술적 결론

현재 파이프라인은 아래 수준까지는 달성했다.

- `parser -> filter -> adaptive DBSCAN -> tracker` 흐름이 안정적으로 동작
- 정면 거리 변화가 로그에 반영됨
- 객체를 전혀 못 잡는 상태는 아님
- 과도한 분할도 초기 상태보다 줄었음

### 6.2 가장 적절한 기준값

현재 study 기준 추천 baseline:

- `snr_threshold = 110`
- `dbscan_min_samples = 3`
- `dbscan_adaptive_eps_bands = [(0.0~1.4, 0.22), (1.4~, 0.45)]`
- `right_rail_padding = 0.05`
- `near_front keepout = on`

### 6.3 아직 남은 한계

- 대표 대상이 프레임마다 바뀌면 거리 곡선이 점프할 수 있음
- 사람 1명을 항상 1 track으로 유지하지는 못함
- 접근/이탈 분석에는 충분하지만, 정밀 trajectory 분석에는 추가 보완이 필요함

---

## 7. 다음 단계 제안

### 7.1 우선순위 1

`primary_track` 대신 "가장 오래 유지된 track_id"를 기준으로 거리 곡선을 기록

효과:

- 한 사람의 연속 궤적처럼 보이는 로그 확보 가능

### 7.2 우선순위 2

single-person 실험용 mode 추가

예:

- 가장 큰 cluster 하나만 사용
- 또는 confidence / hits가 가장 높은 track 하나만 사용

효과:

- 시연/평가 실험에서 거리 곡선이 훨씬 해석하기 쉬워짐

### 7.3 우선순위 3

필요하면 viewer에도 primary target distance 표시 추가

효과:

- 로그를 열지 않고도 실시간으로 접근/이탈 정도를 확인 가능

---

## 8. 요약 문장

이번 튜닝 결과를 한 문장으로 요약하면 다음과 같다.

> 거리 구간별 adaptive DBSCAN과 filter 파라미터 재조정을 통해, 초기보다 과도한 객체 분할을 줄이고 사람의 반복적인 접근/이탈 거리를 로그상에서 유의미하게 추적할 수 있는 수준까지 안정화하였다.

