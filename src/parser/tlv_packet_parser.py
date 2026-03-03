"""Low-level TLV packet parser for TI mmWave UART output.

Adapted for real-time use from TI mmWave SDK parser examples.
"""

import math
import struct
from typing import List, Tuple

TC_PASS = 0
TC_FAIL = 1

HEADER_NUM_BYTES = 40
MAGIC_WORD = bytes([2, 1, 4, 3, 6, 5, 8, 7])


def get_uint32(data: bytes) -> int:
    return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)


def get_uint16(data: bytes) -> int:
    return data[0] | (data[1] << 8)


def check_magic_pattern(data: bytes) -> bool:
    return len(data) >= 8 and data[:8] == MAGIC_WORD


def parser_helper(data: bytes, read_num_bytes: int, debug: bool = False):
    header_start_index = data.find(MAGIC_WORD, 0, read_num_bytes)

    if header_start_index == -1:
        total_packet_num_bytes = -1
        frame_number = -1
        num_det_obj = -1
        num_tlv = -1
        sub_frame_number = -1
    else:
        total_packet_num_bytes = get_uint32(data[header_start_index + 12:header_start_index + 16])
        frame_number = get_uint32(data[header_start_index + 20:header_start_index + 24])
        num_det_obj = get_uint32(data[header_start_index + 28:header_start_index + 32])
        num_tlv = get_uint32(data[header_start_index + 32:header_start_index + 36])
        sub_frame_number = get_uint32(data[header_start_index + 36:header_start_index + 40])

    if debug:
        print(f"headerStartIndex={header_start_index}")
        print(f"totalPacketNumBytes={total_packet_num_bytes}")
        print(f"frameNumber={frame_number}")
        print(f"numDetObj={num_det_obj}")
        print(f"numTlv={num_tlv}")
        print(f"subFrameNumber={sub_frame_number}")

    return (
        header_start_index,
        total_packet_num_bytes,
        frame_number,
        num_det_obj,
        num_tlv,
        sub_frame_number,
    )


def _parse_detected_points_tlv(
    data: bytes, tlv_start: int, num_det_obj: int
) -> Tuple[List[float], List[float], List[float], List[float], List[float], List[float], List[float]]:
    detected_x_array: List[float] = []
    detected_y_array: List[float] = []
    detected_z_array: List[float] = []
    detected_v_array: List[float] = []
    detected_range_array: List[float] = []
    detected_azimuth_array: List[float] = []
    detected_elev_angle_array: List[float] = []

    offset = 8
    for _ in range(num_det_obj):
        x, y, z, v = struct.unpack_from('<ffff', data, tlv_start + offset)
        comp_detected_range = math.sqrt((x * x) + (y * y) + (z * z))

        if y == 0:
            detected_azimuth = 90.0 if x >= 0 else -90.0
        else:
            detected_azimuth = math.degrees(math.atan(x / y))

        if x == 0 and y == 0:
            detected_elev_angle = 90.0 if z >= 0 else -90.0
        else:
            detected_elev_angle = math.degrees(math.atan(z / math.sqrt((x * x) + (y * y))))

        detected_x_array.append(x)
        detected_y_array.append(y)
        detected_z_array.append(z)
        detected_v_array.append(v)
        detected_range_array.append(comp_detected_range)
        detected_azimuth_array.append(detected_azimuth)
        detected_elev_angle_array.append(detected_elev_angle)

        offset += 16

    return (
        detected_x_array,
        detected_y_array,
        detected_z_array,
        detected_v_array,
        detected_range_array,
        detected_azimuth_array,
        detected_elev_angle_array,
    )


