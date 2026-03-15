# Kalman Filter Guide

## 1. 이 문서는 누구를 위한 문서인가
이 문서는 `Kalman Filter 기반 객체 추적`을 처음 맡은 팀원을 위한 문서다.

대상 독자:

- 대학생 2학년 수준에서 tracking을 처음 구현하는 사람
- detection은 이해했지만 "프레임 사이 연결"이 왜 필요한지 아직 헷갈리는 사람
- Kalman Filter를 수학보다 시스템 관점에서 이해하고 싶은 사람

## 2. Kalman Filter가 뭐냐
쉽게 말하면 Kalman Filter는 `이전 상태와 현재 측정을 섞어서 더 그럴듯한 현재 위치를 추정하는 방법`이다.

레이더는 프레임마다 점이나 cluster를 준다.
그런데 센서 데이터는 흔들리고, 어떤 프레임에서는 객체가 잠깐 안 보일 수도 있다.

Kalman Filter는 이런 상황에서

- 지금 어디쯤 있을지 예측하고
- 새 측정이 오면 그걸 반영해서 수정하고
- 잠깐 측정이 없어도 track을 이어가게 해준다

즉 tracker의 핵심은 `예측 + 보정`이다.

## 3. 왜 Kalman tracking이 중요한가
DBSCAN이 "한 프레임 안에서 객체를 만드는 단계"라면, Kalman tracking은 "여러 프레임 사이에서 같은 객체를 이어주는 단계"다.

이 프로젝트 흐름은 아래와 같다.

`TLV Parsing -> Point Filtering -> DBSCAN -> Kalman Tracking -> Control`

여기서 tracking이 흔들리면 아래 문제가 생긴다.

- 사람 1명이 움직이는데 track id가 계속 바뀜
- 객체가 잠깐 안 보이면 track이 바로 끊김
- 2객체가 가까워질 때 ID가 섞임
- 제어 이벤트가 불안정해짐

현업 관점에서는 tracking을 단순 smoothing으로 보지 않는다.
`객체의 시간적 연속성을 보장하는 상태추정 계층`으로 본다.

## 4. 현재 코드 구조를 먼저 이해하자
현재 Kalman tracker 핵심 파일은 아래다.

- `src/tracking/kalman_tracker.py`

주요 구성은 아래와 같다.

- `TrackOutput`: 최종 출력 구조
- `_Track`: 내부 track 상태 저장용 객체
- `MultiObjectKalmanTracker`: 다중 객체 tracker 본체

즉 현재 구조는 `cluster measurement를 입력으로 받아 multi-track output을 만드는 클래스`다.

## 5. 데이터가 실제로 흐르는 순서

### 5.1 Step 1. DBSCAN이 cluster measurement를 만든다
tracker는 point를 직접 받지 않고 cluster centroid를 받는다.

입력 예시는 아래와 같다.

```python
{
    "x": 1.3,
    "y": 0.6,
    "z": 0.1,
    "v": -0.2,
    "size": 7,
    "confidence": 0.9,
}
```

### 5.2 Step 2. tracker가 다음 위치를 먼저 예측한다
Kalman Filter는 새 측정이 오기 전에 먼저 "이전 속도대로 가면 지금쯤 어디 있겠지"를 예측한다.

이걸 `predict` 단계라고 부른다.

### 5.3 Step 3. 새 measurement와 기존 track을 연결한다
이게 `association`이다.

즉 "이번 프레임의 cluster가 기존 몇 번 track이랑 같은 객체인지"를 정하는 단계다.

현재 코드는 거리 기반 gate와 greedy matching을 사용한다.

### 5.4 Step 4. 연결된 track은 update한다
같은 객체라고 판단되면 새 측정값으로 track 상태를 보정한다.

이걸 `update` 단계라고 부른다.

### 5.5 Step 5. 연결 안 된 measurement는 새 track으로 만든다
기존 track과 연결되지 않은 measurement는 새 객체라고 보고 track을 생성한다.

### 5.6 Step 6. 오래 못 본 track은 삭제한다
몇 프레임 동안 measurement가 안 붙는 track은 삭제한다.

즉 tracker의 핵심은 아래 4개다.

- predict
- associate
- update
- create/delete

## 6. 코드 레벨에서 꼭 이해해야 할 부분

### 6.1 상태벡터(state)
현재 코드는 2D constant velocity 모델을 쓴다.

즉 상태는 대략 아래 의미다.

- `x`
- `y`
- `vx`
- `vy`

쉽게 말하면 "위치 2개 + 속도 2개"다.

