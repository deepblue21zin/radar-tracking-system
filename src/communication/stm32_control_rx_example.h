#ifndef STM32_CONTROL_RX_EXAMPLE_H
#define STM32_CONTROL_RX_EXAMPLE_H

#include <stdint.h>

#include "control_packet_protocol.h"

#if defined(__GNUC__) || defined(__clang__)
#define STM32_CONTROL_WEAK __attribute__((weak))
#else
#define STM32_CONTROL_WEAK
#endif

typedef struct {
    uint8_t target_speed_pct;
    uint8_t applied_speed_pct;
    uint32_t last_packet_ms;
    uint32_t timeout_count;
} conveyor_control_state_t;

void conveyor_control_init(conveyor_control_state_t *state);
void conveyor_control_on_packet(
    conveyor_control_state_t *state,
    const control_packet_t *packet,
    uint32_t now_ms
);
void conveyor_control_periodic(
    conveyor_control_state_t *state,
    uint32_t now_ms,
    uint32_t timeout_ms
);

void conveyor_motor_apply_speed_pct(uint8_t speed_pct);
void conveyor_motor_stop_immediate(void);

#endif
