# Radar Modification Story Presentation Outline

## Slide 1. 제목
- Radar Tracking System
- 라이브러리 도입 이후 왜 수정이 계속 필요했는가
- 발표 목적: 수정의 이유와 시스템 엔지니어링 포인트 설명

## Slide 2. 출발점
- TLV Parse -> Preprocess -> DBSCAN -> Kalman Tracking -> Viewer/Control 파이프라인 구성
- 외부 라이브러리 활용: scikit-learn DBSCAN, FilterPy Kalman, TI mmWave packet parsing 기반
- 초기 목표: 빠르게 동작 확인
- 실제 한계: 환경 재현성, parser validity, continuity, 시각화 신뢰성, safety 설명 부족

## Slide 3. 왜 수정이 반복적으로 필요했나
- 라이브러리는 알고리즘 블록을 주지만, 실제 장비에서는 시스템 문제가 먼저 드러남
- cfg 적용 결과를 모르고, malformed frame을 확실히 거르지 못하고, viewer와 runtime 결과가 다를 수 있었음
- 실내 설치에서는 yaw/pitch/height, clutter, range gate가 tracking continuity에 직접 영향
- 따라서 "라이브러리 도입" 이후의 핵심은 시스템 정합성과 디버깅 가능성 확보였음

## Slide 4. 수정 흐름 요약 타임라인
- 03-15: 환경 정리, cfg 응답 로그, Type1 누락 fail, 에러 로그 체계
- 03-18 초반: filter/keepout/range/z gate 튜닝
- 03-18 오후: runtime_pipeline 분리 + 공용 params 구조
- 03-18 밤: viewer와 runtime 공용 처리 경로 정렬
- 03-19: world 좌표 보정, worker/draw 분리, 자동 리포트 생성

## Slide 5. 1단계 수정 이유: "되냐"보다 "왜 안 되냐"를 보여주기 위해
- requirements.txt 최소화 -> 팀원 환경 재현
- cfg 응답 로그 추가 -> bring-up 시 Error/Done 즉시 확인
- Type1 누락 frame fail -> 잘못된 point cloud를 정상 데이터로 넘기지 않음
- 날짜별 에러 로그 -> 현장 실패 원인 누적

## Slide 6. 2단계 수정 이유: viewer를 믿을 수 있어야 튜닝도 믿을 수 있음
- motion cloud, trail, velocity arrow, status overlay 추가
- viewer가 runtime과 다른 계산을 하지 않도록 공용 처리 함수 사용
- 최종적으로 runtime loop callback 기반 renderer로 재구성
- 이유: 시각화가 runtime truth와 다르면 잘못 튜닝하게 됨

## Slide 7. 3단계 수정 이유: 설치 자세와 draw stall이 실제 성능을 왜곡했기 때문
- sensor_yaw_deg 노출 -> 축 틀어짐 원인 분리
- sensor_pitch_deg, sensor_height_m 추가 -> world coordinate 보정
- viewer read/process와 draw 분리 -> Matplotlib stall이 parser/control을 막지 않게 함
- disable-text-log, disable-overview-png -> 병목을 logging과 draw로 분리 측정

## Slide 8. 로그 근거로 본 개선 과정
- 20260315_165830: FPS 0.158, avg pipe 6311 ms, 사실상 unusable
- 20260318_024048: FPS 9.36, filter는 동작했지만 continuity 약함
- 20260319_015812: FPS 9.87, parser health 개선, zero-track 27/395까지 감소
- 20260319_023912: parser health는 더 좋아졌지만 range gate / multi-track split이 남음
- 의미: 문제는 사라진 것이 아니라 "어디가 병목인지"가 점점 분리되어 보이게 됨

## Slide 9. 라이브러리 사용과 직접 기여의 경계
- 가져온 것: DBSCAN 알고리즘, Kalman 수학 기반, 기본 TLV parsing 아이디어
- 직접 바꾼 것: 환경 재현성, parser validity policy, runtime 구조, shared processing path, world coordinate correction, viewer architecture, logging/reporting automation
- 발표 포인트: 라이브러리 사용 후에 실제 장비에서 신뢰 가능한 시스템으로 만들기 위해 엔지니어링을 수행함

## Slide 10. 현재 상태와 다음 단계
- 현재: shared runtime pipeline, 공용 params, world 보정, viewer decoupling, 자동 리포트, REQ 문서 확보
- 남은 것: health gate, max/p95 latency summary, interface health bitfield, RTOS reference skeleton
- 결론: 라이브러리 도입 이후 진짜 작업은 알고리즘보다 시스템을 믿을 수 있게 만드는 과정이었음