### 6.2 측정벡터(measurement)
현재 measurement는 아래 2개다.

- `x`
- `y`

즉 DBSCAN이 준 centroid 위치만 직접 update에 사용한다.

### 6.3 `F`, `H`, `P`, `Q`, `R`
처음 보면 수학처럼 보여도 의미만 알면 된다.

- `F`: 시간이 지나면 상태가 어떻게 변하는지
- `H`: 상태 중에서 어떤 값을 실제로 측정하는지
- `P`: 현재 추정이 얼마나 불확실한지
- `Q`: 시스템 자체의 흔들림 정도
- `R`: 측정값의 잡음 정도

면접에서는 수식보다 이 의미를 설명할 수 있는 게 더 중요하다.

### 6.4 association gate
기존 track 위치와 새 measurement 위치가 너무 멀면 같은 객체로 보지 않는 장치다.

쉽게 말해:

- gate가 너무 작으면 같은 사람도 못 이어붙인다
- gate가 너무 크면 다른 사람과 잘못 연결된다

### 6.5 `max_misses`, `min_hits`
이 두 파라미터는 실제 현업에서도 매우 중요하다.

- `max_misses`: 몇 번 안 보여도 track을 살려둘 것인가
- `min_hits`: 몇 번 확인돼야 track으로 인정할 것인가

즉 노이즈와 추적 연속성 사이 균형을 잡는 장치다.

## 7. 현업 관점에서 tracking에 요구되는 성능

### 7.1 기능 요구사항
- 객체별 track id를 유지할 것
- 잠깐 measurement가 사라져도 continuity를 유지할 것
- 새 객체와 사라진 객체를 구분할 것

### 7.2 성능 요구사항
- tracker 평균 처리시간 `<= 5ms/frame`
- 전체 시스템 FPS `>= 15`
- 단일 객체 60초 시나리오에서 ID switch `<= 1`
- 0.5초 이하 일시 누락 시 동일 track 유지율 `>= 80%`

### 7.3 품질 요구사항
- ID switch를 측정 가능해야 함
- fragmentation을 기록 가능해야 함
- false track 생성 사례를 설명 가능해야 함

## 8. 지금 코드가 하는 것과 아직 부족한 것

### 8.1 현재 코드가 이미 잘 하고 있는 것
- Kalman 기반 multi-object 구조가 있다
- predict/update 루프가 있다
- 거리 기반 association gate가 있다
- track 생성/유지/삭제 정책이 있다
- `min_hits`, `max_misses` 조정이 가능하다

즉, `tracking baseline`은 이미 있다.

### 8.2 아직 완전하다고 보기 어려운 이유
결론부터 말하면 `현재 tracker는 MVP용 baseline`이다.

이유는 아래와 같다.

#### 1. association이 greedy 방식이다
- 지금은 가장 가까운 쌍부터 순서대로 붙인다
- 복잡한 다중 객체 상황에서는 최적이 아닐 수 있다

#### 2. gating이 단순 Euclidean distance다
- covariance를 반영한 Mahalanobis gate가 아니다
- track 불확실도 차이를 반영하지 못한다

#### 3. confidence가 단순하다
- measurement confidence를 최대값으로 유지하는 정도다
- 진짜 추적 신뢰도를 정교하게 표현하지 못한다

#### 4. tracker 품질 지표가 자동화돼 있지 않다
- ID switch count
- fragmentation
- reacquisition time
- false track count

같은 값이 자동 계산되지 않는다.

#### 5. 테스트가 없다
- 단일 객체/2객체 fixture가 없다
- association corner case 테스트가 없다

## 9. 지금 코드에서 실제로 주의해야 할 점
현재 구현 기준으로 꼭 알아야 할 제한사항은 아래와 같다.

### 9.1 association이 복잡한 상황에 약할 수 있다
지금은 거리순으로 greedy matching을 한다.

그래서

- 2객체가 교차하거나
- 서로 가까워지거나
- measurement가 순간적으로 흔들리면

ID switch가 늘 수 있다.

### 9.2 process noise가 고정형이다
현재는 초기 `Q` 구성이 단순하고, 상황별 자동 튜닝 구조가 없다.

즉:

- 빠르게 움직이는 객체
- 거의 정지한 객체

를 같은 방식으로 보는 한계가 있다.

### 9.3 속도 측정치를 직접 쓰지 않는다
DBSCAN output에는 `v`가 있지만 현재 update는 `x`, `y` 위치만 직접 사용한다.

즉 tracking이 단순하고 안정적이라는 장점은 있지만, 더 풍부한 센서 정보를 아직 다 쓰고 있지는 않다.

