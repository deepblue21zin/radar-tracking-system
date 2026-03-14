# Capstone Team REQ and 3-Month Roadmap

## 1. 문서 목적
본 문서는 3인 팀이 `IWR6843 기반 실시간 객체추적 시스템`을 3개월 안에 완성하기 위한 팀 운영용 요구사항 문서다.

기준 시점: 2026-03-12

이 문서의 목적은 다음 3가지다.

1. 이번 달 안에 반드시 끝내야 할 1단계 목표를 명확히 정의한다.
2. 팀원별 역할과 완료 기준(REQ, Acceptance Criteria)을 수치로 고정한다.
3. 캡스톤 발표와 현대모비스 인턴/취업 포트폴리오에 바로 쓸 수 있도록 증거 자료와 정량 KPI를 남기는 방식을 정리한다.

## 2. 프로젝트 한 줄 정의
`IWR6843 레이더의 TLV 포인트클라우드를 실시간으로 파싱하고, DBSCAN과 Kalman Filter로 객체를 추적한 뒤, 최종적으로는 컨베이어벨트 제어 이벤트까지 연결하는 실시간 레이더 객체추적 시스템`

## 3. 단계별 최종 목표

### 3.1 1단계 목표: 이번 달 MVP
이번 달 목표는 "완벽한 정밀 추적"이 아니라, 아래 기준을 만족하는 `동작하는 실시간 추적 MVP`를 만드는 것이다.

- IWR6843 실기기에서 TLV 프레임 수신 성공
- 실시간 포인트클라우드 파싱 성공
- DBSCAN으로 객체 후보 군집화 성공
- Kalman 기반 객체 추적 성공
- 평균 FPS `>= 15`
- 60초 이상 연속 동작
- 1개 객체, 2개 객체 기본 시나리오 데모 가능

### 3.2 2단계 목표: 중간 고도화
- 추적 흔들림 감소
- ID switch 감소
- 오검출/미검출 감소
- 시나리오별 파라미터 튜닝 체계화
- 장시간 안정성 확보

### 3.3 3단계 목표: 최종 시연
- 실시간 추적 결과를 이벤트로 변환
- STM32 또는 제어보드로 정지/감속/알람 명령 전송
- 컨베이어벨트 모사 시스템 제어 데모
- "센싱 -> 인지 -> 판단 -> 제어" 전체 흐름을 하나의 프로젝트로 증명

## 4. 팀 구조와 역할 정의

| 역할 | 담당 모듈 | 1차 책임 | 최종 산출물 |
|---|---|---|---|
| 팀원 A | TLV Parsing | UART 수신, 프레임 동기화, TLV 디코딩, 파서 안정성 | 안정적 `ParsedFrame` 출력 |
| 팀원 B | DBSCAN | 포인트 전처리 입력 기반 클러스터링, 파라미터 튜닝 | 안정적 객체 측정값 생성 |
| 팀원 C | Kalman Filter | 객체 연계, 상태추정, track life-cycle 관리 | 안정적 `TrackOutput` 생성 |

권장 운영 원칙:

- 각자 모듈만 잘 만드는 것으로 끝내면 안 된다.
- 모든 팀원은 `자기 모듈 단위 성능`과 `파이프라인 전체 성능` 둘 다 책임진다.
- 주 2회는 반드시 통합 테스트를 진행한다.

## 5. 모듈 인터페이스 계약
현재 코드 기준 인터페이스는 아래를 따른다.

### 5.1 TLV Parser 출력 계약
파서 단계 출력은 아래 정보를 포함해야 한다.

- `frame_number: int`
- `num_obj: int`
- `points: {x[], y[], z[], v[], range[], snr[], noise[]}`

추가 요구사항:

- 프레임 누락 여부 확인 가능해야 함
- 파싱 실패 시 크래시하지 않고 다음 프레임으로 복구해야 함
- 디버그 모드에서 fail reason을 확인할 수 있어야 함

### 5.2 DBSCAN 입력/출력 계약
입력:

- 파서 또는 전처리 단계에서 전달한 point list
- 각 포인트는 최소 `x, y`를 포함
- 가능하면 `z, v, snr`를 함께 사용

출력:

- `x, y, z`: cluster centroid
- `v`: cluster 평균 속도
- `size`: cluster 내 포인트 수
- `confidence`: cluster 신뢰도

### 5.3 Tracker 입력/출력 계약
입력:

- DBSCAN cluster list

출력:

- `track_id`
- `x, y, vx, vy`
- `age, hits, misses, confidence`

