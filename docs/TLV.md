# TLV Parsing Guide

## 1. 이 문서는 누구를 위한 문서인가
이 문서는 `IWR6843 TLV 파싱`을 처음 맡은 팀원을 위한 문서다.

대상 독자:

- 대학생 2학년 수준에서 레이더 프로젝트를 처음 해보는 사람
- UART, binary parsing, buffer 개념이 아직 익숙하지 않은 사람
- "파서를 어디까지 만들면 되는지"와 "현업에서는 무엇을 중요하게 보는지"가 궁금한 사람

## 2. TLV가 뭐냐
TLV는 `Type-Length-Value`의 약자다.

쉽게 말하면 레이더가 보내는 한 덩어리 데이터 안에,

- 이 데이터가 무슨 종류인지 `Type`
- 길이가 몇 바이트인지 `Length`
- 실제 데이터 내용이 무엇인지 `Value`

를 같이 넣어 보내는 형식이다.

예를 들어,

- `Type 1`: 검출된 점들의 `(x, y, z, v)`
- `Type 7`: 각 점의 `snr`, `noise`

처럼 타입별로 의미가 다르다.

즉 TLV 파서는 "그냥 바이트를 읽는 코드"가 아니라, `레이더가 보낸 의미 있는 정보를 꺼내는 첫 번째 관문`이다.

## 3. 왜 TLV 파싱이 중요한가
이 프로젝트 전체 흐름은 아래와 같다.

`Radar UART -> TLV Parsing -> Point Filtering -> DBSCAN -> Kalman Tracking -> Control`

여기서 TLV 파싱이 흔들리면 뒤는 다 무너진다.

- frame 경계를 잘못 잡으면 좌표가 전부 깨진다.
- point 개수가 틀리면 DBSCAN이 이상해진다.
- 프레임이 중간에 누락되면 tracker가 튄다.
- 파서가 느리면 FPS가 바로 떨어진다.

현업 관점에서는 TLV 파서를 "전처리 코드"로 보지 않는다.
`센서 인터페이스의 신뢰성과 실시간성을 책임지는 핵심 모듈`로 본다.

## 4. 현재 코드 구조를 먼저 이해하자
현재 파서 관련 핵심 파일은 4개다.

- `src/parser/tlv_packet_parser.py`
- `src/parser/runtime_pipeline.py`
- `src/parser/tlv_parse_runner.py`
- `src/runtime_params.py`

역할은 이렇게 나뉜다.

### 4.1 `tlv_packet_parser.py`
이 파일은 `순수 바이트 덩어리`를 받아서 실제 숫자로 바꾼다.

주요 역할:

- magic word 찾기
- header 읽기
- TLV type/length 읽기
- Detected Points와 SNR/Noise 해석
- 최종적으로 점 데이터 배열 반환

쉽게 말하면 `바이트 해석기`다.

### 4.2 `runtime_pipeline.py`
이 파일은 실제 레이더 포트를 열고, 버퍼를 관리하면서 프레임 단위로 파서를 호출한다.

주요 역할:

- CLI/Data 포트 열기
- cfg 전송
- UART 바이트를 버퍼에 축적
- magic word 기준으로 프레임 분리
- `tlv_packet_parser.py` 호출
- `ParsedFrame`으로 정리해서 다음 모듈로 전달

쉽게 말하면 `실시간 입력 관리자`다.

### 4.3 `tlv_parse_runner.py`
이 파일은 기존 실행 명령과 import를 유지하기 위한 호환 래퍼다.

핵심 역할:

- `runtime_pipeline.py`의 `main`, `run_realtime`, `MMWaveSerialReader` 등을 다시 export
- 기존 `python src/parser/tlv_parse_runner.py ...` 명령을 계속 지원

즉 "실구현"은 아니고, `entrypoint compatibility layer`에 가깝다.

### 4.4 `src/runtime_params.py`
이 파일은 `config/runtime_params.json`을 읽어 공용 기본값을 만든다.

핵심 역할:

- runner/viewer 공용 기본 파라미터 정의
- `--params-file`로 JSON override 로딩
- 알 수 없는 키 검증

즉 반복 튜닝 값 관리 지점이다.

## 5. 데이터가 실제로 흐르는 순서

### 5.1 Step 1. 레이더가 바이트를 계속 보낸다
Data 포트에서는 사람이 읽기 어려운 binary byte stream이 계속 들어온다.

이 상태에서는 아직 "점"이 아니다.
그냥 숫자 바이트 조각이다.

### 5.2 Step 2. runner가 byte buffer에 모은다
`MMWaveSerialReader`는 들어온 바이트를 내부 버퍼에 계속 붙인다.

