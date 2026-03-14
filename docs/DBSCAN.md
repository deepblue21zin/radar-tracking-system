# DBSCAN Guide

## 1. 이 문서는 누구를 위한 문서인가
이 문서는 `DBSCAN 기반 레이더 포인트 클러스터링`을 처음 맡은 팀원을 위한 문서다.

대상 독자:

- 대학생 2학년 수준에서 clustering을 처음 프로젝트에 적용하는 사람
- 점 데이터는 있는데 "객체 단위"로 어떻게 묶는지 감이 부족한 사람
- DBSCAN 파라미터를 왜 조정해야 하는지, 현업에서는 무엇을 중요하게 보는지 궁금한 사람

## 2. DBSCAN이 뭐냐
DBSCAN은 `Density-Based Spatial Clustering of Applications with Noise`의 약자다.

쉽게 말하면 "가까이 모여 있는 점들은 같은 그룹으로 보고, 너무 외롭게 떨어진 점은 noise로 버리는 방법"이다.

레이더에서는 한 사람이나 한 물체가 보통 여러 개의 point로 찍힌다.
그래서 DBSCAN의 목적은 `점(point)`을 `객체(object)`로 묶는 것이다.

예를 들어,

- 사람 1명 -> point 8개
- 사람 2명 -> point 6개
- 벽 반사나 잡음 -> 흩어진 point 몇 개

가 있으면 DBSCAN은 "사람 1", "사람 2", "noise"로 분리해주는 역할을 한다.

## 3. 왜 DBSCAN이 중요한가
레이더 포인트는 점 단위라서 그대로 tracker에 넣으면 흔들림이 심하고 계산량도 커진다.

이 프로젝트 흐름은 아래와 같다.

`TLV Parsing -> Point Filtering -> DBSCAN -> Kalman Tracking -> Control`

여기서 DBSCAN이 흔들리면 뒤 단계 문제가 바로 생긴다.

- 한 객체가 두 cluster로 나뉘면 track이 두 개 생길 수 있다.
- 두 객체가 하나로 합쳐지면 tracking이 꼬인다.
- noise를 잘 못 버리면 false track이 생긴다.

현업 관점에서는 DBSCAN을 단순 clustering 코드로 보지 않는다.
`추적기의 입력 품질을 결정하는 객체 생성 단계`로 본다.

## 4. 현재 코드 구조를 먼저 이해하자
현재 DBSCAN 핵심 파일은 아래다.

- `src/cluster/dbscan_cluster.py`

이 파일의 중심 함수는 하나다.

- `cluster_points(points, eps, min_samples, use_velocity_feature)`

즉 현재 구조는 단순하다.
`point list를 받아서 cluster list를 반환하는 순수 함수` 형태다.

## 5. 데이터가 실제로 흐르는 순서

### 5.1 Step 1. 파서/필터가 point list를 만든다
DBSCAN은 TLV 파서가 만든 point를 그대로 받지 않고, 전처리된 point list를 받는다.

각 point는 보통 아래 같은 형태다.

```python
{
    "x": 1.2,
    "y": 0.4,
    "z": 0.1,
    "v": -0.3,
    "range": 1.27,
    "snr": 15.0,
    "noise": 3.0,
}
```

### 5.2 Step 2. DBSCAN feature를 만든다
현재 코드는 두 가지 방식이 있다.

- 기본: `(x, y)`
- 옵션: `(x, y, v)`

즉 point마다 feature vector를 만든 뒤 clustering을 수행한다.

### 5.3 Step 3. label을 받는다
DBSCAN은 각 point에 label을 붙인다.

- `0, 1, 2, ...`: cluster 번호
- `-1`: noise

### 5.4 Step 4. 같은 label끼리 묶는다
같은 label을 받은 point들을 모아 하나의 객체 측정값으로 만든다.

현재 출력은 아래 정보를 가진다.

- `x, y, z`: cluster 중심
- `v`: 평균 속도
- `size`: cluster에 포함된 point 수
- `confidence`: 간단한 신뢰도
- `label`

즉 DBSCAN의 핵심 목적은 `point cloud -> object measurement` 변환이다.

## 6. 코드 레벨에서 꼭 이해해야 할 부분

### 6.1 `points` 입력
입력은 `Iterable[dict]` 형태다.

즉 numpy array만 받는 게 아니라, 파서/필터가 만든 point dict들을 유연하게 받는다.

### 6.2 `eps`
이건 "얼마나 가까우면 같은 무리로 볼 것인가"를 정하는 거리 기준이다.

쉽게 말해:

