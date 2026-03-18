# TLV Study Note

## 1. 이 문서는 왜 만들었나
이 문서는 `TLV 파싱을 처음 공부하는 사람`이 `개념 -> 코드 -> 실습` 순서로 차근차근 이해할 수 있도록 만든 공부용 노트다.

기존 [docs/TLV.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/TLV.md)가 개발 가이드에 가깝다면, 이 문서는 더 기초부터 설명하는 `스터디 문서`에 가깝다.

목표는 단순하다.

1. TLV 파싱이 왜 필요한지 이해한다.
2. 현재 코드가 실제로 어떻게 동작하는지 흐름을 잡는다.
3. 바이트가 어떻게 `x, y, z, v`로 바뀌는지 설명할 수 있게 된다.
4. 실패 케이스와 로그를 보고 원인을 추정할 수 있게 된다.

## 2. 먼저 큰 그림부터 잡자
이 프로젝트 전체 흐름은 아래와 같다.

`Radar UART -> TLV Parser -> Filter -> DBSCAN -> Kalman Tracker -> Control`

여기서 TLV 파서는 `센서가 보낸 생 바이트(raw bytes)`를 `의미 있는 점 데이터(point cloud)`로 바꾸는 역할을 한다.

즉 TLV 파싱이 끝나야 비로소 우리는 이런 데이터를 얻게 된다.

```python
{
    "x": [1.2, 1.4],
    "y": [0.3, 0.5],
    "z": [0.1, 0.0],
    "v": [-0.2, -0.1],
    "range": [1.24, 1.49],
    "snr": [18, 16],
    "noise": [3, 4],
}
```

즉 TLV 파싱은 "뒷단 알고리즘이 먹을 수 있는 형태로 바꿔주는 번역기"다.

## 3. TLV를 공부하기 전에 알아야 하는 기초

## 3.1 바이트(Byte)
컴퓨터에서 센서 데이터는 결국 `0과 1`로 오고, 보통 우리는 그것을 `바이트` 단위로 본다.

1바이트는 8비트다.

예시:

- `0x02`
- `0x01`
- `0x04`

이런 값이 계속 이어져서 한 프레임이 된다.

## 3.2 16진수(Hex)
센서 바이트를 볼 때는 보통 16진수로 본다.

예시:

- `0x00`
- `0x7B`
- `0xFF`

사람 눈으로 보기 편해서 그렇다.

## 3.3 little-endian
이건 아주 중요하다.

`little-endian`은 여러 바이트로 된 숫자를 저장할 때 `가장 작은 자리수 바이트를 앞에 두는 방식`이다.

예를 들어 `92`를 4바이트 정수로 저장하면:

```text
5C 00 00 00
```

왜냐하면 `0x5C = 92`이기 때문이다.

현재 코드의 `get_uint32()`는 바로 이 little-endian 규칙으로 4바이트를 정수로 바꾼다.  
[src/parser/tlv_packet_parser.py:17](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L17)

```python
def get_uint32(data: bytes) -> int:
    return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
```

즉:

- 첫 바이트는 그대로
- 두 번째 바이트는 8비트 왼쪽 이동
- 세 번째 바이트는 16비트 이동
- 네 번째 바이트는 24비트 이동

을 해서 하나의 숫자로 합친다.

## 3.4 float를 읽는 방식
점 데이터의 `x, y, z, v`는 정수가 아니라 `float`다.

그래서 현재 코드는 이렇게 읽는다.  
[src/parser/tlv_packet_parser.py:76](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L76)

```python
x, y, z, v = struct.unpack_from('<ffff', data, tlv_start + offset)
```

이 뜻은:

- `<` : little-endian
- `f` : 4바이트 float
- `ffff` : float 4개

즉 `x, y, z, v`를 한 번에 읽는다는 뜻이다.

## 4. TLV가 정확히 뭔가
TLV는 `Type-Length-Value`다.

예를 들어 센서가 보낸 데이터 안에 이런 정보가 있을 수 있다.

- 이 블록은 point 좌표 데이터다
- 이 블록은 snr/noise 데이터다
- 이 블록은 다른 보조 정보다

이걸 센서가 스스로 표시해 주는 방식이 TLV다.

구조는 이렇게 생각하면 된다.