왜 버퍼가 필요하냐면,

- 한 번 읽을 때 프레임 전체가 안 들어올 수도 있고
- 프레임 두 개가 한 번에 붙어서 들어올 수도 있기 때문이다

즉 UART 데이터는 "예쁘게 한 프레임씩" 안 들어온다.

### 5.3 Step 3. magic word를 찾는다
`MAGIC_WORD = 02 01 04 03 06 05 08 07`

이 값은 "여기서부터 새 프레임 시작"이라는 표식이다.

파서는 이걸 찾아야 프레임 경계를 잡을 수 있다.

### 5.4 Step 4. header를 읽는다
header에서 중요한 값은 아래다.


이걸 먼저 읽어야 뒤에 TLV가 몇 개 있는지, 점이 몇 개인지 알 수 있다.

### 5.5 Step 5. TLV를 순서대로 읽는다
프레임 안에는 TLV가 여러 개 있을 수 있다.

현재 코드가 주요하게 읽는 건 2개다.

- `tlv_type == 1`: detected points
- `tlv_type == 7`: snr/noise

### 5.6 Step 6. 최종 point 구조로 넘긴다
현재 파서 출력은 아래 구조다.

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

이후 전처리, DBSCAN, Kalman이 이 값을 사용한다.

## 6. 코드 레벨에서 꼭 이해해야 할 함수

### 6.1 `parser_helper`
역할:

- magic word 위치 찾기
- header 값 추출

이 함수는 "이 프레임이 대충 어떤 프레임인지" 먼저 읽는 단계다.

### 6.2 `_parse_detected_points_tlv`
역할:

- 각 object point의 `x, y, z, v`를 읽음
- 추가로 `range`, `azimuth`, `elevation` 계산

여기서 가장 중요한 건 사실 `x, y, z, v`다.
나머지 각도 값은 부가 정보다.

### 6.3 `_parse_snr_noise_tlv`
역할:

- 각 점의 `snr`, `noise` 읽기

이 값은 뒤에서 filter와 품질 판단에 중요하다.

### 6.4 `parser_one_mmw_demo_output_packet`
역할:

- 한 개 패킷 전체를 파싱
- header 검증
- TLV 반복 해석
- 파싱 결과 반환

즉 `low-level parser의 핵심 함수`다.

### 6.5 `MMWaveSerialReader.read_frame`
역할:

- UART로부터 계속 읽기
- 버퍼에 누적
- 프레임 길이 확인
- 한 프레임만 잘라서 parser에 전달
- 성공하면 `ParsedFrame` 반환

현업에서는 이 함수를 매우 중요하게 본다.
이 부분이 `실시간성`, `프레임 복구`, `버퍼 안정성`을 좌우하기 때문이다.

## 7. 현업 관점에서 TLV 파서에 요구되는 성능
캡스톤이라도 이 수치 정도는 목표로 잡는 게 좋다.

### 7.1 기능 요구사항
- 실시간 프레임을 끊기지 않고 읽을 것
- magic word 기준으로 프레임 경계를 안정적으로 잡을 것
- 최소 `Type 1`, `Type 7`을 정확히 해석할 것
- 비정상 프레임이 와도 프로그램이 죽지 않을 것

### 7.2 성능 요구사항
- parser success rate `>= 99%`
- parser 평균 처리시간 `<= 10ms/frame`
- 전체 시스템 목표 FPS `>= 15`
- 10분 이상 연속 실행 중 크래시 `0회`

### 7.3 품질 요구사항
- frame number가 정상 증가하는지 확인 가능해야 함
- fail reason을 로그로 확인 가능해야 함
- corrupted frame 이후 정상 frame으로 복구 가능해야 함

## 8. 지금 코드가 하는 것과 아직 부족한 것

### 8.1 현재 코드가 이미 잘 하고 있는 것
- magic word 기반 frame sync가 있다
- UART byte buffer 구조가 있다
- `Detected Points`, `SNR/Noise`를 읽는다
- `range`, `snr`, `noise`까지 다음 단계에 전달한다
- 실시간 runner까지 연결되어 있다

즉, `완전 처음부터 만드는 단계는 이미 지났다`.
기본 구조는 있다.

### 8.2 아직 완전하다고 보기 어려운 이유
결론부터 말하면 `현재 코드는 MVP 수준이지, 완전한 production 수준은 아니다`.

이유는 아래와 같다.

#### 1. 테스트 코드가 없다
- sample packet 기반 unit test가 없다
- corrupted packet replay test가 없다
- frame gap test가 없다

