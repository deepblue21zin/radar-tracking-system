# Runtime Pipeline and Control Study Note

## 1. 문서 목적
이 문서는 현재 `radar-tracking-system` 코드베이스에서

- 어떤 변경이 들어갔는지
- Python/STM32가 어떤 역할로 나뉘는지
- 실제 실행은 무엇을 기준으로 하는지
- 전체 데이터 흐름이 어떻게 이어지는지
- 현재 기준에서 주의해야 할 리스크가 무엇인지

를 한 번에 정리하기 위한 study note이다.

기준 시점:

- 2026-03-18

---

## 2. 현재 기준 핵심 정리

### 2.1 PC 쪽 메인 실행 파일
현재 Python 파이프라인의 메인 entrypoint는 아래 파일이다.

- `src/parser/tlv_parse_runner.py`
- `src/parser/runtime_pipeline.py`

역할 분리는 이렇게 이해하면 된다.

- `tlv_parse_runner.py`: 기존 실행 명령과 import를 유지하는 호환 래퍼
- `runtime_pipeline.py`: 실제 cfg 전송, UART 수신, parse, filter, cluster, track, control, logging 구현

실행 시 내부에서 아래 모듈들을 순서대로 사용한다.

- `src/parser/tlv_packet_parser.py`
- `src/filter/noise_filter.py`
- `src/cluster/dbscan_cluster.py`
- `src/tracking/kalman_tracker.py`
- `src/control/proximity_speed_control.py`
- `src/communication/control_protocol.py`

반복 튜닝 기본값은 아래 파일에서 공통으로 관리한다.

- `src/runtime_params.py`
- `config/runtime_params.json`

즉 사용자가 보는 실행 명령은 `tlv_parse_runner.py`지만,
실구현은 `runtime_pipeline.py`가 전체 파이프라인을 묶는 구조이다.

### 2.2 STM32 쪽 파일
아래 파일은 PC에서 실행하는 파일이 아니다.

- `src/communication/stm32_control_rx_example.c`
- `src/communication/control_packet_protocol.h`

이 파일들은 STM32CubeIDE 같은 STM32 프로젝트 안으로 가져가서

- UART 수신
- 제어 패킷 파싱
- 목표 속도 반영
- 모터 제어

를 수행하도록 쓰는 예제/스캐폴드 코드이다.

즉 구조는 아래처럼 나뉜다.

- Python: 레이더 데이터 수집, 파싱, 필터링, 클러스터링, 트래킹, 제어 판단, STM32 송신
- STM32: Python이 보낸 제어 패킷 수신, 모터 속도 적용

---

## 3. 지금까지 반영된 주요 변경사항

## 3.1 `src/cluster/dbscan_cluster.py`
기존 baseline DBSCAN을 조금 더 안정적인 형태로 보완했다.

주요 변경:

- `velocity_weight` 파라미터 추가
- `(x, y, v)` feature 사용 시 속도를 그대로 쓰지 않고 `v * velocity_weight`로 스케일링
- 비정상 좌표/수치 입력 정리
- centroid 계산 시 `snr`가 있으면 SNR 가중 평균 사용
- `spread_xy`, `mean_snr`, `centroid_method` 출력 추가
- `confidence`를 point count만이 아니라 `size + snr + spread` 기반 heuristic으로 계산

이 변경의 목적은 다음과 같다.

- 속도 feature가 XY 거리 기준을 과도하게 망치지 않게 하기
- centroid 흔들림을 줄이기
- cluster 품질을 분석할 수 있는 보조 지표를 남기기

## 3.2 `src/control/proximity_speed_control.py`
새 제어 판단 모듈을 추가했다.

핵심 개념:

- `ControlZone`: 직사각형 ROI
- `ProximitySpeedController`: 접근/정지/근접 여부를 보고 `STOP/SLOW/RESUME` 결정

판단에 사용되는 주요 값:

- `slow_distance`
- `stop_distance`
- `resume_distance`
- `slow_speed_ratio`
- `approach_speed_threshold`
- `stationary_speed_threshold`
- `clear_frames_required`

이 모듈은 최종적으로 `ControlDecision`을 만든다.

포함 정보 예:

- `command`
- `speed_ratio`
- `primary_event`
- `track_id`
- `zone_distance_m`
- `closing_speed_mps`
- `inside_zone`
- `approaching`
- `changed`

## 3.3 `src/parser/runtime_pipeline.py`
현재 real-time parser runner의 실제 구현은 이 파일에 있다.

추가된 내용:

