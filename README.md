# Radar Tracking System

실시간 TI mmWave(IWR6843) 포인트클라우드를 수집하고, 필터링/DBSCAN/트래킹/제어 판단까지 연결해 객체 단위 상태를 출력하는 파이프라인 프로젝트입니다.

핵심 흐름:
`TLV Parse -> Preprocess -> DBSCAN -> Kalman Tracking -> Control / Runtime Metrics`

## 1. 현재 실행 구조
- 기존 실행 명령은 그대로 `src/parser/tlv_parse_runner.py`를 사용합니다.
- 실제 런타임 구현은 `src/parser/runtime_pipeline.py`에 있습니다.
- `src/parser/tlv_parse_runner.py`는 기존 명령과 import 호환을 위한 래퍼입니다.
- 공용 기본 파라미터는 `config/runtime_params.json`에 있습니다.
- 러너와 3D viewer는 둘 다 `--params-file`로 같은 기본값을 읽습니다.
- CLI 인자를 직접 주면 JSON 기본값보다 우선합니다.
- run 종료 후 실험 리포트와 성능 로그는 `src/reporting/` 보조 모듈이 생성합니다.

## 2. 디렉터리 구조
```text
radar-tracking-system/
├─ config/
│  └─ runtime_params.json
├─ docs/
│  ├─ architecture.md
│  ├─ capstone_pipeline_spec.md
│  ├─ doxygen_overview.md
│  ├─ experiment_reports/
│  └─ ...
├─ evidence/
├─ experiments/
└─ src/
   ├─ parser/
   │  ├─ tlv_packet_parser.py
   │  ├─ runtime_pipeline.py
   │  └─ tlv_parse_runner.py
   ├─ filter/
   │  └─ noise_filter.py
   ├─ cluster/
   │  └─ dbscan_cluster.py
   ├─ tracking/
   │  ├─ kalman_tracker.py
   │  ├─ tracker_utils.c
   │  └─ tracker_utils.h
   ├─ control/
   │  └─ proximity_speed_control.py
   ├─ communication/
   │  ├─ control_protocol.py
   │  └─ stm32_control_rx_example.c
   ├─ reporting/
   │  ├─ runtime_experiment_report.py
   │  ├─ performance_log_report.py
   │  ├─ generate_runtime_code_browser.py
   │  └─ generate_runtime_doxygen_portal.py
   ├─ visualization/
   │  └─ live_rail_viewer.py
   ├─ runtime_params.py
   └─ filterpy-master/
```

## 3. 요구사항
- Python 3.10+
- Windows(COM 포트 기준) 또는 Linux(tty 포트로 치환)
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
프로젝트 루트(`radar-tracking-system/radar-tracking-system`)에서 실행합니다.

### 4.1 기본 실행
가장 먼저 정상 동작 여부를 확인할 때 쓰는 명령입니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg
```

### 4.2 60초 baseline 측정
summary CSV와 FPS 로그를 비교할 때 추천하는 명령입니다. keepout/static clutter를 끄고 full-frame baseline을 봅니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 60 --scenario baseline --roi-tag full_frame --disable-near-front-keepout --disable-right-rail-keepout --disable-static-clutter-filter
```

### 4.3 parser-only 비교 run
viewer 없이 parser/runtime 안정성만 보고 싶을 때 씁니다. text log flush와 overview PNG 생성을 꺼서 비교 run을 가볍게 만듭니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 60 --disable-text-log --disable-overview-png
```

### 4.4 좌표 preview를 함께 보고 싶을 때
filtered point, cluster, track 좌표 일부를 콘솔과 frame CSV에 같이 남깁니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 40 --coord-preview-count 3 --coord-preview-every 10
```

의미:
- `--coord-preview-count 3`: 첫 3개 좌표만 출력
- `--coord-preview-every 10`: 10프레임마다 한 번만 출력