즉 "보여서 돌아가는 것"과 "검증된 것"은 아직 다르다.

#### 2. 지원 TLV 타입이 제한적이다
- 현재 핵심은 `Type 1`, `Type 7`만 처리
- 다른 TLV가 중요해지면 확장 필요

#### 3. 파서 실패 원인 분류가 아직 약하다
- 어떤 이유로 fail 되었는지 세분화된 통계가 없다
- success/fail rate를 parser 전용 지표로 더 분리할 필요가 있다

#### 4. 성능 계측이 parser 전용으로 충분히 분리돼 있지 않다
- 전체 FPS는 보지만 parser 단독 latency 로그는 아직 약하다
- byte overflow, resync 횟수 같은 운영 지표가 필요하다

#### 5. 문서화와 재현성은 이제 갖추는 단계다
- 이번 문서 추가로 이해도는 좋아지지만
- 실제 검증 CSV와 replay fixture는 더 필요하다

## 9. 이번 확인에서 발견된 실제 이슈
이번에 코드를 직접 확인하면서, 아래 내용은 `추측`이 아니라 실제로 확인된 문제 또는 제한사항이다.

### 9.1 직접 스크립트 실행 경로 이슈
기존에는 README 스타일인

```bash
python src/parser/tlv_parse_runner.py --help
```

실행이 import 문제로 깨질 수 있었다.

이번 작업에서 runner가 `src` 경로를 보강하도록 수정해서, 직접 실행도 가능하게 정리했다.

### 9.2 malformed TLV를 정상 프레임처럼 넘길 가능성
기존 코드는 TLV 길이가 이상하면 loop를 `break`만 하고, 결과를 `PASS`로 돌려줄 가능성이 있었다.

이번 작업에서 아래 상황은 `FAIL`로 처리되도록 보강했다.

- TLV header가 덜 들어온 경우
- TLV length가 비정상인 경우
- TLV 내부 unpack에서 예외가 나는 경우

이건 실시간 시스템에서 중요하다.
이상 프레임을 성공으로 처리하면 뒤 단계가 더 크게 무너진다.

### 9.3 각도 계산 보정
기존 azimuth 계산은 `atan(x / y)` 형태라 사분면 정보가 틀어질 수 있었다.

이번 작업에서 `atan2` 기반으로 바꿔서 더 자연스럽게 보정했다.

참고:
현재 프로젝트 핵심은 `x, y, z, v`와 `range/snr/noise`라서 각도가 1순위는 아니지만, 계산식은 맞는 쪽이 낫다.

### 9.4 `num_det_obj > 0`인데 `Type 1`이 없는 프레임 fail 처리
실시간 parser에서는 `header만 그럴듯하고 핵심 payload가 없는 프레임`을 성공으로 넘기면 안 된다.

이번 작업에서 아래 조건은 `FAIL`로 본다.

- `num_det_obj > 0`
- 그런데 TLV loop 안에서 `Type 1` detected points payload를 한 번도 못 찾음

이렇게 한 이유는 간단하다.

- 이 프레임은 뒤 단계가 실제 좌표를 만들 수 없는 프레임이다.
- 그런데 성공으로 넘기면 filter/DBSCAN/Kalman이 `이상한 0값 point`를 정상처럼 받을 수 있다.

즉 이건 "몇 번 연속 안 오면 fail"보다 `프레임 단위에서 즉시 fail`이 맞다.

### 9.5 cfg 전송 응답 로그 추가
이전에는 runner가 cfg 파일을 CLI 포트로 보내기만 하고, 보드가 `Done`인지 `Error`인지 콘솔에서 바로 확인하기 어려웠다.

이번 작업에서 실행 시작 시 아래 로그를 볼 수 있다.

```text
[CFG] >> profileCfg ...
[CFG] << Done
```

그리고 `Error`, `Fail` 응답이 오면 즉시 예외를 올려서 bring-up 문제를 빨리 찾을 수 있게 했다.

## 10. TLV 담당자가 지금부터 공부할 순서
처음부터 SDK 전체를 다 보려 하지 말고, 아래 순서로 가는 게 좋다.

### 10.1 1단계: 바이트 구조 이해
먼저 아래 개념만 확실히 이해하면 된다.

- little-endian
- magic word
- header
- TLV type / length / value
- float 4개를 `struct.unpack_from('<ffff', ...)`로 읽는 방식

이 단계 목표:
`"바이트가 왜 x, y, z, v로 바뀌는지"`를 설명할 수 있어야 한다.

### 10.2 2단계: 현재 코드 한 줄씩 따라가기
아래 순서로 보면 된다.