- `send_config()` 이후 `time.sleep(0.2)` + `data_port.reset_input_buffer()` 적용
- `--params-file` 기반 공용 기본값 로딩
- control 관련 CLI 옵션 추가
- runtime CSV 로그에 control 관련 컬럼 추가
- `ControlZone`, `ProximitySpeedController` 초기화
- frame loop 안에서 `ControlDecision` 생성
- 필요 시 STM32로 제어 패킷 송신

즉 기존 `parse -> filter -> cluster -> track` 흐름에

- `control decision`
- `optional STM32 UART tx`

가 추가된 상태이다.

### 3.3.1 `src/parser/tlv_parse_runner.py`
이 파일은 위 구현을 그대로 다시 export하는 호환 래퍼다.

의미:

- 기존 실행 명령을 바꾸지 않아도 된다.
- 기존 import 경로를 쓰던 코드도 크게 안 깨진다.

## 3.4 `src/communication/control_protocol.py`
Python에서 STM32로 보낼 제어 패킷 인코더/송신기를 추가했다.

현재 패킷 역할:

- `STOP`, `SLOW`, `RESUME`
- `speed_ratio`
- `event`
- zone 거리
- closing speed
- flags
- CRC8

즉 Python의 제어 판단을 STM32가 해석 가능한 고정 길이 패킷으로 바꾸는 역할이다.

## 3.5 `src/communication/control_packet_protocol.h`
Python과 STM32가 같은 형식으로 패킷을 해석하도록
공통 상수/구조체를 정리한 헤더이다.

## 3.6 `src/communication/stm32_control_rx_example.c`
STM32 쪽 수신/파싱/속도 갱신 예제를 추가했다.

현재 구현 범위:

- UART byte stream parser
- CRC 검사
- command/event 해석
- target speed 갱신
- timeout fail-safe
- 간단한 ramp

아직 TODO로 남아 있는 부분:

- 실제 UART HAL 연결
- 실제 모터 드라이버 출력
- TB6600 기준 STEP/DIR/ENA 제어

---

## 4. 전체 런타임 플로우

## 4.1 설정/시작
사용자는 계속 `tlv_parse_runner.py`를 실행한다.

다만 실제로 내부에서 main loop를 수행하는 구현은 `runtime_pipeline.py`다.

입력 예:

- CLI port
- Data port
- radar cfg 파일
- filtering/DBSCAN/tracking 파라미터
- control ROI/거리 파라미터
- optional STM32 output port

## 4.2 레이더 cfg 전송
`runtime_pipeline.py`는 CLI 포트로 cfg 파일의 명령을 한 줄씩 전송한다.

목적:

- radar profile 설정
- sensing 동작 시작
- startup stale byte를 줄이기 위해 `send_config()` 뒤에 잠깐 대기 후 `data_port.reset_input_buffer()`를 적용한다.

## 4.3 UART raw frame 수신
Data 포트에서는 raw bytes가 계속 들어온다.

이 raw bytes는 아직 사람이 읽을 수 있는 point 정보가 아니다.

## 4.4 TLV 파싱
`src/parser/tlv_packet_parser.py`가

- magic word
- packet length
- frame number
- TLV type/length

를 읽고

- point coordinates `(x, y, z, v)`
- `snr`
- `noise`

를 point-cloud 형태로 복원한다.

출력 형태는 대략 아래와 같다.

```python
{
    "x": [...],
    "y": [...],
    "z": [...],
    "v": [...],
    "range": [...],
    "snr": [...],
    "noise": [...],
}
```

## 4.5 point list 변환
`src/filter/noise_filter.py`의 `points_dict_to_list()`가
dict-of-arrays를 point list로 바꾼다.

예:

```python
[
    {"x": 1.2, "y": 0.4, "z": 0.1, "v": -0.3, "range": 1.27, "snr": 15.0, "noise": 3.0},
    {"x": 1.3, "y": 0.5, "z": 0.1, "v": -0.2, "range": 1.39, "snr": 14.0, "noise": 2.0},
]
```

## 4.6 point filtering
`preprocess_points()`가 아래 기준으로 point를 거른다.

- SNR threshold
- optional noise threshold
- range gate
- optional z gate

이 단계의 목적은 노이즈 point를 최대한 줄여 뒤 단계가 흔들리지 않게 하는 것이다.

## 4.7 DBSCAN clustering
`cluster_points()`가 filtered point들을 DBSCAN으로 묶는다.

기본 feature:

- `(x, y)`

옵션:

