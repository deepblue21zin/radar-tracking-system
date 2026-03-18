# Radar Tracking System

실시간 TI mmWave(IWR6843) 포인트클라우드를 수집/전처리/클러스터링/트래킹하여 객체 단위 상태를 출력하는 파이프라인 프로젝트입니다.

## 1. 프로젝트 목표
- UART TLV 스트림을 안정적으로 파싱
- 노이즈 제거 후 객체 후보를 DBSCAN으로 군집화
- Kalman 기반 다중 객체 트래킹 수행
- 실시간 운영 지표(FPS, 프레임별 처리 상태) 출력

핵심 파이프라인:
`TLV Parse -> Preprocess -> DBSCAN -> Kalman Tracking -> Runtime Metrics`

## 2. 디렉터리 구조
```text
radar-tracking-system/
├─ docs/
│  ├─ architecture.md
│  ├─ architecture_analysis_spec.md
│  ├─ capstone_pipeline_spec.md
│  ├─ FMEA.md
│  └─ performance_log.md
├─ evidence/
├─ experiments/
└─ src/
   ├─ parser/
   │  ├─ tlv_packet_parser.py
   │  └─ tlv_parse_runner.py
   ├─ filter/
   │  └─ noise_filter.py
   ├─ cluster/
   │  └─ dbscan_cluster.py
   ├─ tracking/
   │  ├─ kalman_tracker.py
   │  ├─ tracker_utils.c
   │  └─ tracker_utils.h
   ├─ communication/
   │  └─ stm32_uart_tx.c
   ├─ filterpy-master/
   └─ plot_dbscan.py
```

## 3. 요구사항
- Python 3.10+
- Windows (COM 포트 기준) 또는 Linux (tty 포트로 치환)
- TI IWR6843 + 유효한 mmWave cfg 파일

권장 환경:
```bash
conda activate mmwave_env
python -m pip install -r requirements.txt
```

필수 패키지:
```bash
pyserial==3.5
numpy==1.26.4
scikit-learn==1.5.2
filterpy==1.4.5
matplotlib==3.9.2
```

참고:
- `filterpy`는 pip 설치를 권장합니다.
- 로컬 `src/filterpy-master`는 fallback 용도로만 사용합니다.
- `matplotlib`는 `src/visualization/live_rail_viewer.py` 3D 디버그 뷰어에 필요합니다.

## 4. 빠른 시작
프로젝트 루트(`radar-tracking-system/radar-tracking-system`)에서 실행한다.

### 4.1 기본 실행
가장 먼저 정상 동작 여부를 볼 때 쓰는 명령이다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg
```

### 4.2 60초 baseline 측정
summary CSV와 FPS 로그를 비교할 때 추천하는 명령이다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 60 --scenario baseline --roi-tag full_frame
```

### 4.3 좌표값을 같이 보고 싶을 때
filtered point, cluster, track의 좌표 일부를 콘솔과 frame CSV에 같이 남긴다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --coord-preview-count 3 --coord-preview-every 10
```

의미:
- `--coord-preview-count 3`: 첫 3개 좌표만 출력
- `--coord-preview-every 10`: 10프레임마다 한 번만 출력

### 4.4 파서 debug를 보고 싶을 때
header 값과 parser 내부 상태를 확인할 때 쓴다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --debug --duration 30
```