```text
[Type 4바이트][Length 4바이트][Value ...]
```

즉 TLV 하나를 읽을 때는 항상:

1. `이 데이터가 무슨 종류인가?`
2. `길이가 몇 바이트인가?`
3. `그 길이만큼 실제 데이터를 읽자`

순서로 가면 된다.

## 5. 한 프레임의 전체 구조
현재 코드 기준으로 한 프레임은 대략 아래처럼 생긴다.

```text
[Magic Word 8B][Header 40B][TLV #1][TLV #2]...[TLV #N]
```

즉 프레임 전체는:

1. 시작 표식
2. 프레임 설명서(header)
3. 실제 데이터 묶음(TLV들)

으로 이루어진다.

## 6. Magic Word는 왜 필요한가

## 6.1 Magic Word의 의미
Magic Word는 프레임 시작을 알리는 `특수한 8바이트 패턴`이다.  
[src/parser/tlv_packet_parser.py:14](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L14)

```python
MAGIC_WORD = bytes([2, 1, 4, 3, 6, 5, 8, 7])
```

16진수로 쓰면:

```text
02 01 04 03 06 05 08 07
```

이 값을 보면 파서는:

`"아, 여기서부터 새 프레임이 시작되는구나"`

라고 판단한다.

## 6.2 왜 꼭 필요하냐
UART는 파일처럼 "한 줄씩" 주지 않는다.
그냥 바이트가 계속 흐른다.

예를 들면 실제로는 이런 느낌이다.

```text
AA 14 9C 02 01 04 03 06 05 08 07 ...
```

앞의 `AA 14 9C`는 이전 프레임 찌꺼기거나 쓸모없는 일부 데이터일 수 있다.
파서는 그걸 버리고 `02 01 04 03 06 05 08 07`부터 읽어야 한다.

## 6.3 현재 코드에서 어떻게 찾나
현재 코드는 버퍼 안에서 magic word를 찾는다.  
[src/parser/runtime_pipeline.py:346](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L346)

```python
start_idx = buffer_view.find(MAGIC_WORD)
```

결과는 이렇게 해석한다.

- `-1`: 못 찾음
- `0`: 버퍼 맨 앞에서 찾음
- `0보다 큰 값`: 앞에 쓸모없는 바이트가 있다는 뜻

## 6.4 못 찾았을 때 왜 마지막 7바이트만 남기나
현재 코드는 magic word를 못 찾으면 버퍼 대부분을 버리고 `마지막 7바이트`만 남긴다.  
[src/parser/runtime_pipeline.py:348](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L348)

이유는 magic word가 8바이트라서, 다음 read에서 앞부분이 이어질 수 있기 때문이다.

예를 들어:

이번 read:

```text
... 02 01 04 03 06
```

다음 read:

```text
05 08 07 ...
```

이렇게 쪼개져 들어올 수 있다.

그래서 마지막 7바이트를 남겨야 다음에 이어붙여서 다시 찾을 수 있다.

이게 바로 `resync`의 핵심 아이디어다.

## 7. 버퍼(Buffer)란 무엇인가

## 7.1 버퍼를 한 줄로 설명하면
버퍼는 `들어온 데이터를 잠깐 쌓아두는 대기 공간`이다.

## 7.2 왜 버퍼가 꼭 필요하냐
센서에서 한 프레임이 3000바이트라고 해도, serial read 1번에 3000바이트가 깔끔하게 오지 않을 수 있다.

예를 들면:

- 첫 번째 read: 700바이트
- 두 번째 read: 1200바이트
- 세 번째 read: 1100바이트

이렇게 나눠질 수 있다.

그래서 버퍼에 계속 쌓아두고,

- magic word를 찾고
- header를 읽고
- `total_packet_num_bytes`만큼 다 모였는지 확인한 다음
- 한 프레임만 잘라서 파싱해야 한다

## 7.3 현재 코드에서 버퍼는 어떻게 구현되나
현재 코드는 `bytearray`로 버퍼를 관리한다.  
[src/parser/runtime_pipeline.py:310](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L310)

```python
self.byte_buffer = bytearray(max_buffer_size)
self.byte_buffer_length = 0
```

새 데이터가 들어오면 `_append()`로 뒤에 붙이고,  
[src/parser/runtime_pipeline.py:315](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L315)

