"""Real-time UART reader for IWR6843 TLV point-cloud frames."""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import serial

try:
    from .tlv_packet_parser import MAGIC_WORD, parser_one_mmw_demo_output_packet
except ImportError:
    from tlv_packet_parser import MAGIC_WORD, parser_one_mmw_demo_output_packet

try:
    from ..filter.noise_filter import points_dict_to_list, preprocess_points
    from ..cluster.dbscan_cluster import cluster_points
    from ..tracking.kalman_tracker import MultiObjectKalmanTracker
except ImportError:
    from filter.noise_filter import points_dict_to_list, preprocess_points
    from cluster.dbscan_cluster import cluster_points
    from tracking.kalman_tracker import MultiObjectKalmanTracker


WORD = [1, 2**8, 2**16, 2**24]


@dataclass
class ParsedFrame:
    frame_number: int
    num_obj: int
    points: Dict[str, list]


class MMWaveSerialReader:
    def __init__(self, max_buffer_size: int = 2**15, debug: bool = False):
        self.max_buffer_size = max_buffer_size
        self.byte_buffer = bytearray(max_buffer_size)
        self.byte_buffer_length = 0
        self.debug = debug

    def _append(self, chunk: bytes) -> None:
        if not chunk:
            return
        if len(chunk) > self.max_buffer_size:
            chunk = chunk[-self.max_buffer_size:]
        free = self.max_buffer_size - self.byte_buffer_length
        if len(chunk) > free:
            overflow = len(chunk) - free
            self._shift_left(min(overflow, self.byte_buffer_length))
        end = self.byte_buffer_length + len(chunk)
        self.byte_buffer[self.byte_buffer_length:end] = chunk
        self.byte_buffer_length = end

    def _shift_left(self, shift: int) -> None:
        if shift <= 0:
            return
        remain = self.byte_buffer_length - shift
        if remain > 0:
            self.byte_buffer[:remain] = self.byte_buffer[shift:self.byte_buffer_length]
        self.byte_buffer[remain:self.byte_buffer_length] = b"\x00" * shift
        self.byte_buffer_length = max(0, remain)

    def read_frame(self, data_port: serial.Serial) -> Optional[ParsedFrame]:
        self._append(data_port.read(data_port.in_waiting or 1))
        if self.byte_buffer_length < 16:
            return None

        buffer_view = self.byte_buffer[:self.byte_buffer_length]
        start_idx = buffer_view.find(MAGIC_WORD)
        if start_idx == -1:
            self._shift_left(max(0, self.byte_buffer_length - 7))
            return None

        if start_idx > 0:
            self._shift_left(start_idx)
            buffer_view = self.byte_buffer[:self.byte_buffer_length]

        if self.byte_buffer_length < 16:
            return None

        total_packet_len = int(sum(buffer_view[12 + i] * WORD[i] for i in range(4)))
        if total_packet_len <= 0 or total_packet_len > self.max_buffer_size:
            self._shift_left(1)
            return None

        if self.byte_buffer_length < total_packet_len:
            return None

        packet = bytes(buffer_view[:total_packet_len])
        parsed = parser_one_mmw_demo_output_packet(packet, len(packet), self.debug)
        (
            parser_result,
            _header_start_index,
            total_packet_num_bytes,
            frame_number,
            num_det_obj,
            _num_tlv,
            _sub_frame_number,
            detected_x_array,
            detected_y_array,
            detected_z_array,
            detected_v_array,
            detected_range_array,
            _detected_azimuth_array,
            _detected_elevation_array,
            detected_snr_array,
            detected_noise_array,
        ) = parsed

        shift_size = total_packet_num_bytes if total_packet_num_bytes > 0 else total_packet_len
        self._shift_left(shift_size)

        if parser_result != 0:
            return None

        points = {
            "x": detected_x_array,
            "y": detected_y_array,
            "z": detected_z_array,
            "v": detected_v_array,
            "range": detected_range_array,
            "snr": detected_snr_array,
            "noise": detected_noise_array,
        }
        return ParsedFrame(frame_number=frame_number, num_obj=num_det_obj, points=points)


def send_config(cli_port: serial.Serial, config_file: Path) -> None:
    lines = config_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        cmd = line.strip()
        if not cmd or cmd.startswith("%"):
            continue
        cli_port.write((cmd + "\n").encode())
        time.sleep(0.01)


