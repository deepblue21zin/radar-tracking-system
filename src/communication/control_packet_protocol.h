#ifndef CONTROL_PACKET_PROTOCOL_H
#define CONTROL_PACKET_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define CONTROL_PACKET_HEADER0 0xAAu
#define CONTROL_PACKET_HEADER1 0x55u
#define CONTROL_PACKET_SIZE 12u
#define CONTROL_PACKET_PAYLOAD_SIZE 9u
#define CONTROL_DISTANCE_UNAVAILABLE_CM 0xFFFFu

typedef enum {
    CONTROL_CMD_STOP = 0,
    CONTROL_CMD_SLOW = 1,
    CONTROL_CMD_RESUME = 2,
    CONTROL_CMD_ALARM = 3
} control_command_t;

typedef enum {
    CONTROL_EVENT_CLEAR = 0,
    CONTROL_EVENT_OBJECT_APPROACHING = 1,
    CONTROL_EVENT_OBJECT_IN_ZONE = 2,
    CONTROL_EVENT_OBJECT_STOPPED = 3,
    CONTROL_EVENT_EMERGENCY_STOP = 4
} control_event_t;

enum {
    CONTROL_FLAG_INSIDE_ZONE = 1u << 0,
    CONTROL_FLAG_APPROACHING = 1u << 1,
    CONTROL_FLAG_STATE_CHANGED = 1u << 2
};

typedef struct {
    uint8_t sequence;
    uint8_t command;
    uint8_t speed_ratio_pct;
    uint8_t event;
    uint8_t flags;
    uint16_t zone_distance_cm;
    int16_t closing_speed_cms;
} control_packet_t;

typedef struct {
    uint8_t state;
    uint8_t payload_and_crc[CONTROL_PACKET_PAYLOAD_SIZE + 1u];
    uint8_t index;
    uint32_t packets_ok;
    uint32_t crc_failures;
    uint32_t sync_losses;
} control_packet_parser_t;

uint8_t control_crc8(const uint8_t *data, size_t len);
void control_packet_parser_init(control_packet_parser_t *parser);
int control_packet_parser_consume(control_packet_parser_t *parser, uint8_t byte, control_packet_t *out_packet);

#endif