앞부분을 버릴 때는 `_shift_left()`로 왼쪽으로 민다.  
[src/parser/runtime_pipeline.py:330](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L330)

즉 버퍼는 `쌓기 -> 찾기 -> 잘라내기 -> 남은 것 유지` 반복 구조다.

## 8. Header는 무엇인가
Magic word 바로 뒤에는 40바이트 header가 온다.  
[src/parser/tlv_packet_parser.py:13](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L13)

```python
HEADER_NUM_BYTES = 40
```

Header는 프레임 자체를 설명하는 정보다.
쉽게 말하면 `이 프레임 사용설명서`다.

## 8.1 현재 코드가 읽는 핵심 header 값 5개
현재 코드가 직접 꺼내는 값은 아래다.  
[src/parser/tlv_packet_parser.py:39](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L39)

- `total_packet_num_bytes`
- `frame_number`
- `num_det_obj`
- `num_tlv`
- `sub_frame_number`

## 8.2 각 값의 뜻

### `total_packet_num_bytes`
이번 프레임 전체 길이다.

예:

- 값이 `92`이면, 현재 프레임은 총 92바이트다.

이 값이 중요한 이유:

- 버퍼에 92바이트가 다 쌓여야 파싱 가능
- 프레임 끝을 어디까지로 볼지 결정

### `frame_number`
프레임 번호다.

예:

- 121
- 122
- 123

처럼 증가하는 게 정상이다.

이 값으로 알 수 있는 것:

- 프레임이 빠졌는지
- 순서가 꼬였는지
- 대략 얼마나 연속적으로 들어오는지

### `num_det_obj`
검출된 점 개수다.

주의:

이건 보통 `사람 수`가 아니라 `detected point 수`에 더 가깝다.

예:

- 한 사람인데 `num_det_obj = 8`일 수 있음
- 두 사람인데 `num_det_obj = 15`일 수 있음

이 값이 중요한 이유:

- type 1에서 몇 개 point를 읽어야 하는지 결정
- type 7에서 snr/noise를 몇 개 읽어야 하는지 결정

### `num_tlv`
이번 프레임 안에 TLV 블록이 몇 개 있는지다.

예:

- `2`면 TLV가 2개 들어 있음

현재 프로젝트에서는 보통:

- TLV 하나는 point data
- TLV 하나는 snr/noise

형태로 자주 본다.

### `sub_frame_number`
subframe 번호다.

기본 실험에서는 보통 `0`인 경우가 많다.
여러 subframe/profile을 번갈아 쓰는 고급 설정에서 의미가 커진다.

## 8.3 현재 코드에서 header 오프셋
현재 코드는 header 내부의 특정 바이트 위치에서 값을 읽는다.  
[src/parser/tlv_packet_parser.py:39](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L39)

예를 들어:

- `header_start_index + 12 ~ 15`: `total_packet_num_bytes`
- `header_start_index + 20 ~ 23`: `frame_number`
- `header_start_index + 28 ~ 31`: `num_det_obj`
- `header_start_index + 32 ~ 35`: `num_tlv`
- `header_start_index + 36 ~ 39`: `sub_frame_number`

즉 "오프셋(offset)"은 `프레임 시작 기준 몇 바이트 떨어져 있는가`를 뜻한다.

## 9. TLV Type은 무엇인가
Type은 `이 TLV가 어떤 데이터인지`를 알려주는 번호다.

현재 코드 기준으로 핵심은 2개다.  
[src/parser/tlv_packet_parser.py:200](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L200)

### `TLV type == 1`
Detected points다.

즉 각 point의:

- `x`
- `y`
- `z`
- `v`

를 담고 있다.

현재 코드는 point 1개당 16바이트를 읽는다.

- float 4개
- `4 bytes * 4 = 16 bytes`

### `TLV type == 7`
SNR / Noise 데이터다.

즉 각 point의:

- `snr`
- `noise`

를 담고 있다.

현재 코드는 point 1개당 4바이트를 읽는다.

- uint16 2개
- `2 bytes * 2 = 4 bytes`

## 9.1 왜 하필 1과 7인가
현재 센서 출력 형식에서 `그 번호가 그 의미로 정해져 있기 때문`이다.