- 너무 작으면 한 사람도 여러 cluster로 쪼개진다.
- 너무 크면 두 사람도 하나로 합쳐진다.

### 6.3 `min_samples`
이건 "최소 몇 개 point가 모여야 cluster로 인정할 것인가"다.

쉽게 말해:

- 너무 작으면 noise도 cluster가 된다.
- 너무 크면 실제 객체도 사라진다.

### 6.4 `use_velocity_feature`
이 옵션이 켜지면 `(x, y)` 대신 `(x, y, v)`로 clustering한다.

장점:

- 위치가 비슷해도 속도가 다른 객체를 나누는 데 도움이 될 수 있다

주의:

- 위치 단위(m)와 속도 단위(m/s)를 그냥 같이 쓰면 scale mismatch가 생길 수 있다

즉 이 옵션은 무조건 좋지 않고, `정규화`를 같이 생각해야 한다.

### 6.5 cluster summary 생성
현재 코드는 cluster 안 point들의 평균으로 centroid와 평균 속도를 만든다.

이건 구현이 단순해서 빠르다.
대신 bounding box나 covariance 같은 더 풍부한 정보는 아직 없다.

## 7. 현업 관점에서 DBSCAN에 요구되는 성능

### 7.1 기능 요구사항
- point cloud를 object cluster로 변환할 것
- noise point를 분리할 것
- tracker가 쓸 수 있는 centroid를 안정적으로 제공할 것

### 7.2 성능 요구사항
- clustering 평균 처리시간 `<= 15ms/frame`
- 전체 시스템 FPS `>= 15`
- 단일 객체 시나리오에서 `1 cluster 유지율 >= 90%`
- 2객체 분리 시나리오에서 `2 cluster 분리 성공률 >= 85%`

### 7.3 품질 요구사항
- noise 비율을 설명 가능해야 함
- false cluster 발생 사례를 기록해야 함
- 파라미터 변경 전후 결과를 비교 가능해야 함

## 8. 지금 코드가 하는 것과 아직 부족한 것

### 8.1 현재 코드가 이미 잘 하고 있는 것
- 구조가 단순해서 이해하기 쉽다
- 입력/출력이 tracker 친화적이다
- `eps`, `min_samples`, `velocity feature`를 바로 바꿔볼 수 있다
- point count 기반 confidence라도 최소한의 품질 점수는 있다

즉, `실험용 baseline`으로는 충분히 쓸 만하다.

### 8.2 아직 완전하다고 보기 어려운 이유
결론부터 말하면 `현재 DBSCAN 코드는 MVP 수준의 baseline`이다.

이유는 아래와 같다.

#### 1. 파라미터가 고정형이다
- 거리별로 `eps`를 다르게 쓰지 않는다
- 환경별 preset이 없다

#### 2. velocity feature 정규화가 없다
- `(x, y, v)`를 그대로 넣는다
- 위치와 속도 단위가 섞여서 cluster 품질이 왜곡될 수 있다

#### 3. confidence가 단순하다
- 현재는 point 개수 기반 점수다
- SNR, spatial spread, noise ratio 같은 정보가 반영되지 않는다

#### 4. cluster 품질 지표가 없다
- 분리 성공률, false cluster count, noise ratio를 자동 계산하지 않는다

#### 5. 테스트와 fixture가 없다
- labeled sample point cloud가 없다
- parameter sweep 자동화가 없다

## 9. 지금 코드에서 실제로 주의해야 할 점
이번 문서는 설명용이지만, 현재 구현 기준으로 꼭 알아야 할 제한사항이 있다.

### 9.1 `use_velocity_feature=True`는 바로 쓰면 위험할 수 있다
현재는 `x`, `y`, `v`를 그대로 한 feature vector에 넣는다.

즉:

- 위치는 meter
- 속도는 meter/sec

단위가 다르다.

이걸 그대로 넣으면 velocity 값이 clustering에 과하게 작용하거나 거의 영향이 없을 수 있다.
그래서 이 옵션은 `정규화나 scaling 없이 무조건 켜는 기능`이 아니다.

### 9.2 cluster confidence가 너무 단순하다
현재 confidence는 사실상 `size / min_samples`다.

즉,

- point가 많으면 confidence가 높고
- 적으면 낮다

정도만 본다.

하지만 실제로는

- SNR이 높은지
- cluster가 너무 퍼져 있지는 않은지
- noise가 주변에 많은지

같은 정보도 중요하다.

### 9.3 거리별 특성이 반영되지 않는다
레이더는 가까운 거리와 먼 거리가 point density가 다를 수 있다.
그런데 현재는 모든 거리에서 같은 `eps`를 사용한다.