### 4.5 파라미터를 한 곳에서 반복 튜닝할 때
반복적으로 바꾸는 값은 `config/runtime_params.json`에서 관리하는 것이 가장 편합니다.

추천 흐름:
- 기본값은 `config/runtime_params.json`을 그대로 사용
- 러너와 viewer가 같은 파일을 함께 읽음
- 특정 run에서만 바꾸고 싶으면 CLI 인자로 덮어씀

예:
```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --dbscan-eps 0.55 --association-gate 1.2
```

### 4.6 기록용 run
실험 제목/문제/가설/변경/다음 단계를 같이 남기고 싶을 때 씁니다. run 종료 후 `docs/experiment_reports/`와 `docs/performance_log.md`가 갱신됩니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --duration 60 --disable-text-log --disable-overview-png --experiment-title "front back walk with pitch correction" --experiment-problem "viewer에서 대각선 이동처럼 보이고 추적이 자주 끊김" --experiment-hypothesis "pitch/height 미보정과 parser continuity가 동시에 영향" --experiment-change "sensor_pitch_deg=30, sensor_height_m=1.74 적용 후 parser-only 비교" --experiment-next-step "viewer 실시간 run에서 yaw/pitch 보정과 draw 분리 효과 재확인"
```

### 4.7 파서 debug를 보고 싶을 때
header 값과 parser 내부 상태를 확인할 때 씁니다.

```bash
python src/parser/tlv_parse_runner.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --debug --duration 30
```

### 4.8 3D 시각화로 보고 싶을 때
오른쪽 rail이 있는 3D 디버그 viewer를 실행합니다. viewer는 `run_realtime()`의 공용 처리 경로를 그대로 사용하고, runtime worker와 draw loop를 분리해서 최신 결과만 그립니다.

```bash
python src/visualization/live_rail_viewer.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg
```

시연용으로는 draw 부담을 줄이기 위해 이 명령을 먼저 추천합니다.

```bash
python src/visualization/live_rail_viewer.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --max-vis-fps 5
```

설치값을 CLI에서 직접 덮어쓰고 싶으면:

```bash
python src/visualization/live_rail_viewer.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg --sensor-yaw-deg 20 --sensor-pitch-deg 30 --sensor-height-m 1.74 --max-vis-fps 5
```

현재 `config/runtime_params.json` 예시 기본값은 다음 설치를 기준으로 잡혀 있습니다.
- `sensor_yaw_deg = 20`
- `sensor_pitch_deg = 30`
- `sensor_height_m = 1.74`
- `filter_z_min = -0.2`, `filter_z_max = 2.2`
- `max_range = 3.5`

문제가 생기면:
- 예외가 `docs/error/YYYY-MM-DD.md`에 자동 기록됩니다.
- direct script 실행과 module import 경로를 모두 고려한 fallback import가 들어 있습니다.
- ghost track가 많이 남으면 `--report-miss-tolerance 0` 또는 `--max-misses 3` 쪽을 먼저 확인합니다.

### 4.9 실행 시 확인 포인트
- 시작 직후 `[CFG] << Done` 응답이 정상적으로 이어지는지 확인
- 프레임 로그가 `frame=... gap=... packet=... raw=... filtered=... clusters=... tracks=...` 형태로 이어지는지 확인
- `send_config()` 이후 data port input buffer가 한 번 비워진 뒤 읽기가 시작되는지 확인
- 가능하면 `Ctrl-C`보다 `--duration`으로 종료해 summary 비교가 쉬운 run을 남깁니다

예상 로그:
```text
[CFG] >> sensorStart
[CFG] << Done
frame=123 gap=0 packet=2848B raw=87 filtered=51 clusters=3 tracks=2 parser_ms=2.41 pipe_ms=7.88
[PERF] fps=14.8 window=1.01s
```

## 5. 실행 인자
기본 실행 커맨드는 `src/parser/tlv_parse_runner.py`이고, 실제 구현은 `src/parser/runtime_pipeline.py`에 있습니다.

공용:
- `--params-file`: 공용 JSON 파라미터 파일 경로, 기본값 `config/runtime_params.json`
- `--cli-port`: 레이더 CLI 포트
- `--data-port`: 레이더 Data 포트
- `--config`: mmWave cfg 파일 경로
- `--duration`: 실행 시간(초), 미지정 시 무한 실행
- `--debug`: 파서 디버그 출력
- `--sensor-yaw-deg`
- `--sensor-pitch-deg`
- `--sensor-height-m`
- `--coord-preview-count`
- `--coord-preview-every`
- `--disable-file-log`: frame CSV / text log / summary / overview PNG를 모두 끔
- `--disable-text-log`: frame `.log` 텍스트 로그만 끔
- `--disable-overview-png`: 종료 후 자동 생성되는 overview PNG만 끔
- `--experiment-title`
- `--experiment-problem`
- `--experiment-hypothesis`
- `--experiment-change`
- `--experiment-next-step`

전처리:
- `--snr-threshold`
- `--max-noise`
- `--min-range`
- `--max-range`, 현재 예시 params 기본값 `3.5m`
- `--filter-x-min`, `--filter-x-max`
- `--filter-y-min`, `--filter-y-max`
- `--filter-z-min`, 현재 예시 params 기본값 `-0.2m`
- `--filter-z-max`, 현재 예시 params 기본값 `2.2m`
- `--disable-near-front-keepout`
- `--disable-right-rail-keepout`
- `--disable-static-clutter-filter`

클러스터링:
- `--dbscan-eps`
- `--dbscan-min-samples`
- `--use-velocity-feature`
- `--dbscan-velocity-weight`
- `--dbscan-adaptive-eps-bands`

트래커:
- `--association-gate`
- `--max-misses`
- `--min-hits`
- `--report-miss-tolerance`

제어/STM32:
- `--control-enabled`
- `--control-zone-x-min`, `--control-zone-x-max`
- `--control-zone-y-min`, `--control-zone-y-max`
- `--control-zone-z-min`, `--control-zone-z-max`
- `--control-slow-distance`
- `--control-stop-distance`
- `--control-resume-distance`
- `--control-belt-axis-x`, `--control-belt-axis-y`
- `--control-moving-confirm-sec`
- `--control-static-hold-sec`
- `--control-static-disp-window-sec`
- `--control-static-disp-threshold`
- `--control-out-port`

시각화:
- `src/visualization/live_rail_viewer.py`도 `--params-file`을 지원합니다.
- viewer는 공용 filter/clustering 기본값과 함께 시야 범위(`x/y/z`), `--max-vis-fps`, point history/trail 관련 인자를 읽습니다.
- 주요 viewer 인자:
  - `--max-vis-fps`
  - `--point-persistence-frames`
  - `--track-history-sec`
  - `--track-history-points`
  - `--velocity-arrow-scale`
  - `--velocity-min-speed`

## 6. 데이터 계약
파서 출력(`ParsedFrame`):
- `frame_number: int`
- `num_obj: int`
- `points: {x[], y[], z[], v[], range[], snr[], noise[]}`

클러스터 출력:
- `x, y, z`: centroid
- `v`: 평균 속도
- `size`: 포인트 수
- `confidence`: `size + snr + spread` 기반 heuristic score
- `spread_xy`, `mean_snr`, `centroid_method`

트랙 출력:
- `track_id`
- `x, y, vx, vy`
- `age, hits, misses, confidence`

제어 출력:
- `command`
- `speed_ratio`
- `primary_event`
- `track_id`
- `zone_distance_m`, `closing_speed_mps`

## 7. 성능 운영 기준
- 평균 FPS: `>= 10`
- P95 프레임 처리시간: `<= 100ms`
- 장시간 안정성: 30분 이상 크래시/메모리 누수 없음

측정 및 기록:
- 런타임 FPS 로그: 표준 출력
- 프레임 CSV/텍스트 로그: `evidence/runtime_logs/`
- 실험 결과 기록: `docs/performance_log.md`
- run별 구조화 리포트: `docs/experiment_reports/`
- 실험 과정 저널: `docs/experiment_journal.md`
- 원페이지 시스템 개요: `docs/runtime_system_onepage.html`
- 스토리보드 설명 페이지: `docs/runtime_storyboard.html`
- 코드 브라우저 페이지: `docs/runtime_code_browser.html`

시연/저부하 실행 팁:
- `live_rail_viewer.py`는 `disable_file_log=True`, `console_output=False`로 runtime loop에 붙으므로 시연 중 frame CSV/text log를 남기지 않습니다.
- `tlv_parse_runner.py`로 parser-only 안정성을 볼 때는 `--disable-text-log --disable-overview-png`를 먼저 켜서 flush 부담을 줄일 수 있습니다.

## 8. 트러블슈팅
1. `ModuleNotFoundError: sklearn` 또는 `filterpy`
- `python -m pip install -r requirements.txt` 재설치

2. 프레임이 안 올라옴
- COM 포트 매핑 확인
- cfg 경로/권한 확인
- baudrate(115200/921600) 장비 설정 일치 확인
- 에러 발생 시 `docs/error/YYYY-MM-DD.md` 자동 기록 확인

3. 튜닝 값을 자주 바꾸고 있는데 명령이 너무 길다
- `config/runtime_params.json`에서 반복 파라미터를 먼저 수정
- run별 실험만 CLI 인자로 덮어쓰기

4. 트랙이 자주 끊김
- `--association-gate` 증가
- `--max-misses` 증가
- `--dbscan-eps` / `--dbscan-min-samples` / `--dbscan-velocity-weight` 재튜닝

5. ghost track가 너무 많이 남음
- `--report-miss-tolerance 0` 유지
- `--max-misses` 감소
- `--snr-threshold` 증가
- keepout/static clutter 기본값이 장면과 맞는지 확인

## 9. 개발 가이드
- 반복 튜닝 값은 우선 `config/runtime_params.json`에 모읍니다.
- 새 기능은 파이프라인 계약을 깨지 않도록 모듈 단위로 추가합니다.
- 구조 변경 시 `README.md`, `docs/architecture.md`, `docs/doxygen_overview.md`를 함께 갱신합니다.
- 과거 장애/수정 로그는 `docs/error/`, `docs/correction report/`에 날짜 기준으로 남깁니다.

## 10. 관련 문서
- 시스템 요구사항 포털: `docs/system_requirements/index.html`
- 시스템 요구사항 패키지: `docs/system_requirements/README.md`
- 원페이지 시스템 개요 HTML: `docs/runtime_system_onepage.html`
- 스토리보드형 전체 설명 HTML: `docs/runtime_storyboard.html`
- 전체 코드 브라우저 HTML: `docs/runtime_code_browser.html`
- 아키텍처: `docs/architecture.md`
- Doxygen 개요: `docs/doxygen_overview.md`
- 캡스톤 구현 명세: `docs/capstone_pipeline_spec.md`
- TLV 개발 가이드: `docs/TLV.md`
- TLV 스터디 노트: `docs/study/study_TLV.md`
- 런타임/제어 스터디 노트: `docs/study/study_runtime_pipeline_and_control.md`
- 런타임 이슈/튜닝 계획: `docs/elevation/runtime_issue_fix_plan.md`
- 실험 과정 저널: `docs/experiment_journal.md`
- 시각화 진척 보드: `docs/elevation/visualization.md`
- 런타임 로깅/ROI 계획: `docs/runtime_logging_roi_plan.md`
- 에러 로그: `docs/error/`
- 수정 이력 리포트: `docs/correction report/`
- 자동 생성 run 리포트: `docs/experiment_reports/`