즉 우리 코드가 임의로 정한 값이 아니라, 센서가 "이 TLV는 type 1", "이 TLV는 type 7"이라고 보내는 것을 해석하는 것이다.

## 10. 현재 코드가 실제로 동작하는 순서

## 10.1 전체 흐름
실제 함수 호출 순서는 대략 아래와 같다.

```text
MMWaveSerialReader.read_frame
  -> 버퍼에 데이터 추가
  -> magic word 찾기
  -> frame 길이 확인
  -> packet 잘라내기
  -> parser_one_mmw_demo_output_packet
       -> parser_helper
       -> TLV 반복 해석
       -> _parse_detected_points_tlv
       -> _parse_snr_noise_tlv
  -> ParsedFrame 반환
```

## 10.2 `MMWaveSerialReader.read_frame`
이 함수는 실시간 처리의 중심이고, 현재 구현 위치는 `runtime_pipeline.py`다.  
[src/parser/runtime_pipeline.py:339](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L339)

하는 일:

1. UART에서 bytes를 읽음
2. 버퍼에 붙임
3. magic word를 찾음
4. packet 길이를 읽음
5. 한 프레임이 다 들어왔으면 잘라냄
6. parser에 넘김
7. 성공하면 `ParsedFrame` 반환

## 10.3 `parser_helper`
이 함수는 header 핵심값을 먼저 뽑아낸다.  
[src/parser/tlv_packet_parser.py:29](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L29)

즉 "이 프레임이 얼마나 크고, 점이 몇 개고, TLV가 몇 개인가"를 먼저 읽는다.

## 10.4 `parser_one_mmw_demo_output_packet`
이 함수는 한 패킷 전체를 파싱한다.  
[src/parser/tlv_packet_parser.py:122](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L122)

하는 일:

1. header 읽기
2. packet 길이 검증
3. TLV 개수만큼 반복
4. type 1이면 points 읽기
5. type 7이면 snr/noise 읽기
6. 최종 결과 반환

## 10.5 `_parse_detected_points_tlv`
type 1 TLV 안에서 point를 읽는다.  
[src/parser/tlv_packet_parser.py:63](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L63)

현재 코드는 각 point마다:

- `x`
- `y`
- `z`
- `v`

를 읽고, 추가로:

- `range`
- `azimuth`
- `elevation`

도 계산한다.

## 10.6 `_parse_snr_noise_tlv`
type 7 TLV 안에서 각 point의 `snr`, `noise`를 읽는다.  
[src/parser/tlv_packet_parser.py:107](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L107)

## 11. 바이트가 실제로 해석되는 예시
이 부분이 가장 중요하다.

## 11.1 가상의 예시 frame
아래는 설명을 위한 단순화된 예시다.

```text
[Magic Word]
02 01 04 03 06 05 08 07

[Header 일부]
.. .. .. .. 5C 00 00 00 .. .. .. .. 7B 00 00 00 .. .. .. .. 02 00 00 00 02 00 00 00 00 00 00 00
```

여기서 핵심 값은:

- `5C 00 00 00` -> `92` -> `total_packet_num_bytes`
- `7B 00 00 00` -> `123` -> `frame_number`
- `02 00 00 00` -> `2` -> `num_det_obj`
- `02 00 00 00` -> `2` -> `num_tlv`
- `00 00 00 00` -> `0` -> `sub_frame_number`

즉 우리는 이 프레임이:

- 총 길이 92바이트
- frame #123
- point 2개
- TLV 2개

라는 걸 알게 된다.

## 11.2 TLV #1 해석
가정:

```text
01 00 00 00   20 00 00 00   [payload 32 bytes]
```

의미:

- `01 00 00 00` -> type 1
- `20 00 00 00` -> length 32

현재 코드 기준으로 length는 payload 길이로 해석된다.

point가 2개면:

- point 1 = 16 bytes
- point 2 = 16 bytes

총 32 bytes가 맞다.

## 11.3 TLV #2 해석
가정:

```text
07 00 00 00   08 00 00 00   [payload 8 bytes]
```

의미:

- `07 00 00 00` -> type 7
- `08 00 00 00` -> length 8

point가 2개면:

- point 1 snr/noise = 4 bytes
- point 2 snr/noise = 4 bytes

