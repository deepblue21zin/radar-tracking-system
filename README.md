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

필수 패키지:
```bash
pip install pyserial numpy scikit-learn filterpy
```

참고:
- `filterpy`는 pip 설치를 권장합니다.
- 로컬 `src/filterpy-master`는 fallback 용도로만 사용합니다.

## 4. 빠른 시작
프로젝트 루트(`radar-tracking-system/radar-tracking-system`)에서 실행:

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

예상 로그:
```text
frame=123 raw=87 filtered=51 clusters=3 tracks=2
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

3. 트랙이 자주 끊김
- `--association-gate` 증가
- `--max-misses` 증가
- `--dbscan-eps` / `--dbscan-min-samples` 재튜닝

## 9. 개발 가이드
- 새로운 기능은 파이프라인 계약을 깨지 않도록 모듈 단위로 추가
- 실험 결과는 `docs/`와 `evidence/`에 함께 기록
- 구조 변경 시 `docs/architecture.md`와 동기화

## 10. 관련 문서
- 아키텍처: `docs/architecture.md`
- 분석 명세: `docs/architecture_analysis_spec.md`
- 캡스톤 구현 명세: `docs/capstone_pipeline_spec.md`
- 성능 로그: `docs/performance_log.md`
- FMEA: `docs/FMEA.md`