### 5.4 제어 단계 이벤트 계약
최종 단계에서는 tracking 결과를 아래 이벤트로 변환한다.

- `OBJECT_IN_ZONE`
- `OBJECT_STOPPED`
- `OBJECT_APPROACHING`
- `EMERGENCY_STOP`

이 이벤트는 STM32 또는 제어 대상 장비로 전달 가능해야 한다.

## 6. 시스템 REQ

### 6.1 Functional Requirements

#### FR-01. 실시간 UART 수신
- 시스템은 IWR6843의 CLI/Data 포트와 연결되어야 한다.
- cfg 전송 이후 Data 포트에서 연속 프레임을 수신해야 한다.

#### FR-02. TLV 프레임 파싱
- 시스템은 magic word를 기준으로 프레임 경계를 탐지해야 한다.
- header, TLV type, TLV length를 검증해야 한다.
- 최소한 `Detected Points`와 `SNR/Noise` TLV를 해석해야 한다.

#### FR-03. 파싱 오류 복구
- 잘못된 패킷 길이, 손상된 헤더, 불완전한 프레임이 들어와도 시스템 전체가 죽으면 안 된다.
- 다음 정상 magic word를 찾아 재동기화해야 한다.

#### FR-04. 전처리
- SNR threshold, noise threshold, range gate 기반 포인트 필터링이 가능해야 한다.
- 필터 전/후 포인트 수를 로그로 남겨야 한다.

#### FR-05. 객체 군집화
- DBSCAN으로 point cloud를 객체 단위 cluster로 변환해야 한다.
- `eps`, `min_samples`, `velocity feature 사용 여부`를 런타임 설정 가능해야 한다.

#### FR-06. 객체 추적
- cluster 입력을 기반으로 multi-object tracking을 수행해야 한다.
- track 생성/유지/삭제 정책을 가져야 한다.
- `association_gate`, `max_misses`, `min_hits`를 조정 가능해야 한다.

#### FR-07. 실시간 성능 로그
- 프레임별로 `raw points`, `filtered points`, `clusters`, `tracks`를 출력해야 한다.
- 최소 1초 윈도우 기준 FPS를 출력해야 한다.

#### FR-08. 실험 증거 저장
- 실험마다 날짜, 시나리오, 파라미터, 결과 KPI를 `docs/`와 `evidence/`에 남겨야 한다.
- 최소 CSV, 이미지, 짧은 동영상 중 2개 이상을 남겨야 한다.

#### FR-09. 제어 이벤트 출력
- 최종 단계에서는 zone/event 로직을 통해 STM32 전송 데이터 생성이 가능해야 한다.
- 명령 예시는 `STOP`, `SLOW`, `RESUME`, `ALARM` 중 최소 1개 이상이어야 한다.

#### FR-10. 재현 가능 실행
- 동일 시나리오에서 같은 인자값으로 실행하면 유사한 성능을 재현할 수 있어야 한다.
- 실행 명령, cfg 버전, 파라미터를 실험 로그에 남겨야 한다.

### 6.2 Non-Functional Requirements

#### NFR-01. 1단계 성능
- 평균 FPS `>= 15`
- P95 frame processing time `<= 67ms`
- 단일 객체 시나리오 60초 연속 추적 가능

#### NFR-02. 1단계 안정성
- 20분 연속 실행 중 크래시 `0회`
- 파서 복구 실패로 인한 전체 중단 `0회`

#### NFR-03. 1단계 추적 품질
- 단일 객체 직선 이동 시 ID switch `<= 1`
- 객체가 0.5초 이내 잠깐 약해져도 동일 track 유지율 `>= 80%`

#### NFR-04. 2단계 품질
- 평균 FPS `>= 18`
- 장시간 30분 연속 실행 성공
- 2객체 교차 시나리오에서 track fragmentation 감소

#### NFR-05. 3단계 제어 성능
- 객체가 zone 조건을 만족하면 제어 이벤트 발생
- 감지 후 이벤트 출력까지 end-to-end latency `<= 200ms`

## 7. 이번 달 1단계 완료 기준

### 7.1 이번 달 팀 공통 Acceptance Criteria
아래 6개를 모두 만족하면 이번 달 목표 달성으로 본다.

1. 실기기 IWR6843에서 live data를 수신한다.
2. 파서가 연속 프레임을 안정적으로 디코딩한다.
3. 최소 1개 객체를 실시간으로 추적한다.
4. 평균 FPS가 `15 이상`이다.
5. 60초 시연 영상을 확보한다.
6. KPI 로그와 실험 문서를 남긴다.