총 8 bytes가 맞다.

## 11.4 최종 결과
이 프레임을 다 읽고 나면 최종적으로는:

```python
{
    "x": [..., ...],
    "y": [..., ...],
    "z": [..., ...],
    "v": [..., ...],
    "range": [..., ...],
    "snr": [..., ...],
    "noise": [..., ...],
}
```

형태가 만들어진다.

즉 TLV 파싱의 본질은:

`바이트 -> 숫자 -> point 배열`

변환이다.

## 12. 실패 케이스를 왜 먼저 공부해야 하나
현업에서는 정상 케이스보다 실패 케이스가 더 중요하다.
왜냐하면 정상 케이스는 누구나 보여줄 수 있지만, `깨졌을 때도 안 죽는 코드`가 진짜 중요하기 때문이다.

## 12.1 대표 실패 케이스

### 1. magic word를 못 찾음
원인:

- 중간에 프레임이 잘림
- 잡음 섞임
- 아직 데이터가 덜 들어옴

대응:

- 마지막 7바이트 유지
- 다음 read에서 다시 탐색

### 2. packet length가 이상함
원인:

- header 일부가 깨짐
- magic word를 잘못 잡음

대응:

- invalid packet으로 판단
- 한 바이트 밀고 다시 탐색

### 3. TLV length가 이상함
원인:

- TLV header 파손
- 데이터 중간 손실

대응:

- 현재 코드는 `FAIL` 처리하도록 보강돼 있다

### 4. `num_det_obj`와 실제 payload가 안 맞음
원인:

- object 수 정보가 깨졌거나
- payload가 덜 왔음

대응:

- unpack 예외 발생 시 fail 처리

### 5. SNR TLV가 없는 경우
원인:

- 해당 TLV가 안 오거나
- format이 다름

대응:

- 현재 코드는 부족한 만큼 0으로 채운다  
[src/parser/tlv_packet_parser.py:226](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L226)

## 13. 지금 코드에서 어떤 로그를 봐야 하나
현재는 디버그 로그와 런타임 로그를 함께 볼 수 있다.