### 9.4 다중 객체 metric이 아직 없다
코드가 동작하는 것과 "품질이 좋은 것"은 다르다.
현재는 track id continuity를 자동으로 채점하는 도구가 없다.

## 10. Kalman 담당자가 지금부터 공부할 순서

### 10.1 1단계: 한 객체 tracking 개념 이해
먼저 아래 개념만 확실히 잡으면 된다.

- state
- measurement
- predict
- update
- noise

이 단계 목표:
`"왜 측정값 그대로 쓰지 않고 예측을 섞는지"` 설명할 수 있어야 한다.

### 10.2 2단계: 현재 코드 따라가기
아래 순서로 보면 된다.

1. `_build_kf`
2. `_predict`
3. `_associate`
4. `update`
5. `TrackOutput`

이 단계 목표:
`"measurement가 어떻게 track으로 바뀌는지"` 말할 수 있어야 한다.

### 10.3 3단계: 단일 객체부터 보기
처음부터 다중 객체를 보면 헷갈린다.

먼저 확인할 것:

- 한 객체가 직선 이동할 때 위치가 부드러워지는지
- 잠깐 안 보여도 같은 track이 유지되는지
- `max_misses`, `min_hits`가 어떤 영향을 주는지

### 10.4 4단계: association 공부
tracking에서 제일 어렵고 중요한 건 사실 Kalman 자체보다 association이다.

꼭 봐야 하는 상황:

- 2객체가 가까워질 때
- 2객체가 교차할 때
- 한 객체가 잠깐 사라질 때
- 새 객체가 갑자기 들어올 때

### 10.5 5단계: 수치화
Kalman 담당자는 "부드러워 보인다"가 아니라 숫자로 말해야 한다.

최소한 아래는 남겨야 한다.

- ID switch count
- fragmentation count
- continuity ratio
- false track count
- tracker latency

## 11. Kalman 담당자의 개발 우선순위

### Priority 1. 단일 객체 continuity 확보
- 한 사람 track id가 쉽게 바뀌지 않게 하기
- 잠깐 measurement가 사라져도 유지되게 하기

### Priority 2. gate와 life-cycle 튜닝
- `association_gate`
- `max_misses`
- `min_hits`

를 시나리오별로 맞추기

### Priority 3. metric 수집
- ID switch
- miss
- fragmentation
- false track

자동 집계 구조 만들기

### Priority 4. association 개선 검토
- greedy와 Hungarian 비교
- Euclidean gate와 Mahalanobis gate 비교

### Priority 5. 모델 개선
- velocity 활용
- noise model 개선
- confidence 설계 보완

## 12. Kalman 담당자가 만들어야 할 증거 자료

### 필수
- `evidence/tracker_metrics.csv`
- track id timeline 그래프
- 단일 객체 continuity 결과
- 2객체 시나리오 결과 영상

### 있으면 강한 것
- ID switch 비교표
- gate 크기별 성능 그래프
- `max_misses`, `min_hits` sweep 결과
- 교차 시나리오 실패 사례 정리

## 13. 네가 면접에서 설명할 수 있어야 하는 말

1. `Kalman tracker는 noisy measurement를 시간축으로 연결해 객체 상태를 추정하는 계층이다.`
2. `핵심은 Kalman 수식 자체보다 data association과 track management다.`
3. `나는 gate, max_misses, min_hits, process/measurement noise를 조정해 continuity를 개선했다.`
4. `tracking 품질은 ID switch와 fragmentation 같은 지표로 검증해야 한다.`

## 14. 지금 당장 추천하는 확인 항목

### 개발 중 확인할 로그
- `track count`
- `track_id`
- `hits`
- `misses`
- `age`
- `tracker latency`

### 꼭 확인할 질문
- 왜 같은 사람인데 track id가 바뀌는가
- 왜 없는 객체 track이 갑자기 생기는가
- 왜 객체가 잠깐 사라졌는데 바로 삭제되는가
- gate를 키웠을 때 왜 오히려 더 나빠지는가

## 15. 한 줄 결론
Kalman tracking은 "좌표를 부드럽게 만드는 필터"가 아니라, 실제로는 `객체를 시간축으로 이어붙이는 상태추정 모듈`이다.

현재 코드는 baseline으로는 충분히 쓸 수 있지만, `association 개선`, `metric 수집`, `noise tuning`, `다중 객체 검증`이 더 필요하다.

너는 지금부터 `단일 객체 안정화 -> metric 수집 -> 다중 객체 튜닝 -> association 개선` 순서로 발전시키면 된다.