### 7.2 공통 필수 데모 시나리오

#### 시나리오 S1. 단일 객체 직선 이동
- 1명이 레이더 정면에서 좌우 또는 전후 이동
- 목적: 기본 detection, cluster, track continuity 확인

#### 시나리오 S2. 단일 객체 정지-재이동
- 1명이 이동 후 2초 정지 후 재이동
- 목적: track 유지, velocity 안정성 확인

#### 시나리오 S3. 2객체 분리 이동
- 2명이 서로 1m 이상 떨어져 이동
- 목적: cluster 분리, multi-track 생성 확인

## 8. 역할별 1개월 상세 REQ

### 8.1 TLV Parsing 담당 REQ

### 목표
`실기기 UART 데이터에서 끊기지 않고 ParsedFrame을 공급하는 안정적 입력 모듈 완성`

### 주차별 목표

#### Week 1
- IWR6843 UART 포트 연결 및 cfg 송신 성공
- raw byte dump 확보
- magic word 기반 header 탐색 로직 검증
- frame length와 frame number를 로그로 확인

#### Week 2
- `Detected Points(TLV type 1)` 파싱 검증
- `SNR/Noise(TLV type 7)` 파싱 검증
- 파서 출력 포맷 고정
- 정상 프레임과 비정상 프레임 예시 캡처

#### Week 3
- 파싱 실패 유형 분류
- 재동기화(resync) 전략 검증
- 파서 디버그 로그 정리
- 파서 처리시간 측정 추가

#### Week 4
- DBSCAN 담당자와 통합
- 실기기 연속 10분 테스트
- parser success rate 계산
- 발표용 파서 구조 설명 자료 정리

### 상세 REQ
- REQ-PAR-01: magic word 탐지 성공률이 높아야 한다.
- REQ-PAR-02: TLV length 검증으로 비정상 패킷을 걸러야 한다.
- REQ-PAR-03: frame number 누락/역전 여부를 감지해야 한다.
- REQ-PAR-04: 파싱 실패 시 프로그램 전체가 죽지 않아야 한다.
- REQ-PAR-05: `x, y, z, v, range, snr, noise`를 일관된 구조로 출력해야 한다.
- REQ-PAR-06: 디버그 모드에서 fail reason을 남겨야 한다.

### Acceptance Criteria
- 10,000 frame 기준 parser success rate `>= 99%`
- 손상 프레임 또는 중간 byte 누락이 있어도 다음 정상 프레임으로 복구
- 파서 평균 처리시간 `<= 10ms/frame`
- frame number가 단조 증가하는 로그 증명 가능

### 남겨야 할 증거
- `evidence/parser_benchmark.csv`
- raw dump 일부 샘플
- 정상/비정상 파싱 로그 캡처
- 파서 처리시간 그래프

### 면접에서 강조할 포인트
- UART binary protocol parser를 직접 구현했다는 점
- corrupted frame recovery를 설계했다는 점
- 실시간 시스템에서 parser 안정성이 전체 성능을 좌우한다는 관점을 설명할 수 있어야 한다

### 8.2 DBSCAN 담당 REQ

### 목표
`노이즈를 줄이고 객체 단위 measurement를 안정적으로 생성하는 clustering 모듈 완성`

### 주차별 목표

#### Week 1
- point cloud 시각화
- baseline DBSCAN 적용
- `eps`, `min_samples` 기본값 후보 3세트 도출

#### Week 2
- SNR/noise/range filter 이후 cluster 품질 비교
- 단일 객체 시나리오에서 1개 cluster 유지율 측정
- noise label 비율 측정

#### Week 3
- 2객체 시나리오에서 분리율 테스트
- velocity feature 적용 여부 비교
- cluster confidence 정의 개선

#### Week 4
- tracker 담당자와 통합
- 실시간 성능 측정
- 발표용 파라미터 테이블 정리

### 상세 REQ
- REQ-DBS-01: point cloud를 객체 단위 cluster로 변환해야 한다.
- REQ-DBS-02: `eps`, `min_samples`를 시나리오별로 조정 가능해야 한다.
- REQ-DBS-03: noise point를 -1 label로 구분하고 비율을 기록해야 한다.
- REQ-DBS-04: cluster centroid와 size를 tracker 입력용으로 안정적으로 출력해야 한다.
- REQ-DBS-05: 잘못된 병합과 과분할 사례를 실험 로그로 정리해야 한다.