## 13.1 디버그 로그
`--debug`를 켜면 header 관련 값이 출력된다.  
[src/parser/tlv_packet_parser.py:45](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/tlv_packet_parser.py#L45)

예:

- `headerStartIndex`
- `totalPacketNumBytes`
- `frameNumber`
- `numDetObj`
- `numTlv`
- `subFrameNumber`

## 13.2 런타임 프레임 로그
현재 실시간 실행 시 아래 형태 로그가 나온다.  
[src/parser/runtime_pipeline.py:555](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/src/parser/runtime_pipeline.py#L555)

```text
frame=123 packet=2848B raw=87 filtered=51 clusters=3 tracks=2 parser_ms=2.41 pipe_ms=7.88
```

여기서 TLV 담당자가 특히 봐야 할 것은:

- `frame`
- `packet`
- `raw`
- `parser_ms`

## 13.3 자동 CSV 로그
이제 실행할 때마다 CSV가 자동 저장된다.

- 프레임별 로그: `evidence/runtime_logs/frames_*.csv`
- 실행 요약: `evidence/runtime_logs/run_summary.csv`

즉 네가 나중에 `parser latency`, `dropped frame`, `resync count`를 정리할 때 아주 유용하다.

## 14. TLV 담당자가 공부할 순서

## 14.1 1단계: 바이트 구조 이해
먼저 아래만 잡으면 된다.

- byte
- hex
- little-endian
- uint16 / uint32
- float unpack

여기까지 이해하면:

`"4바이트 정수가 왜 92가 되는지"`  
`"16바이트가 왜 x, y, z, v가 되는지"`

설명할 수 있어야 한다.

## 14.2 2단계: 현재 코드 따라가기
추천 순서:

1. `MMWaveSerialReader.read_frame`
2. `parser_helper`
3. `parser_one_mmw_demo_output_packet`
4. `_parse_detected_points_tlv`
5. `_parse_snr_noise_tlv`

이때 중요한 질문:

- 프레임 시작은 어디서 찾지?
- 길이는 언제 확인하지?
- TLV는 어디서 반복문으로 도는지?
- 점은 어디서 읽는지?

## 14.3 3단계: 로그로 눈 익히기
다음 값을 보면 좋다.

- `frame_number`
- `packet_bytes`
- `num_obj`
- `num_tlv`
- `parser_latency_ms`
- `parse_failures`
- `resync_events`

## 14.4 4단계: 실패 케이스를 일부러 생각하기
머릿속으로라도 다음을 그려보면 좋다.

- magic word 앞에 쓰레기 바이트가 붙으면?
- packet이 반만 들어오면?
- TLV 길이가 너무 크면?
- `num_det_obj = 100`인데 payload는 16바이트밖에 없으면?

이걸 설명할 수 있으면 이해도가 급격히 올라간다.

## 14.5 5단계: 수치화하기
TLV 담당자는 "잘 돌아가요"에서 끝나면 안 된다.

최소한 남길 것:

- avg parser latency
- parse failure count
- resync count
- dropped frame estimate
- avg packet bytes

## 15. TLV 담당자가 이번 달에 실제로 해야 할 일

### Priority 1. 정상 프레임 안정 파싱
- frame number가 계속 증가하는지 보기
- packet size가 이상 없이 유지되는지 보기
- raw point가 꾸준히 나오는지 보기

### Priority 2. 실패 프레임 복구
- parse failure가 있어도 전체 실행이 이어지는지 보기
- resync가 발생해도 다시 정상 프레임으로 돌아오는지 보기

### Priority 3. 성능 계측
- 60초 / 10분 테스트
- parser latency 기록
- packet size 기록

### Priority 4. 재현 가능한 테스트
- sample raw bytes 저장
- 정상 packet fixture
- 비정상 packet fixture
- parser 단위 테스트

## 16. 네가 직접 해볼 수 있는 실습

## 실습 1. header 값 손으로 읽기
아래 값을 보고 숫자로 바꿔보자.

- `5C 00 00 00`
- `7B 00 00 00`
- `02 00 00 00`

정답:

- `92`
- `123`
- `2`

## 실습 2. 현재 코드에서 오프셋 찾기
`src/parser/tlv_packet_parser.py`에서:

- packet length는 몇 번째 바이트부터 읽는지
- frame number는 몇 번째 바이트부터 읽는지

직접 찾아보자.

## 실습 3. 실행만 먼저 해보기

```bash
python -m src.parser.tlv_parse_runner --help
```

또는:

```bash
python src/parser/tlv_parse_runner.py --help
```

## 실습 4. 실기기 실행 후 확인할 것
실행 후 아래를 확인한다.

- frame number가 증가하는가
- packet 크기가 어느 정도인가
- parser_ms가 어느 정도인가
- parse failure가 있는가

## 17. 자주 헷갈리는 포인트

### `num_det_obj`는 사람 수가 아니다
대부분 `point 수`에 더 가깝다.

### parser가 되면 tracking도 자동으로 잘 되는 건 아니다
parser는 입력 품질을 보장하는 단계이고, tracking 품질은 또 별개다.

### frame이 안 나오는 이유가 parser만의 문제는 아닐 수 있다
- COM 포트 문제
- cfg 문제
- UART baudrate 문제
- 센서 출력량 과다

도 원인이 될 수 있다.

## 18. 면접에서 이렇게 말하면 좋다

1. `TLV parser는 레이더 UART binary stream을 point cloud 데이터로 변환하는 계층이다.`
2. `핵심은 단순 해석이 아니라 frame sync, length validation, fail-safe, resync다.`
3. `나는 실시간성 관점에서 packet size, parser latency, dropped frame, resync를 계측했다.`
4. `parser 품질은 이후 DBSCAN과 tracking의 안정성에 직접적인 영향을 준다.`

## 19. 한 줄 요약
TLV 파싱은 그냥 바이트를 읽는 작업이 아니라,

`연속적으로 들어오는 센서 바이트 스트림에서 프레임을 찾아내고, 그것을 의미 있는 점 데이터로 안전하게 변환하는 작업`

이다.

이 문서를 기준으로 공부할 때는 아래 순서를 추천한다.

`바이트/엔디안 이해 -> magic word와 buffer 이해 -> header 이해 -> TLV type 이해 -> 현재 코드 추적 -> 로그와 실패 케이스 분석`