def _parse_snr_noise_tlv(data: bytes, tlv_start: int, num_det_obj: int) -> Tuple[List[int], List[int]]:
    detected_snr_array: List[int] = []
    detected_noise_array: List[int] = []

    offset = 8
    for _ in range(num_det_obj):
        snr = get_uint16(data[tlv_start + offset:tlv_start + offset + 2])
        noise = get_uint16(data[tlv_start + offset + 2:tlv_start + offset + 4])
        detected_snr_array.append(snr)
        detected_noise_array.append(noise)
        offset += 4

    return detected_snr_array, detected_noise_array


def parser_one_mmw_demo_output_packet(data: bytes, read_num_bytes: int, debug: bool = False):
    detected_x_array: List[float] = []
    detected_y_array: List[float] = []
    detected_z_array: List[float] = []
    detected_v_array: List[float] = []
    detected_range_array: List[float] = []
    detected_azimuth_array: List[float] = []
    detected_elev_angle_array: List[float] = []
    detected_snr_array: List[int] = []
    detected_noise_array: List[int] = []

    result = TC_PASS

    (
        header_start_index,
        total_packet_num_bytes,
        frame_number,
        num_det_obj,
        num_tlv,
        sub_frame_number,
    ) = parser_helper(data, read_num_bytes, debug)

    if header_start_index == -1:
        return (
            TC_FAIL,
            header_start_index,
            total_packet_num_bytes,
            frame_number,
            num_det_obj,
            num_tlv,
            sub_frame_number,
            detected_x_array,
            detected_y_array,
            detected_z_array,
            detected_v_array,
            detected_range_array,
            detected_azimuth_array,
            detected_elev_angle_array,
            detected_snr_array,
            detected_noise_array,
        )

    next_header_start_index = header_start_index + total_packet_num_bytes
    if header_start_index + total_packet_num_bytes > read_num_bytes:
        result = TC_FAIL
    elif next_header_start_index + 8 < read_num_bytes and not check_magic_pattern(
        data[next_header_start_index:next_header_start_index + 8]
    ):
        result = TC_FAIL
    elif num_det_obj < 0 or sub_frame_number > 3:
        result = TC_FAIL

    if result == TC_FAIL:
        return (
            result,
            header_start_index,
            total_packet_num_bytes,
            frame_number,
            num_det_obj,
            num_tlv,
            sub_frame_number,
            detected_x_array,
            detected_y_array,
            detected_z_array,
            detected_v_array,
            detected_range_array,
            detected_azimuth_array,
            detected_elev_angle_array,
            detected_snr_array,
            detected_noise_array,
        )

    tlv_start = header_start_index + HEADER_NUM_BYTES
    for _ in range(num_tlv):
        if tlv_start + 8 > read_num_bytes:
            break

        tlv_type = get_uint32(data[tlv_start + 0:tlv_start + 4])
        tlv_len = get_uint32(data[tlv_start + 4:tlv_start + 8])

        if tlv_len <= 0 or (tlv_start + 8 + tlv_len) > read_num_bytes:
            break

        if tlv_type == 1:
            (
                detected_x_array,
                detected_y_array,
                detected_z_array,
                detected_v_array,
                detected_range_array,
                detected_azimuth_array,
                detected_elev_angle_array,
            ) = _parse_detected_points_tlv(data, tlv_start, num_det_obj)
        elif tlv_type == 7:
            detected_snr_array, detected_noise_array = _parse_snr_noise_tlv(data, tlv_start, num_det_obj)

        tlv_start += 8 + tlv_len

    if len(detected_snr_array) < num_det_obj:
        detected_snr_array += [0] * (num_det_obj - len(detected_snr_array))
        detected_noise_array += [0] * (num_det_obj - len(detected_noise_array))

    return (
        result,
        header_start_index,
        total_packet_num_bytes,
        frame_number,
        num_det_obj,
        num_tlv,
        sub_frame_number,
        detected_x_array,
        detected_y_array,
        detected_z_array,
        detected_v_array,
        detected_range_array,
        detected_azimuth_array,
        detected_elev_angle_array,
        detected_snr_array,
        detected_noise_array,
    )