1. `MMWaveSerialReader.read_frame`
2. `parser_helper`
3. `parser_one_mmw_demo_output_packet`
4. `_parse_detected_points_tlv`
5. `_parse_snr_noise_tlv`

이 단계 목표:
`"프레임 1개가 들어오면 어떤 함수들을 지나가는지"` 말할 수 있어야 한다.

### 10.3 3단계: 디버그 출력으로 frame 확인
실제로는 눈으로 보는 게 가장 빠르다.

권장:

- frame number 출력
- num_obj 출력
- 첫 3개 point 출력
- fail 횟수 출력

이 단계 목표:
`"지금 프레임이 정상인지 비정상인지 로그만 보고 감이 오는 상태"`가 되는 것

### 10.4 4단계: 실패 케이스 공부
현업에서는 정상 케이스보다 실패 케이스를 더 중요하게 본다.

꼭 봐야 하는 실패 케이스:

- magic word를 못 찾는 경우
- packet length가 이상한 경우
- SNR TLV가 없는 경우
- point 수와 실제 payload 길이가 안 맞는 경우
- `num_det_obj > 0`인데 `Type 1` payload가 없는 경우
- 프레임이 중간에 잘린 경우

### 10.5 5단계: 성능 수치 남기기
파싱 담당자는 "코드만 짰다"로 끝나면 안 된다.

최소한 아래는 남겨야 한다.

- 평균 parser latency
- parser success rate
- fail count
- resync count
- dropped frame count

## 11. TLV 담당자의 개발 우선순위
너가 이번 달 안에 현실적으로 먼저 해야 할 일 순서를 정리하면 이렇다.

### Priority 1. 정상 프레임 안정 파싱
- live data에서 끊기지 않고 frame이 올라오는지 확인
- `frame_number`, `num_obj`가 정상인지 확인

### Priority 2. 실패 프레임 안전 처리
- 이상 패킷이 와도 크래시하지 않도록 만들기
- fail reason과 fail count 남기기

### Priority 3. 성능 계측
- parser 처리시간 측정
- success rate 측정
- 10분 연속 실행 로그 남기기

### Priority 4. 재현 가능한 테스트
- raw byte sample 저장
- good/bad packet fixture 만들기
- parser 단위 테스트 만들기

## 12. TLV 담당자가 만들어야 할 증거 자료
취업과 캡스톤 둘 다 생각하면 아래를 남겨야 한다.

### 필수
- `evidence/parser_benchmark.csv`
- 정상 프레임 로그 캡처
- 비정상 프레임 복구 로그 캡처
- 10분 연속 실행 결과

### 있으면 강한 것
- raw packet sample
- good packet / bad packet 테스트 fixture
- parser latency 그래프
- frame drop 분석 표

## 13. 네가 면접에서 설명할 수 있어야 하는 말
아래 문장을 자기 말로 설명할 수 있으면 좋다.

1. `TLV parser는 레이더 binary stream을 객체 점 정보로 변환하는 센서 인터페이스 계층이다.`
2. `파싱 정확도뿐 아니라 resync와 fail-safe가 중요하다.`
3. `나는 frame sync, header/TLV 해석, 오류 처리, 성능 계측을 담당했다.`
4. `뒤 단계 DBSCAN/Kalman 성능도 결국 parser 품질에 영향을 받는다.`

## 14. 지금 당장 추천하는 실행/확인 방법

### 실행 확인
현재 공식 실행 명령은 아래 wrapper entrypoint다.

```bash
python src/parser/tlv_parse_runner.py --help
```

실제로 호출되는 구현은 `src/parser/runtime_pipeline.py` 쪽이다.

반복 튜닝 값은 `config/runtime_params.json`에서 먼저 조정하고, 실험용 override만 CLI로 주는 흐름을 권장한다.

### 개발 중 확인할 로그
- `frame_number`
- `num_obj`
- `raw bytes read`
- `parse fail count`
- `resync count`
- `parser latency`

## 15. 한 줄 결론
TLV 파싱은 "맨 앞단 입력 처리"라서 쉬워 보이지만, 실제로는 `실시간성 + 안정성 + 오류 복구`를 동시에 요구하는 중요한 모듈이다.

현재 코드에는 기본 구조가 이미 있고, 이번 수정으로 실행성과 일부 오류 처리를 보강했다.
하지만 테스트, 계측, 실패 원인 분류, fixture 기반 검증이 아직 부족하므로 `완전한 상태`라고 보기는 어렵다.

너는 지금부터 `정상 파싱 -> 실패 복구 -> 성능 수치화 -> 테스트 자동화` 순서로 발전시키면 된다.
