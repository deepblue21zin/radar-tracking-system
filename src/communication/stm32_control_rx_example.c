/* Example STM32-side receiver for Python control packets.
 *
 * Intended flow:
 * 1) Receive UART bytes from the Python host.
 * 2) Feed each byte into control_packet_parser_consume().
 * 3) When a full packet arrives, update target conveyor speed.
 * 4) Run conveyor_control_periodic() from a 10 ms timer tick.
 *
 * The actual motor driver calls are left as TODO hooks because each board uses
 * different timers / GPIOs / driver wiring (TB6600 STEP/DIR, PWM inverter, etc.).
 */

#include "control_packet_protocol.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint8_t target_speed_pct;
    uint8_t applied_speed_pct;
    uint32_t last_packet_ms;
    uint32_t timeout_count;
} conveyor_control_state_t;

static uint8_t read_u8(const uint8_t *buf, size_t index)
{
    return buf[index];
}

static uint16_t read_u16_le(const uint8_t *buf, size_t index)
{
    return (uint16_t)buf[index] | ((uint16_t)buf[index + 1u] << 8);
}

static int16_t read_i16_le(const uint8_t *buf, size_t index)
{
    return (int16_t)read_u16_le(buf, index);
}

uint8_t control_crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0u;
    size_t i;
    for (i = 0u; i < len; ++i) {
        uint8_t bit;
        crc ^= data[i];
        for (bit = 0u; bit < 8u; ++bit) {
            if ((crc & 0x80u) != 0u) {
                crc = (uint8_t)((crc << 1u) ^ 0x07u);
            } else {
                crc <<= 1u;
            }
        }
    }
    return crc;
}

void control_packet_parser_init(control_packet_parser_t *parser)
{
    if (parser == NULL) {
        return;
    }

    parser->state = 0u;
    parser->index = 0u;
    parser->packets_ok = 0u;
    parser->crc_failures = 0u;
    parser->sync_losses = 0u;
}

int control_packet_parser_consume(control_packet_parser_t *parser, uint8_t byte, control_packet_t *out_packet)
{
    uint8_t payload_crc;
    uint8_t computed_crc;

    if (parser == NULL || out_packet == NULL) {
        return 0;
    }

    switch (parser->state) {
    case 0u:
        if (byte == CONTROL_PACKET_HEADER0) {
            parser->state = 1u;
        }
        return 0;

    case 1u:
        if (byte == CONTROL_PACKET_HEADER1) {
            parser->state = 2u;
            parser->index = 0u;
            return 0;
        }
        parser->state = (byte == CONTROL_PACKET_HEADER0) ? 1u : 0u;
        parser->sync_losses += 1u;
        return 0;

    default:
        parser->payload_and_crc[parser->index] = byte;
        parser->index += 1u;

        if (parser->index < (CONTROL_PACKET_PAYLOAD_SIZE + 1u)) {
            return 0;
        }

        payload_crc = parser->payload_and_crc[CONTROL_PACKET_PAYLOAD_SIZE];
        computed_crc = control_crc8(parser->payload_and_crc, CONTROL_PACKET_PAYLOAD_SIZE);

        parser->state = 0u;
        parser->index = 0u;

        if (payload_crc != computed_crc) {
            parser->crc_failures += 1u;
            return 0;
        }

        out_packet->sequence = read_u8(parser->payload_and_crc, 0u);
        out_packet->command = read_u8(parser->payload_and_crc, 1u);
        out_packet->speed_ratio_pct = read_u8(parser->payload_and_crc, 2u);
        out_packet->event = read_u8(parser->payload_and_crc, 3u);
        out_packet->flags = read_u8(parser->payload_and_crc, 4u);
        out_packet->zone_distance_cm = read_u16_le(parser->payload_and_crc, 5u);
        out_packet->closing_speed_cms = read_i16_le(parser->payload_and_crc, 7u);
        parser->packets_ok += 1u;
        return 1;
    }
}

static uint8_t clamp_speed_pct(uint8_t speed_pct)
{
    return (speed_pct > 100u) ? 100u : speed_pct;
}

static void conveyor_motor_apply_speed_pct(uint8_t speed_pct)
{
    (void)speed_pct;
    /* TODO:
     * - TB6600 direct drive: convert speed_pct to STEP pulse frequency.
     * - PWM/VFD drive: convert speed_pct to PWM duty or DAC voltage.
     */
}

static void conveyor_motor_stop_immediate(void)
{
    /* TODO:
     * - Disable STEP timer output and/or drive ENA to safe state.
     * - For VFD/PWM, force zero output and assert brake if used.
     */
}

void conveyor_control_init(conveyor_control_state_t *state)
{
    if (state == NULL) {
        return;
    }

    state->target_speed_pct = 0u;
    state->applied_speed_pct = 0u;
    state->last_packet_ms = 0u;
    state->timeout_count = 0u;
}

void conveyor_control_on_packet(
    conveyor_control_state_t *state,
    const control_packet_t *packet,
    uint32_t now_ms
)
{
    if (state == NULL || packet == NULL) {
        return;
    }

    state->last_packet_ms = now_ms;

    switch (packet->command) {
    case CONTROL_CMD_STOP:
        state->target_speed_pct = 0u;
        break;

    case CONTROL_CMD_SLOW:
        state->target_speed_pct = clamp_speed_pct(packet->speed_ratio_pct);
        break;

    case CONTROL_CMD_RESUME:
        state->target_speed_pct = 100u;
        break;

    case CONTROL_CMD_ALARM:
    default:
        state->target_speed_pct = 0u;
        break;
    }

    if (packet->event == CONTROL_EVENT_EMERGENCY_STOP) {
        state->target_speed_pct = 0u;
        state->applied_speed_pct = 0u;
        conveyor_motor_stop_immediate();
    }
}

void conveyor_control_periodic(
    conveyor_control_state_t *state,
    uint32_t now_ms,
    uint32_t timeout_ms
)
{
    if (state == NULL) {
        return;
    }

    if ((now_ms - state->last_packet_ms) > timeout_ms) {
        if (state->target_speed_pct != 0u || state->applied_speed_pct != 0u) {
            state->timeout_count += 1u;
        }
        state->target_speed_pct = 0u;
    }

    if (state->applied_speed_pct < state->target_speed_pct) {
        state->applied_speed_pct += 1u;
    } else if (state->applied_speed_pct > state->target_speed_pct) {
        state->applied_speed_pct -= 1u;
    }

    if (state->applied_speed_pct == 0u) {
        conveyor_motor_stop_immediate();
    } else {
        conveyor_motor_apply_speed_pct(state->applied_speed_pct);
    }
}

/* Example HAL-style usage:
 *
 * static control_packet_parser_t g_parser;
 * static conveyor_control_state_t g_conveyor;
 * static control_packet_t g_packet;
 * static uint8_t g_rx_byte;
 *
 * void app_init(void)
 * {
 *     control_packet_parser_init(&g_parser);
 *     conveyor_control_init(&g_conveyor);
 *     HAL_UART_Receive_IT(&huart1, &g_rx_byte, 1);
 * }
 *
 * void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
 * {
 *     if (huart == &huart1) {
 *         if (control_packet_parser_consume(&g_parser, g_rx_byte, &g_packet)) {
 *             conveyor_control_on_packet(&g_conveyor, &g_packet, HAL_GetTick());
 *         }
 *         HAL_UART_Receive_IT(&huart1, &g_rx_byte, 1);
 *     }
 * }
 *
 * void app_10ms_tick(void)
 * {
 *     conveyor_control_periodic(&g_conveyor, HAL_GetTick(), 300u);
 * }
 */