def run_realtime(
    cli_port_name: str,
    data_port_name: str,
    config_file: str,
    duration_sec: Optional[int] = None,
    debug: bool = False,
    snr_threshold: float = 8.0,
    max_noise: Optional[float] = None,
    min_range: float = 0.0,
    max_range: Optional[float] = None,
    dbscan_eps: float = 0.6,
    dbscan_min_samples: int = 4,
    use_velocity_feature: bool = False,
    association_gate: float = 1.5,
    max_misses: int = 8,
    min_hits: int = 2,
) -> None:
    config_path = Path(config_file)
    tracker = None
    dbscan_import_error_printed = False

    try:
        tracker = MultiObjectKalmanTracker(
            association_gate=association_gate,
            max_misses=max_misses,
            min_hits=min_hits,
        )
    except ImportError as exc:
        print(f"[WARN] Kalman tracker disabled: {exc}")

    with serial.Serial(cli_port_name, 115200, timeout=0.1) as cli_port, serial.Serial(
        data_port_name, 921600, timeout=0.05
    ) as data_port:
        send_config(cli_port, config_path)
        reader = MMWaveSerialReader(debug=debug)

        start_time = time.time()
        report_t0 = start_time
        processed_frames = 0

        while True:
            frame = reader.read_frame(data_port)
            if frame is not None:
                now = time.time()
                processed_frames += 1

                raw_points = points_dict_to_list(frame.points, frame.num_obj)
                filtered_points = preprocess_points(
                    raw_points,
                    snr_threshold=snr_threshold,
                    max_noise=max_noise,
                    min_range=min_range,
                    max_range=max_range,
                )

                clusters = []
                try:
                    clusters = cluster_points(
                        filtered_points,
                        eps=dbscan_eps,
                        min_samples=dbscan_min_samples,
                        use_velocity_feature=use_velocity_feature,
                    )
                except ImportError as exc:
                    if not dbscan_import_error_printed:
                        print(f"[WARN] DBSCAN disabled: {exc}")
                        dbscan_import_error_printed = True

                tracks = []
                if tracker is not None:
                    tracks = tracker.update(clusters, frame_ts=now)

                print(
                    f"frame={frame.frame_number} raw={len(raw_points)} "
                    f"filtered={len(filtered_points)} clusters={len(clusters)} tracks={len(tracks)}"
                )

                elapsed_report = now - report_t0
                if elapsed_report >= 1.0:
                    fps = processed_frames / elapsed_report
                    print(f"[PERF] fps={fps:.1f} window={elapsed_report:.2f}s")
                    report_t0 = now
                    processed_frames = 0

            if duration_sec is not None and (time.time() - start_time) >= duration_sec:
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time TLV reader for IWR6843")
    parser.add_argument("--cli-port", required=True, help="CLI port (e.g. COM6)")
    parser.add_argument("--data-port", required=True, help="Data port (e.g. COM5)")
    parser.add_argument("--config", required=True, help="Path to mmWave cfg file")
    parser.add_argument("--duration", type=int, default=None, help="Run duration in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable parser debug output")

    parser.add_argument("--snr-threshold", type=float, default=8.0, help="Minimum SNR for preprocessing")
    parser.add_argument("--max-noise", type=float, default=None, help="Maximum noise threshold")
    parser.add_argument("--min-range", type=float, default=0.0, help="Minimum detection range")
    parser.add_argument("--max-range", type=float, default=None, help="Maximum detection range")

    parser.add_argument("--dbscan-eps", type=float, default=0.6, help="DBSCAN eps parameter")
    parser.add_argument("--dbscan-min-samples", type=int, default=4, help="DBSCAN min_samples parameter")
    parser.add_argument(
        "--use-velocity-feature",
        action="store_true",
        help="Use (x, y, v) for DBSCAN features instead of (x, y)",
    )

    parser.add_argument("--association-gate", type=float, default=1.5, help="Tracker association gate in meters")
    parser.add_argument("--max-misses", type=int, default=8, help="Maximum consecutive misses before track deletion")
    parser.add_argument("--min-hits", type=int, default=2, help="Minimum hits before a track is reported")

    args = parser.parse_args()

    run_realtime(
        cli_port_name=args.cli_port,
        data_port_name=args.data_port,
        config_file=args.config,
        duration_sec=args.duration,
        debug=args.debug,
        snr_threshold=args.snr_threshold,
        max_noise=args.max_noise,
        min_range=args.min_range,
        max_range=args.max_range,
        dbscan_eps=args.dbscan_eps,
        dbscan_min_samples=args.dbscan_min_samples,
        use_velocity_feature=args.use_velocity_feature,
        association_gate=args.association_gate,
        max_misses=args.max_misses,
        min_hits=args.min_hits,
    )


if __name__ == "__main__":
    main()