### Acceptance Criteria
- 단일 객체 시나리오에서 `1 cluster 유지율 >= 90%`
- 2객체가 1m 이상 분리된 경우 `2 cluster 분리 성공률 >= 85%`
- 클러스터링 평균 처리시간 `<= 15ms/frame`
- noise 비율과 false cluster 사례를 설명 가능한 수준으로 문서화

### 남겨야 할 증거
- `experiments/` 시각화 이미지
- `evidence/dbscan_param_sweep.csv`
- 단일 객체/2객체 비교표
- 파라미터별 성능 테이블

### 면접에서 강조할 포인트
- 비전이 아닌 radar point cloud에서 clustering을 튜닝했다는 점
- 단순 "DBSCAN 사용"이 아니라 `실시간성`과 `추적 안정성` 관점으로 파라미터를 설계했다는 점
- cluster output contract를 tracker와 연결한 시스템 사고를 보여줘야 한다

### 8.3 Kalman Filter 담당 REQ

### 목표
`cluster centroid 기반 다중 객체 추적 모듈 완성`

### 주차별 목표

#### Week 1
- 2D constant velocity Kalman tracker baseline 구현
- 상태벡터와 측정벡터 정의
- predict/update 루프 검증

#### Week 2
- association gate 설계
- greedy matching 또는 Hungarian 기반 연계 전략 비교
- track 생성/삭제 정책 초안 확정

#### Week 3
- `Q`, `R`, `association_gate`, `max_misses`, `min_hits` 튜닝
- 단일 객체 continuity 측정
- ID switch, miss, fragmentation 측정

#### Week 4
- DBSCAN 출력과 통합
- 실시간 로그 정리
- 발표용 tracker state 설명 자료 정리

### 상세 REQ
- REQ-KF-01: 최소 2D 위치 기반 객체 상태를 추정해야 한다.
- REQ-KF-02: track 생성/유지/삭제 규칙이 있어야 한다.
- REQ-KF-03: 측정이 잠깐 사라져도 track continuity를 유지해야 한다.
- REQ-KF-04: `track_id`, `x`, `y`, `vx`, `vy`, `hits`, `misses`를 출력해야 한다.
- REQ-KF-05: ID switch와 track fragmentation을 측정해야 한다.

### Acceptance Criteria
- 단일 객체 60초 시나리오에서 ID switch `<= 1`
- 0.5초 이하 일시 누락 구간에서 동일 track 유지율 `>= 80%`
- tracker 평균 처리시간 `<= 5ms/frame`
- track 생성/삭제가 로그로 설명 가능

### 남겨야 할 증거
- `evidence/tracker_metrics.csv`
- track id timeline 그래프
- 단일 객체/2객체 시나리오 결과 영상
- 파라미터별 ID switch 비교표

### 면접에서 강조할 포인트
- 센서 입력이 불안정한 상황에서 상태추정을 설계했다는 점
- 단순 필터 구현이 아니라 `data association + life-cycle management`까지 다뤘다는 점
- tracking KPI를 수치화했다는 점

## 9. 팀 공통 운영 REQ

### REQ-OPS-01. Git 운영
- `main`에는 통합 테스트를 통과한 코드만 반영
- 모듈별 브랜치 사용 권장
- 실험마다 commit message에 scenario와 parameter 변경 이유를 남김

### REQ-OPS-02. 주간 회의
- 월요일: 주간 목표 확정
- 수요일: 중간 점검
- 금요일: 통합 테스트 및 KPI 기록

### REQ-OPS-03. Definition of Done
각자 "구현 완료"는 아래 4개를 모두 만족해야 한다.

1. 코드 동작
2. 로그/성능 수치 존재
3. 실패 케이스 설명 가능
4. 다른 모듈과 인터페이스 연결 완료

### REQ-OPS-04. 통합 우선순위
- 개별 정확도 100점을 노리기보다 전체 파이프라인 80점 완성을 우선
- 캡스톤은 "개별 알고리즘 구현"보다 "실시간 시스템 통합"이 평가 포인트가 된다

## 10. 1개월 상세 일정