- `(x, y, v * velocity_weight)`

출력은 point가 아니라 object-like cluster list이다.

예:

```python
[
    {
        "x": 1.24,
        "y": 0.45,
        "z": 0.10,
        "v": -0.26,
        "size": 6,
        "confidence": 0.87,
        "label": 0,
        "spread_xy": 0.08,
        "mean_snr": 14.3,
        "centroid_method": "snr_weighted",
    }
]
```

## 4.8 tracking
`src/tracking/kalman_tracker.py`가 cluster centroid를 연속 프레임 사이에서 연결한다.

출력 형태:

- `track_id`
- `x`, `y`
- `vx`, `vy`
- `age`, `hits`, `misses`
- `confidence`

즉 이 단계부터는 "클러스터"가 아니라 "추적 객체" 성격이 강해진다.

## 4.9 control decision
`src/control/proximity_speed_control.py`가

- track 위치
- ROI와의 거리
- 접근 속도
- 정지 여부

를 보고 `STOP/SLOW/RESUME`를 만든다.

주요 이벤트:

- `OBJECT_APPROACHING`
- `OBJECT_IN_ZONE`
- `OBJECT_STOPPED`
- `EMERGENCY_STOP`
- `CLEAR`

주요 출력:

- `command`
- `speed_ratio`
- `primary_event`

## 4.10 logging / console output
각 frame마다 다음 정보가 콘솔과 CSV에 남는다.

- frame number
- raw / filtered / clusters / tracks 수
- parser latency
- pipeline latency
- control decision 정보

즉 디버깅할 때

- parser 문제인지
- filter 문제인지
- cluster 문제인지
- tracker/control 문제인지

를 단계별로 분리해서 볼 수 있다.

## 4.11 STM32 packet transmit
`--control-out-port`가 지정된 경우,
`ControlDecision`은 UART 패킷으로 인코딩되어 STM32로 전송된다.

## 4.12 STM32 side apply
STM32 쪽에서는

- packet parser
- CRC 검증
- command 해석
- target speed 변경
- periodic ramp / timeout fail-safe

를 수행한다.

마지막으로 실제 모터 제어는 보드와 드라이버에 맞는 코드로 연결해야 한다.

---

## 5. 제어 로직 요약

## 5.1 ROI
제어 기준은 `ControlZone`이라는 직사각형 ROI이다.

사용 예:

- `control-zone-x-min`
- `control-zone-x-max`
- `control-zone-y-min`
- `control-zone-y-max`

필요하면 `z` 범위도 추가 가능하다.

## 5.2 기본 파라미터
현재 기본값은 `config/runtime_params.json` 기준으로 아래와 같다.

- `slow_distance = 1.5`
- `stop_distance = 0.4`
- `resume_distance = 2.0`
- `slow_speed_ratio = 0.4`
- `approach_speed_threshold = 0.1`
- `stationary_speed_threshold = 0.05`
- `clear_frames_required = 3`

## 5.3 STOP
아래 중 하나면 `STOP`이다.

- ROI 안에 들어옴
- `zone_distance <= stop_distance`

출력:

- `command = STOP`
- `speed_ratio = 0.0`

## 5.4 SLOW
아래 조건이면 `SLOW`이다.

- `zone_distance <= slow_distance`
- 그리고 접근 중이거나, 이전 상태가 이미 `SLOW/STOP`

출력:

- `command = SLOW`
- `speed_ratio = slow_speed_ratio`

## 5.5 RESUME
아래 조건이면 `RESUME`이다.

- nearest object가 `resume_distance` 밖으로 벗어남
- 또는 no-track 상태가 일정 프레임 지속됨

출력:

- `command = RESUME`
- `speed_ratio = 1.0`

---

## 6. 실행 환경 정리

## 6.1 Python
현재 프로젝트에서는 `.venv` 가상환경을 사용한다.

확인된 환경:

- Python 3.12.10
- pip 정상 동작
- `requirements.txt` 설치 완료

설치된 주요 패키지:

- `pyserial`
- `numpy`
- `scikit-learn`
- `filterpy`

참고:

- `requirements.txt`에는 Python 3.10 / 3.11 권장이 적혀 있었지만
- 현재 3.12.10에서도 import와 CLI help까지는 정상 확인했다.

## 6.2 Git Bash
현재 사용 환경이 Git Bash인 경우,
PowerShell용 `Activate.ps1` 대신 아래를 써야 한다.

```bash
source .venv/Scripts/activate
```

