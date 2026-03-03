# Capstone Pipeline Implementation Spec

## 1. 문서 목적
본 문서는 캡스톤 발표/보고에서 "무엇을 구현했고 왜 성능이 좋아졌는지"를 근거 있게 설명하기 위한 명세서다.

기준 시점: 2026-03-03

## 2. 내가 실제로 수행한 구조 변경

### 2.1 End-to-End 파이프라인 연결
기존 parser-only 루프를 다음 구조로 확장했다.

`TLV Parse -> Point Preprocess -> DBSCAN Cluster -> Kalman Multi-Track -> Runtime Metrics`

반영 파일:
- `src/parser/tlv_parse_runner.py`
- `src/filter/noise_filter.py`
- `src/cluster/dbscan_cluster.py` (신규)
- `src/tracking/kalman_tracker.py` (신규)

### 2.2 전처리(Preprocess) 확장
추가/개선 항목:
- parser의 dict-of-arrays를 list-of-points로 변환
- SNR threshold 필터
- noise 상한 필터
- 거리 gate(min/max range)
- (확장 가능) z 축 gate

효과:
- DBSCAN 입력 잡음 감소
- 잘못된 클러스터 병합/분할 감소
- tracker update 안정성 향상

### 2.3 DBSCAN 클러스터링 실데이터화
`plot_dbscan.py` 데모(합성데이터) 대신 실시간 포인트클라우드에 DBSCAN을 적용하도록 모듈화했다.

출력 계약(클러스터 측정값):
- `x, y, z`: centroid
- `v`: 평균 속도
- `size`: 포인트 수
- `confidence`: 간단한 신뢰도

효과:
- 점 단위 입력을 객체 단위 측정으로 축약
- tracker 연산량 감소

### 2.4 칼만 기반 다중 트랙 관리 추가
`filterpy`를 활용한 2D CV(Constant Velocity) tracker를 추가했다.

추가 로직:
- predict/update 루프
- 거리 기반 게이팅 + greedy association
- track 생성/유지/삭제 정책
- `min_hits`, `max_misses` 파라미터화

효과:
- 프레임 간 위치 흔들림 완화
- 단발성 누락에도 트랙 연속성 유지

### 2.5 성능 로그 출력 추가
runner에서 1초 윈도우 FPS를 출력하도록 추가했다.

출력 예:
- `frame=... raw=... filtered=... clusters=... tracks=...`
- `[PERF] fps=...`

효과:
- 실험 중 즉시 성능 확인 가능
- 파라미터 튜닝 피드백 루프 단축

## 3. 성능을 더 높이기 위해 수정/추가해야 할 항목

### 3.1 코드 레벨 (즉시 권장)
1. 전처리 고도화
- static clutter map(정적 히트맵) 도입
- range-dependent threshold(거리별 SNR 임계값)

2. DBSCAN 최적화
- 가까운 거리/먼 거리별 `eps` 분리
- `use_velocity_feature` 활성화 시 scale 정규화

3. Tracker 고도화
- Hungarian assignment 도입(현재 greedy)
- gating 시 Mahalanobis distance 적용
- `Q/R` auto-tuning (주행/실내 시나리오별)

4. 런타임 최적화
- numpy 배열 재사용
- 로그 레벨 분리(실험/배포)

### 3.2 문서/실험 레벨 (발표용 핵심)
1. 실험 매트릭 정의
- FPS(avg, P95)
- latency(avg, P95)
- ID switch 수
- track fragmentation 수
- miss ratio

2. 시나리오별 실험표
- 단일 객체 직선 이동
- 2객체 교차 이동
- 저 SNR 환경
- 원거리 객체

3. 파라미터 테이블
- `snr_threshold`, `dbscan_eps`, `dbscan_min_samples`, `association_gate`, `max_misses`, `min_hits`
- 각 파라미터 변화에 따른 KPI 변동 기록

## 4. 캡스톤 보고서에 그대로 넣을 수 있는 구현 명세

### 4.1 구현 목표
- 실시간 mmWave 포인트클라우드에서 객체 단위 트랙을 안정적으로 추정
- 평균 10 FPS 이상 유지

### 4.2 구현 범위
- 입력: IWR6843 UART TLV 프레임
- 처리: 전처리 + DBSCAN + Kalman multi-target tracking
- 출력: track id/위치/속도/신뢰도 + 실시간 FPS

### 4.3 검증 방법
1. 60초 연속 실행
2. 매 프레임 처리 로그 수집
3. 평균 FPS와 추적 안정성 지표 산출
4. 기준 미달 시 파라미터 재튜닝

### 4.4 수용 기준 (Acceptance Criteria)
- 성능: 평균 FPS >= 10
- 안정성: 30분 연속 실행 시 크래시 0
- 추적 품질: 단일 객체 시 ID switch 0
- 기능성: track 생성/유지/삭제 정상 동작

## 5. 실행 예시

```bash
python src/parser/tlv_parse_runner.py \
  --cli-port COM6 \
  --data-port COM5 \
  --config path/to/profile.cfg \
  --snr-threshold 8 \
  --dbscan-eps 0.6 \
  --dbscan-min-samples 4 \
  --association-gate 1.5 \
  --max-misses 8 \
  --min-hits 2
```

## 6. 리스크 및 대응
- 리스크: `numpy/scikit-learn/filterpy` 미설치 시 일부 단계 비활성화
- 대응: 의존성 설치 가이드 제공 + 모듈 비활성 경고 로그 유지

- 리스크: 장면 복잡도 증가 시 DBSCAN 분할 오류
- 대응: 시나리오별 파라미터 프리셋 문서화

## 7. 결론
이번 수정으로 parser-only 구조에서 실제 추적 파이프라인 구조로 전환되었다.
캡스톤 관점에서 "실시간 처리 + 추적 동작 + 성능 지표"를 제시할 수 있는 최소 완성선을 확보했다.