| 주차 | 팀 목표 | TLV 담당 | DBSCAN 담당 | Kalman 담당 | 공통 산출물 |
|---|---|---|---|---|---|
| 1주차 | 레이더 데이터 확보, baseline 동작 | UART 연결, raw dump, magic word 검증 | point 시각화, baseline DBSCAN | baseline KF, 상태모델 정의 | 첫 통합 입력/출력 계약 |
| 2주차 | 모듈 단위 기능 완성 | type1/type7 파싱 완성 | 파라미터 1차 튜닝 | association/track 정책 확정 | 단일 객체 시나리오 1차 테스트 |
| 3주차 | 안정화와 계측 | resync, fail log, latency 측정 | 분리율/오검출 측정 | ID switch/fragmentation 측정 | KPI 측정 체계 구축 |
| 4주차 | 실시간 데모 완성 | 10분 안정성 검증 | 실시간 cluster 품질 검증 | 실시간 continuity 검증 | 60초 데모 영상, 성능표, 발표자료 |

## 11. 3개월 개발 목표와 과정

### 11.1 Month 1: 실시간 추적 MVP 완성

### 목표
- IWR6843 실기기 기반 실시간 추적 파이프라인 완성
- 평균 FPS `>= 15`
- 기본 시연 확보

### 핵심 산출물
- live parsing 동작
- DBSCAN cluster 결과
- Kalman tracking 결과
- FPS/latency 로그
- 60초 데모 영상

### 필수 KPI
- Avg FPS
- P95 latency
- Parser success rate
- Single-object ID switch
- Crash count

### 발표 포인트
- "실시간으로 동작하는 최소 제품을 만들었다"
- "센서 입력부터 추적 출력까지 end-to-end로 구현했다"

### 11.2 Month 2: 품질 고도화와 산업형 구조화

### 목표
- 추적 품질과 안정성 강화
- 다중 시나리오 실험 체계화
- 제어 이벤트 설계 시작

### 해야 할 일
- static clutter 제거 전략 추가 검토
- range별 threshold 조정
- velocity feature scaling
- Hungarian assignment 또는 개선된 association 검토
- zone detection 로직 설계
- replay 기반 비교 실험 자동화

### 목표 KPI
- Avg FPS `>= 18`
- 30분 연속 실행 성공
- 2객체 시나리오 ID switch/fragmentation 감소
- false track count 감소

### 산출물
- 파라미터 튜닝 표
- 시나리오별 성능 비교표
- 제어 이벤트 설계 문서
- 데모 영상 2종 이상

### 발표 포인트
- "단순 동작"에서 끝난 것이 아니라 품질 개선 근거를 축적했다
- "무엇을 바꾸면 어떤 KPI가 좋아지는지"를 설명할 수 있다

### 11.3 Month 3: 컨베이어 제어 연동과 포트폴리오 마감

### 목표
- radar tracking 결과를 제어 이벤트로 연결
- 컨베이어벨트 모사 시스템 데모 완성
- 취업용 프로젝트 패키징 완료

### 해야 할 일
- zone/event rule 엔진 구현
- `OBJECT_IN_ZONE -> STM32 명령 전송` 연결
- 제어 안전 규칙 정의
- 이벤트 로그와 latency 측정
- 최종 발표 슬라이드, 포스터, 시연 영상 정리

### 목표 KPI
- event trigger latency `<= 200ms`
- 제어 이벤트 오동작률 최소화
- 최종 데모 3분 이상 안정 시연

### 산출물
- 실시간 제어 데모 영상
- 아키텍처 다이어그램 최종본
- KPI 종합표
- 이력서/포트폴리오용 프로젝트 요약본

### 발표 포인트
- "센싱-인지-제어" 폐루프를 구현했다
- "현업형 문제 정의, 실험, 개선, 검증" 흐름이 있다

## 12. 취업에 도움이 되도록 반드시 남겨야 할 정량 지표
취업용 프로젝트는 "재미있는 아이디어"보다 "정량적으로 검증된 엔지니어링 결과"가 중요하다.

### 12.1 시스템 성능 지표
- Avg FPS
- P95 frame time
- End-to-end latency
- CPU 사용률
- 장시간 실행 성공 시간

### 12.2 센서/파서 지표
- parser success rate
- corrupted frame recovery count
- dropped frame ratio
- valid point ratio

### 12.3 클러스터링 지표
- single-object 1 cluster 유지율
- 2객체 분리 성공률
- noise ratio
- false cluster count

### 12.4 추적 지표
- ID switch count
- fragmentation count
- track continuity ratio
- false track count
- reacquisition time

### 12.5 제어 지표
- event trigger latency
- missed trigger count
- false alarm count
- stop/resume success rate

## 13. 증거 자료 관리 방식

### 13.1 실험 파일 네이밍 규칙
권장 형식:

`YYYY-MM-DD_[scenario]_[version]`

