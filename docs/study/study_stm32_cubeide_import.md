# STM32CubeIDE Import Note

## 1. 목적
이 문서는 현재 프로젝트의 STM32 예제 코드를
`STM32CubeIDE` 프로젝트에 가져오는 최소 절차를 정리한 메모이다.

대상 파일:

- `src/communication/control_packet_protocol.h`
- `src/communication/stm32_control_rx_example.h`
- `src/communication/stm32_control_rx_example.c`

---

## 2. 이 파일들의 역할

### 2.1 `control_packet_protocol.h`
Python과 STM32가 공통으로 이해하는 제어 패킷 형식을 정의한다.

포함 내용:

- command enum
- event enum
- packet struct
- parser state struct
- CRC / parser function prototype

### 2.2 `stm32_control_rx_example.h`
`main.c`에서 직접 include하기 위한 공개 헤더이다.

포함 내용:

- `conveyor_control_state_t`
- `conveyor_control_init()`
- `conveyor_control_on_packet()`
- `conveyor_control_periodic()`
- motor output hook prototype

### 2.3 `stm32_control_rx_example.c`
실제 수신/파싱/속도 갱신 로직 구현 파일이다.

현재 포함 기능:

- CRC8
- packet parser
- target speed update
- timeout fail-safe
- simple ramp

---

## 3. CubeIDE에 넣는 방법

### 3.1 새 프로젝트 생성
`STM32CubeIDE`에서

- board 기반
- 또는 MCU 기반

으로 새 프로젝트를 만든다.

### 3.2 `.ioc`에서 최소 설정
적어도 아래는 켜야 한다.

- `USARTx` 1개
  - Asynchronous
  - `115200`, `8-N-1`
- UART RX interrupt
- 10 ms 주기 호출용 timer 또는 `SysTick`

TB6600 기준으로는 나중에 아래도 필요하다.

- `DIR` GPIO output
- `ENA` GPIO output
- `STEP` pulse용 timer channel

### 3.3 파일 복사 위치
아래처럼 넣는 것을 권장한다.

- `control_packet_protocol.h` -> `Core/Inc`
- `stm32_control_rx_example.h` -> `Core/Inc`
- `stm32_control_rx_example.c` -> `Core/Src`

그 다음 `Project -> Refresh` 후 빌드한다.

---

## 4. `main.c` 연결 예시

아래 코드는 `huart1`를 사용한다고 가정한 예시이다.
실제 UART 이름은 네 프로젝트에서 생성된 이름으로 바꿔야 한다.

```c
#include "main.h"
#include "stm32_control_rx_example.h"

static control_packet_parser_t g_parser;
static conveyor_control_state_t g_conveyor;
static control_packet_t g_packet;
static uint8_t g_rx_byte;

static void app_control_init(void)
{
    control_packet_parser_init(&g_parser);
    conveyor_control_init(&g_conveyor);
    HAL_UART_Receive_IT(&huart1, &g_rx_byte, 1);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart == &huart1) {
        if (control_packet_parser_consume(&g_parser, g_rx_byte, &g_packet)) {
            conveyor_control_on_packet(&g_conveyor, &g_packet, HAL_GetTick());
        }
        HAL_UART_Receive_IT(&huart1, &g_rx_byte, 1);
    }
}

static void app_control_tick_10ms(void)
{
    conveyor_control_periodic(&g_conveyor, HAL_GetTick(), 300u);
}
```

`main()` 안에서는 초기화 후 `app_control_init()`를 호출하면 된다.

예:

```c
int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART1_UART_Init();
    MX_TIM2_Init();

    app_control_init();

    while (1) {
        /* main loop */
    }
}
```

10 ms 주기 호출은 아래 둘 중 하나로 처리하면 된다.

- `SysTick` 기반 software tick
- timer interrupt callback

---

## 5. 꼭 직접 채워야 하는 부분

현재 예제 코드에서 아래 두 함수는 약한 기본 구현(weak stub)만 있다.

- `conveyor_motor_apply_speed_pct()`
- `conveyor_motor_stop_immediate()`

즉 실제 보드에선 별도 파일에서 이 함수를 override해서 써야 한다.

예:

```c
#include "stm32_control_rx_example.h"

void conveyor_motor_apply_speed_pct(uint8_t speed_pct)
{
    /* speed_pct -> TB6600 STEP 주파수 변환 */
}

void conveyor_motor_stop_immediate(void)
{
    /* STEP timer off, ENA safe state */
}
```

---

## 6. TB6600 기준으로 생각할 것

TB6600을 쓸 계획이면 STM32 출력 방식은 거의 아래처럼 정리된다.

- `STEP`: timer pulse frequency
- `DIR`: direction GPIO
- `ENA`: enable GPIO

즉 `speed_pct`는 보통 PWM duty가 아니라
`STEP pulse frequency`로 바꾸는 구조가 된다.

예시 개념:

- `0%` -> pulse off
- `40%` -> 중간 주파수
- `100%` -> 기준 최대 주파수

---

## 7. 현재 상태 한 줄 정리

현재 추가된 STM32 코드는

- CubeIDE에 가져갈 수 있는 수신/파싱/제어 뼈대는 있음
- 하지만 실제 UART 핸들, timer, TB6600 출력 코드는 사용자가 보드 기준으로 연결해야 함