또는 이미 `.venv`의 `python`이 PATH에 잡혀 있으면 바로 `python`을 써도 된다.

## 6.3 실행 명령
기본 실행 명령은 계속 wrapper entrypoint를 사용한다.

### 기본 실행

```bash
python src/parser/tlv_parse_runner.py --cli-port COM6 --data-port COM5 --config config/profile_3d.cfg
```

### 공용 파라미터 파일 기반 실행

```bash
python src/parser/tlv_parse_runner.py \
  --cli-port COM6 \
  --data-port COM5 \
  --config config/profile_3d.cfg \
  --params-file config/runtime_params.json
```

### control decision 포함 실행

```bash
python src/parser/tlv_parse_runner.py \
  --cli-port COM6 \
  --data-port COM5 \
  --config config/profile_3d.cfg \
  --control-enabled \
  --control-zone-x-min -0.8 \
  --control-zone-x-max 0.8 \
  --control-zone-y-min 0.3 \
  --control-zone-y-max 1.2
```

### STM32 송신 포함 실행

```bash
python src/parser/tlv_parse_runner.py \
  --cli-port COM6 \
  --data-port COM5 \
  --config config/profile_3d.cfg \
  --control-enabled \
  --control-zone-x-min -0.8 \
  --control-zone-x-max 0.8 \
  --control-zone-y-min 0.3 \
  --control-zone-y-max 1.2 \
  --control-out-port COM7
```

정리:

- 반복해서 바꾸는 값은 `config/runtime_params.json`에 둔다.
- 특정 실험값만 CLI로 덮어쓴다.
- `src/visualization/live_rail_viewer.py`도 같은 `--params-file`을 지원한다.

---

## 7. 현재 기준 참고 사항 / 리스크

## 7.1 z-axis control risk
control 입력은 track를 우선 사용한다.

그런데 현재 track 출력에는 `z`가 없다.
즉 `control-zone-z-min/max`를 설정해도 tracker를 통과한 뒤에는 기대와 다르게 동작할 수 있다.

정리:

- 2D control 기준으로는 괜찮음
- 3D zone control은 아직 미완성에 가까움

## 7.2 fallback cluster risk
track가 아직 안정화되지 않은 초기 프레임에서는 control이 cluster를 fallback으로 쓴다.

그런데 cluster에는 `vx`, `vy`가 없다.
그래서 이 시점에는

- `OBJECT_APPROACHING`
- `closing_speed`

판단이 약해질 수 있다.

## 7.3 tracker dt risk
tracker의 `dt` 계산은 전체 track별로 독립적이지 않고,
첫 번째 track의 timestamp를 기준으로 계산한다.

이 구조는 특정 상황에서 예측 위치가 튈 수 있는 여지를 만든다.

## 7.4 STM32 example code is not final motor driver code
`stm32_control_rx_example.c`는 예제 수신/제어 스캐폴드이다.

아직 직접 연결해야 하는 부분:

- UART HAL receive
- timer output
- TB6600 STEP/DIR/ENA
- immediate stop handling

즉 이 파일은 "바로 제품용 완성 코드"가 아니라
"STM32 프로젝트에 붙일 수 있는 출발점"에 가깝다.

## 7.5 `stm32_uart_tx.c`는 현재 메인 경로가 아님
현재 Python -> STM32 송신은 `control_protocol.py` 기반이다.

`src/communication/stm32_uart_tx.c`는 현재 메인 파이프라인에서 직접 쓰이지 않는 스텁 파일이다.

---

## 8. 발표/시연 관점에서 기억할 포인트

- 사용자가 실행하는 커맨드는 `tlv_parse_runner.py` 하나로 유지된다.
- 실제 런타임 구현은 `runtime_pipeline.py`에 있다.
- 반복 튜닝 파라미터는 `config/runtime_params.json`에서 runner/viewer가 공용으로 읽는다.
- STM32 C 파일은 별도로 STM32 프로젝트에 넣어 빌드/업로드해야 한다.
- 현재 시스템 구조는 `PC가 판단`, `STM32가 실제 구동`이다.
- 디버깅은 반드시 `raw -> filtered -> clusters -> tracks -> control` 순서로 나눠서 본다.

---

## 9. 다음 보완 우선순위

추천 우선순위:

1. control의 `z` 처리 보완
2. cluster fallback 시 접근 판단 약화 문제 보완
3. tracker `dt` 계산 개선
4. STM32 motor driver output 실제 보드 기준 구현
5. 시연 환경에 맞는 ROI / 거리 임계값 재튜닝