예시:

- `2026-03-15_single_walk_v1.mp4`
- `2026-03-15_single_walk_v1.csv`
- `2026-03-15_single_walk_v1.md`

### 13.2 최소 저장 세트
실험 1건마다 아래를 남기는 것을 권장한다.

1. 실행 명령
2. cfg 버전
3. 파라미터 값
4. CSV 로그
5. 결과 이미지 또는 그래프
6. 30~60초 동영상
7. 해석 한 줄

### 13.3 권장 저장 위치
- 성능 요약: `docs/performance_log.md`
- 수치 데이터: `evidence/*.csv`
- 그래프/캡처: `evidence/*.png`
- 시각화 이미지: `experiments/*.png`
- 데모 영상: `evidence/videos/` 또는 별도 클라우드 링크

### 13.4 CSV 권장 컬럼
아래 컬럼을 기준으로 누적하면 면접 때 매우 강하다.

- `date`
- `scenario`
- `cfg_name`
- `snr_threshold`
- `dbscan_eps`
- `dbscan_min_samples`
- `association_gate`
- `avg_fps`
- `p95_latency_ms`
- `parser_success_rate`
- `single_cluster_ratio`
- `id_switch_count`
- `false_track_count`
- `notes`

## 14. 현대모비스 인턴/취업용으로 어떻게 포장할지

### 14.1 프로젝트에서 보여줄 수 있는 역량
- 센서 데이터 파이프라인 설계
- 시리얼 통신 및 바이너리 프로토콜 파싱
- clustering/tracking 알고리즘 적용
- 실시간 시스템 최적화
- 성능 측정 및 실험 설계
- 임베디드 제어 연동

### 14.2 이력서 문장 예시
- `TI IWR6843 mmWave radar 기반 실시간 객체추적 시스템 구현, TLV parsing-DBSCAN-Kalman tracking 파이프라인 통합`
- `실기기 환경에서 평균 15 FPS 이상의 실시간 추적 성능 달성`
- `corrupted UART frame 복구 로직과 추적 KPI 계측 체계를 구축하여 시스템 안정성 검증`
- `추적 결과를 제어 이벤트로 변환하여 STM32 기반 컨베이어 제어 데모 구현`

### 14.3 면접에서 어필해야 할 포인트
- "어떤 알고리즘을 썼다"보다 "왜 그 구조를 택했고 어떤 KPI로 검증했는가"를 말해야 한다.
- 실패 케이스와 개선 과정을 설명할 수 있어야 한다.
- 본인 담당 파트만 말하지 말고 시스템 전체 병목과 통합 이슈를 설명할 수 있어야 한다.

## 15. 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| 레이더 포인트 수가 적음 | DBSCAN 분리 실패 | cfg 조정, threshold 완화, 시나리오 단순화 |
| UART 수신 불안정 | 전체 파이프라인 중단 | buffer/resync 강화, fail-safe 로그 |
| 객체가 가까워 cluster 병합 | multi-track 실패 | eps 재조정, velocity feature 검토 |
| tracker 흔들림 심함 | 데모 품질 저하 | Q/R, gate, miss 정책 튜닝 |
| 한 명만 통합을 알고 있음 | 팀 리스크 큼 | 주 2회 통합, 인터페이스 문서 고정 |
| 수치 증거 미정리 | 취업 활용도 저하 | 실험 직후 `docs`와 `evidence` 업데이트 |

## 16. 이번 주 바로 실행할 일

1. 팀원 3명이 이 문서 기준으로 역할/수치를 합의한다.
2. 이번 주 안에 `S1 단일 객체 시나리오` 로그 1건을 반드시 남긴다.
3. `parser success rate`, `avg fps`, `id switch` 3개를 공통 핵심 KPI로 고정한다.
4. 금요일마다 `docs/performance_log.md`를 업데이트한다.
5. 4주차 종료 시점에 60초 데모 영상을 확보한다.

## 17. 최종 판단 기준
이 프로젝트의 성공은 "정확도가 완벽한가"가 아니라 아래를 증명하는 데 있다.

- 실기기 센서 데이터를 직접 다뤘는가
- 실시간으로 동작하는가
- 수치로 성능을 설명할 수 있는가
- 알고리즘을 시스템으로 통합했는가
- 최종적으로 제어까지 연결했는가

이 다섯 가지가 확보되면 캡스톤, 인턴, 취업 포트폴리오 모두에서 충분히 경쟁력 있는 프로젝트가 된다.
