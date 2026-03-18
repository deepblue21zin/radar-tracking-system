"""Shared control packet encoding for Python host -> STM32 conveyor control."""

from __future__ import annotations

from dataclasses import dataclass
import struct
import time
from typing import Optional

import serial


PACKET_HEADER = b"\xAA\x55"
PACKET_SIZE = 12
DISTANCE_UNAVAILABLE_CM = 0xFFFF

CMD_STOP = 0
CMD_SLOW = 1
CMD_RESUME = 2
CMD_ALARM = 3

EVENT_CLEAR = 0
EVENT_OBJECT_APPROACHING = 1
EVENT_OBJECT_IN_ZONE = 2
EVENT_OBJECT_STOPPED = 3
EVENT_EMERGENCY_STOP = 4

FLAG_INSIDE_ZONE = 1 << 0
FLAG_APPROACHING = 1 << 1
FLAG_STATE_CHANGED = 1 << 2


def crc8(data: bytes, polynomial: int = 0x07, init: int = 0x00) -> int:
    crc = init & 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def command_to_code(command: str) -> int:
    command_map = {
        "STOP": CMD_STOP,
        "SLOW": CMD_SLOW,
        "RESUME": CMD_RESUME,
        "ALARM": CMD_ALARM,
    }
    return command_map.get(str(command).upper(), CMD_STOP)


def event_to_code(event: str) -> int:
    event_map = {
        "CLEAR": EVENT_CLEAR,
        "OBJECT_APPROACHING": EVENT_OBJECT_APPROACHING,
        "OBJECT_IN_ZONE": EVENT_OBJECT_IN_ZONE,
        "OBJECT_STOPPED": EVENT_OBJECT_STOPPED,
        "EMERGENCY_STOP": EVENT_EMERGENCY_STOP,
    }
    return event_map.get(str(event).upper(), EVENT_CLEAR)


def _clamp_uint8(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _clamp_int16(value: float) -> int:
    rounded = int(round(value))
    return max(-32768, min(32767, rounded))


@dataclass
class EncodedControlPacket:
    packet: bytes
    sequence: int
    command_code: int
    event_code: int
    speed_ratio_pct: int
    flags: int
    zone_distance_cm: int
    closing_speed_cms: int


def build_control_packet(decision: object, sequence: int) -> EncodedControlPacket:
    speed_ratio = float(getattr(decision, "speed_ratio", 0.0))
    speed_ratio_pct = _clamp_uint8(speed_ratio * 100.0)

    zone_distance_m = getattr(decision, "zone_distance_m", None)
    if zone_distance_m is None:
        zone_distance_cm = DISTANCE_UNAVAILABLE_CM
    else:
        zone_distance_cm = max(0, min(DISTANCE_UNAVAILABLE_CM - 1, int(round(float(zone_distance_m) * 100.0))))

    closing_speed_mps = getattr(decision, "closing_speed_mps", 0.0)
    closing_speed_cms = _clamp_int16(float(closing_speed_mps) * 100.0)

    flags = 0
    if bool(getattr(decision, "inside_zone", False)):
        flags |= FLAG_INSIDE_ZONE
    if bool(getattr(decision, "approaching", False)):
        flags |= FLAG_APPROACHING
    if bool(getattr(decision, "changed", False)):
        flags |= FLAG_STATE_CHANGED

    command_code = command_to_code(str(getattr(decision, "command", "STOP")))
    event_code = event_to_code(str(getattr(decision, "primary_event", "CLEAR")))
    seq_u8 = sequence & 0xFF

    payload = struct.pack(
        "<BBBBBHh",
        seq_u8,
        command_code,
        speed_ratio_pct,
        event_code,
        flags,
        zone_distance_cm,
        closing_speed_cms,
    )
    packet_without_crc = PACKET_HEADER + payload
    packet_crc = crc8(payload)
    packet = packet_without_crc + bytes([packet_crc])

    return EncodedControlPacket(
        packet=packet,
        sequence=seq_u8,
        command_code=command_code,
        event_code=event_code,
        speed_ratio_pct=speed_ratio_pct,
        flags=flags,
        zone_distance_cm=zone_distance_cm,
        closing_speed_cms=closing_speed_cms,
    )


class ControlPacketSerialWriter:
    """Transmit control packets to an MCU at decision changes and heartbeat intervals."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 0.05,
        heartbeat_interval_ms: int = 200,
    ):
        if heartbeat_interval_ms < 0:
            raise ValueError("heartbeat_interval_ms must be >= 0")
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.sequence = 0
        self._last_send_monotonic: Optional[float] = None
        self._serial = serial.Serial(port, baudrate, timeout=timeout)

    def should_send(self, decision: object) -> bool:
        if bool(getattr(decision, "changed", False)):
            return True
        if self._last_send_monotonic is None:
            return True
        if self.heartbeat_interval_ms == 0:
            return True
        elapsed_ms = (time.monotonic() - self._last_send_monotonic) * 1000.0
        return elapsed_ms >= self.heartbeat_interval_ms

    def send_decision(self, decision: object) -> Optional[EncodedControlPacket]:
        if not self.should_send(decision):
            return None

        encoded = build_control_packet(decision, self.sequence)
        self._serial.write(encoded.packet)
        self._serial.flush()

        self.sequence = (self.sequence + 1) & 0xFF
        self._last_send_monotonic = time.monotonic()
        return encoded

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