즉 near range와 far range를 같은 기준으로 처리하는 한계가 있다.

## 10. DBSCAN 담당자가 지금부터 공부할 순서

### 10.1 1단계: clustering 개념 이해
먼저 아래 개념을 이해하면 된다.

- density
- core point
- border point
- noise point
- `eps`
- `min_samples`

이 단계 목표:
`"왜 DBSCAN이 K-means보다 레이더 point cloud에 잘 맞을 수 있는지"` 설명할 수 있어야 한다.

### 10.2 2단계: 현재 코드 따라가기
아래 순서로 보면 된다.

1. 입력 point list 확인
2. feature matrix 생성
3. `DBSCAN.fit_predict()`
4. label별 point grouping
5. centroid/size/confidence 생성

이 단계 목표:
`"한 프레임의 point가 어떻게 cluster measurement로 바뀌는지"` 설명할 수 있어야 한다.

### 10.3 3단계: 시각화로 감 잡기
DBSCAN은 숫자만 보면 감이 늦게 온다.

꼭 해볼 것:

- raw point plot
- cluster color plot
- noise point 강조
- 파라미터 변경 전후 비교

이 단계 목표:
`"eps를 키우면 어떤 일이 생기는지"` 눈으로 이해하는 것

### 10.4 4단계: 시나리오별 튜닝
아래 시나리오를 분리해서 보라.

- 단일 객체
- 2객체 분리 이동
- 2객체 교차 이동
- 저 SNR 환경
- 먼 거리 객체

이 단계 목표:
`"좋은 파라미터는 하나가 아니라 시나리오별로 달라질 수 있다"`는 걸 아는 것

### 10.5 5단계: 수치화
DBSCAN 담당자는 "그냥 잘 묶였다"가 아니라 숫자로 말할 수 있어야 한다.

최소한 아래는 남겨야 한다.

- single-object 1 cluster ratio
- two-object separation success rate
- noise ratio
- false cluster count
- clustering latency

## 11. DBSCAN 담당자의 개발 우선순위

### Priority 1. baseline 안정화
- 단일 객체에서 cluster 1개가 잘 유지되는지 확인
- noise label이 너무 많거나 적지 않은지 확인

### Priority 2. 파라미터 튜닝
- `eps`, `min_samples` sweep
- 거리/환경별 추천값 정리

### Priority 3. velocity feature 개선
- scale 정규화 적용 검토
- 켰을 때와 껐을 때 성능 비교

### Priority 4. confidence 개선
- SNR, spread, point count를 반영한 점수 검토

### Priority 5. 테스트 자동화
- 시나리오별 비교표 자동 생성
- parameter sweep 결과 CSV 저장

## 12. DBSCAN 담당자가 만들어야 할 증거 자료

### 필수
- `evidence/dbscan_param_sweep.csv`
- raw vs clustered 시각화 이미지
- 단일 객체/2객체 시나리오 비교표
- clustering latency 기록

### 있으면 강한 것
- noise ratio 추이 그래프
- velocity feature on/off 비교표
- 거리대별 eps 실험 결과
- false cluster 사례 정리 문서

## 13. 네가 면접에서 설명할 수 있어야 하는 말

1. `DBSCAN은 radar point cloud를 object measurement로 바꾸는 단계다.`
2. `핵심은 clustering 자체보다 tracker 입력을 안정화하는 것이다.`
3. `나는 eps, min_samples, velocity feature, noise 비율을 기준으로 성능을 튜닝했다.`
4. `좋은 clustering은 false track를 줄이고 track continuity를 높인다.`

## 14. 지금 당장 추천하는 확인 항목

### 개발 중 확인할 로그
- `raw point count`
- `filtered point count`
- `cluster count`
- `noise count`
- `avg cluster size`
- `clustering latency`

### 꼭 확인할 질문
- 한 사람인데 왜 cluster가 2개로 나뉘는가
- 두 사람인데 왜 1개로 합쳐지는가
- noise가 왜 cluster로 승격되는가
- velocity feature가 실제로 도움이 되는가

## 15. 한 줄 결론
DBSCAN은 "점들을 묶는 함수"처럼 보여도, 실제로는 `추적기의 입력 품질을 결정하는 객체 생성 모듈`이다.

현재 코드는 baseline으로는 충분히 좋지만, `파라미터 튜닝`, `velocity scaling`, `confidence 개선`, `성능 지표화`가 더 필요하다.

너는 지금부터 `시각화 -> 파라미터 튜닝 -> 수치화 -> confidence 개선` 순서로 발전시키면 된다.