### 4.5 좌표 preview + baseline을 같이 보고 싶을 때

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 60 --scenario coord_check --roi-tag full_frame --coord-preview-count 2 --coord-preview-every 20
```

### 4.6 3D 시각화로 보고 싶을 때
오른쪽 rail이 있는 3D 디버그 viewer를 실행한다.

```bash
python src/visualization/live_rail_viewer.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg
```

문제가 생기면:
- 예외가 `docs/error/YYYY-MM-DD.md`에 자동 기록된다.
- direct script 실행과 module 실행 둘 다 지원한다.
- 화면에 ghost track가 많이 남으면 `--report-miss-tolerance 0` 또는 `--max-misses 3`로 더 보수적으로 볼 수 있다.

### 4.7 실행 시 확인 포인트
- 시작 직후 `[CFG] << Done` 응답이 정상적으로 이어지는지 확인
- 프레임 로그가 `frame=... packet=... raw=... filtered=... clusters=... tracks=...` 형태로 이어지는지 확인
- 가능하면 `Ctrl-C`보다 `--duration`으로 종료해서 summary 비교가 쉬운 run을 남긴다
- 예외가 나면 `docs/error/YYYY-MM-DD.md`에 자동 기록된다

예상 로그:
```text
[CFG] >> sensorStart
[CFG] << Done
frame=123 packet=2848B raw=87 filtered=51 clusters=3 tracks=2 parser_ms=2.41 pipe_ms=7.88
[PERF] fps=14.8 window=1.01s
```

## 5. 실행 인자
`src/parser/tlv_parse_runner.py`

입출력:
- `--cli-port`: 레이더 CLI 포트 (예: `COM6`)
- `--data-port`: 레이더 Data 포트 (예: `COM5`)
- `--config`: mmWave cfg 파일 경로
- `--duration`: 실행 시간(초), 미지정 시 무한 실행
- `--debug`: 파서 디버그 출력
- `--coord-preview-count`: 좌표 preview 개수
- `--coord-preview-every`: 좌표 preview 출력 주기(frame)

전처리:
- `--snr-threshold`: 최소 SNR
- `--max-noise`: 최대 noise
- `--min-range`: 최소 거리
- `--max-range`: 최대 거리

클러스터링:
- `--dbscan-eps`: DBSCAN `eps`
- `--dbscan-min-samples`: DBSCAN `min_samples`
- `--use-velocity-feature`: `(x, y, v)`로 클러스터링

트래커:
- `--association-gate`: 트랙-측정 연계 거리 게이트(m)
- `--max-misses`: 삭제 전 최대 연속 미검출
- `--min-hits`: 출력 전 최소 hit 수
- `--report-miss-tolerance`: 화면/로그에 보여줄 최대 miss 허용치

시각화:
- `src/visualization/live_rail_viewer.py`: 3D right-rail 디버그 뷰어

## 6. 데이터 계약
파서 출력(`ParsedFrame`):
- `frame_number: int`
- `num_obj: int`
- `points: {x[], y[], z[], v[], range[], snr[], noise[]}`

클러스터 출력:
- `x, y, z`: 중심점
- `v`: 평균 속도
- `size`: 포인트 수
- `confidence`: 신뢰도(단순 점수)

트랙 출력:
- `track_id`
- `x, y, vx, vy`
- `age, hits, misses, confidence`

## 7. 성능 운영 기준(권장)
- 평균 FPS: `>= 10`
- P95 프레임 처리시간: `<= 100ms`
- 장시간 안정성: 30분 이상 크래시/메모리 누수 없음  

측정 및 기록:
- 런타임 FPS 로그: 표준 출력
- 실험 결과 기록: `docs/performance_log.md`

## 8. 트러블슈팅
1. `ModuleNotFoundError: sklearn` 또는 `filterpy`
- `pip install numpy scikit-learn filterpy` 재설치

2. 프레임이 안 올라옴
- COM 포트 매핑 확인(장치 관리자)
- cfg 경로/권한 확인
- Baudrate(115200/921600) 장비 설정과 일치 확인
- 에러 발생 시 `docs/error/YYYY-MM-DD.md` 자동 기록 확인

3. 트랙이 자주 끊김
- `--association-gate` 증가
- `--max-misses` 증가
- `--dbscan-eps` / `--dbscan-min-samples` 재튜닝

4. 화면에 ghost track가 너무 많이 남음
- `--report-miss-tolerance 0` 유지
- `--max-misses` 감소
- `--snr-threshold` 증가

## 9. 개발 가이드
- 새로운 기능은 파이프라인 계약을 깨지 않도록 모듈 단위로 추가
- 실험 결과는 `docs/`와 `evidence/`에 함께 기록
- 구조 변경 시 `docs/architecture.md`와 동기화

## 10. 관련 문서
- 아키텍처: `docs/architecture.md`
- 분석 명세: `docs/architecture_analysis_spec.md`
- 캡스톤 구현 명세: `docs/capstone_pipeline_spec.md`
- 팀 요구사항/3개월 로드맵: `docs/capstone_team_req_roadmap.md`
- TLV 개발 가이드: `docs/TLV.md`
- TLV 스터디 노트: `docs/study/study_TLV.md`
- 개발 진척 보드: `docs/elevation/README.md`
- 발표용 차별화 계획: `docs/elevation/ownership_plan.md`
- 시각화 진척 보드: `docs/elevation/visualization.md`
- DBSCAN 개발 가이드: `docs/DBSCAN.md`
- Kalman 개발 가이드: `docs/Kalman.md`
- 런타임 로깅/ROI 계획: `docs/runtime_logging_roi_plan.md`
- 에러 로그: `docs/error/`
- 수정 이력 리포트: `docs/correction report/`
- 성능 로그: `docs/performance_log.md`
- FMEA: `docs/FMEA.md`
