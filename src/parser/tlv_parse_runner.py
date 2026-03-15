"""Real-time UART reader for IWR6843 TLV point-cloud frames."""

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
    src_root = Path(__file__).resolve().parents[1]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from filter.noise_filter import points_dict_to_list, preprocess_points
    from cluster.dbscan_cluster import cluster_points
    from tracking.kalman_tracker import MultiObjectKalmanTracker


WORD = [1, 2**8, 2**16, 2**24]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "evidence" / "runtime_logs"


@dataclass
class ParsedFrame:
    frame_number: int
    num_obj: int
    points: Dict[str, list]
    packet_bytes: int
    num_tlv: int
    sub_frame_number: int
    parser_latency_ms: float


@dataclass
class ReaderStats:
    bytes_received: int = 0
    read_calls: int = 0
    frames_ok: int = 0
    parse_failures: int = 0
    resync_events: int = 0
    invalid_packet_events: int = 0
    dropped_frames_estimate: int = 0
    last_frame_number: Optional[int] = None


class CsvRunLogger:
    def __init__(self, enabled: bool, log_dir: Path, scenario: str, roi_tag: str):
        self.enabled = enabled
        self.log_dir = log_dir
        self.scenario = scenario
        self.roi_tag = roi_tag
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.frame_log_path: Optional[Path] = None
        self.summary_log_path: Optional[Path] = None
        self._frame_fp = None
        self._frame_writer = None

        if not enabled:
            return

        log_dir.mkdir(parents=True, exist_ok=True)
        self.frame_log_path = log_dir / f"frames_{self.run_id}.csv"
        self.summary_log_path = log_dir / "run_summary.csv"

        self._frame_fp = self.frame_log_path.open("w", newline="", encoding="utf-8")
        self._frame_writer = csv.DictWriter(
            self._frame_fp,
            fieldnames=[
                "run_id",
                "scenario",
                "roi_tag",
                "wall_time",
                "elapsed_sec",
                "frame_number",
                "frame_gap",
                "packet_bytes",
                "num_obj",
                "num_tlv",
                "sub_frame_number",
                "raw_points",
                "filtered_points",
                "clusters",
                "tracks",
                "parser_latency_ms",
                "pipeline_latency_ms",
                "parse_failures_so_far",
                "resync_events_so_far",
                "dropped_frames_estimate_so_far",
            ],
        )
        self._frame_writer.writeheader()

    def log_frame(self, row: Dict[str, object]) -> None:
        if not self.enabled or self._frame_writer is None:
            return
        self._frame_writer.writerow(row)
        self._frame_fp.flush()

    def log_summary(self, row: Dict[str, object]) -> None:
        if not self.enabled or self.summary_log_path is None:
            return

        file_exists = self.summary_log_path.exists()
        with self.summary_log_path.open("a", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "run_id",
                    "started_at",
                    "ended_at",
                    "duration_sec",
                    "scenario",
                    "roi_tag",
                    "config_file",
                    "frames_processed",
                    "avg_fps",
                    "avg_packet_bytes",
                    "avg_num_obj",
                    "avg_raw_points",
                    "avg_filtered_points",
                    "avg_clusters",
                    "avg_tracks",
                    "avg_parser_latency_ms",
                    "avg_pipeline_latency_ms",
                    "bytes_received",
                    "read_calls",
                    "parse_failures",
                    "resync_events",
                    "invalid_packet_events",
                    "dropped_frames_estimate",
                    "snr_threshold",
                    "min_range",
                    "max_range",
                    "dbscan_eps",
                    "dbscan_min_samples",
                    "association_gate",
                    "frame_log_path",
                ],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    def close(self) -> None:
        if self._frame_fp is not None:
            self._frame_fp.close()
            self._frame_fp = None


class MMWaveSerialReader:
    def __init__(self, max_buffer_size: int = 2**15, debug: bool = False):
        self.max_buffer_size = max_buffer_size
        self.byte_buffer = bytearray(max_buffer_size)
        self.byte_buffer_length = 0
        self.debug = debug
        self.stats = ReaderStats()

    def _append(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.stats.read_calls += 1
        self.stats.bytes_received += len(chunk)
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
        parse_t0 = time.perf_counter()
        self._append(data_port.read(data_port.in_waiting or 1))
        if self.byte_buffer_length < 16:
            return None

        buffer_view = self.byte_buffer[:self.byte_buffer_length]
        start_idx = buffer_view.find(MAGIC_WORD)
        if start_idx == -1:
            if self.byte_buffer_length > 7:
                self.stats.resync_events += 1
            self._shift_left(max(0, self.byte_buffer_length - 7))
            return None

        if start_idx > 0:
            self.stats.resync_events += 1
            self._shift_left(start_idx)
            buffer_view = self.byte_buffer[:self.byte_buffer_length]

        if self.byte_buffer_length < 16:
            return None

        total_packet_len = int(sum(buffer_view[12 + i] * WORD[i] for i in range(4)))
        if total_packet_len <= 0 or total_packet_len > self.max_buffer_size:
            self.stats.invalid_packet_events += 1
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
            self.stats.parse_failures += 1
            return None

        if self.stats.last_frame_number is not None and frame_number > self.stats.last_frame_number + 1:
            self.stats.dropped_frames_estimate += frame_number - self.stats.last_frame_number - 1
        self.stats.last_frame_number = frame_number
        self.stats.frames_ok += 1

        parser_latency_ms = (time.perf_counter() - parse_t0) * 1000.0

        points = {
            "x": detected_x_array,
            "y": detected_y_array,
            "z": detected_z_array,
            "v": detected_v_array,
            "range": detected_range_array,
            "snr": detected_snr_array,
            "noise": detected_noise_array,
        }
        return ParsedFrame(
            frame_number=frame_number,
            num_obj=num_det_obj,
            points=points,
            packet_bytes=total_packet_num_bytes,
            num_tlv=_num_tlv,
            sub_frame_number=_sub_frame_number,
            parser_latency_ms=parser_latency_ms,
        )


def send_config(cli_port: serial.Serial, config_file: Path) -> None:
    def read_cli_lines(quiet_window_sec: float = 0.08, max_wait_sec: float = 0.5) -> List[str]:
        buffer = ""
        deadline = time.time() + max_wait_sec
        quiet_deadline = time.time() + quiet_window_sec

        while time.time() < deadline:
            waiting = cli_port.in_waiting
            if waiting:
                buffer += cli_port.read(waiting).decode("utf-8", errors="replace")
                quiet_deadline = time.time() + quiet_window_sec
                continue

            if time.time() >= quiet_deadline:
                break
            time.sleep(0.01)

        return [line.strip() for line in buffer.replace("\r", "\n").split("\n") if line.strip()]

    def is_cli_error(line: str) -> bool:
        lowered = line.lower()
        return "error" in lowered or "fail" in lowered

    startup_lines = read_cli_lines(quiet_window_sec=0.05, max_wait_sec=0.2)
    for response in startup_lines:
        print(f"[CFG] << {response}")

    lines = config_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        cmd = line.strip()
        if not cmd or cmd.startswith("%"):
            continue

        print(f"[CFG] >> {cmd}")
        cli_port.write((cmd + "\n").encode("utf-8"))
        cli_port.flush()

        responses = read_cli_lines()
        for response in responses:
            print(f"[CFG] << {response}")
            if is_cli_error(response):
                raise RuntimeError(f"CLI rejected cfg command '{cmd}': {response}")

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
    scenario: str = "live_run",
    roi_tag: str = "",
    log_dir: Optional[str] = None,
    disable_file_log: bool = False,
) -> None:
    config_path = Path(config_file)
    tracker = None
    dbscan_import_error_printed = False
    started_at = datetime.now()
    logger = CsvRunLogger(
        enabled=not disable_file_log,
        log_dir=Path(log_dir) if log_dir is not None else DEFAULT_LOG_DIR,
        scenario=scenario,
        roi_tag=roi_tag,
    )

    total_packet_bytes = 0
    total_num_obj = 0
    total_raw_points = 0
    total_filtered_points = 0
    total_clusters = 0
    total_tracks = 0
    total_parser_latency_ms = 0.0
    total_pipeline_latency_ms = 0.0
    prev_frame_number: Optional[int] = None

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

        try:
            while True:
                frame = reader.read_frame(data_port)
                if frame is not None:
                    process_t0 = time.perf_counter()
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

                    pipeline_latency_ms = (time.perf_counter() - process_t0) * 1000.0
                    frame_gap = 0 if prev_frame_number is None else max(0, frame.frame_number - prev_frame_number - 1)
                    prev_frame_number = frame.frame_number

                    total_packet_bytes += frame.packet_bytes
                    total_num_obj += frame.num_obj
                    total_raw_points += len(raw_points)
                    total_filtered_points += len(filtered_points)
                    total_clusters += len(clusters)
                    total_tracks += len(tracks)
                    total_parser_latency_ms += frame.parser_latency_ms
                    total_pipeline_latency_ms += pipeline_latency_ms

                    print(
                        f"frame={frame.frame_number} packet={frame.packet_bytes}B raw={len(raw_points)} "
                        f"filtered={len(filtered_points)} clusters={len(clusters)} tracks={len(tracks)} "
                        f"parser_ms={frame.parser_latency_ms:.2f} pipe_ms={pipeline_latency_ms:.2f}"
                    )

                    logger.log_frame(
                        {
                            "run_id": logger.run_id,
                            "scenario": scenario,
                            "roi_tag": roi_tag,
                            "wall_time": datetime.now().isoformat(timespec="milliseconds"),
                            "elapsed_sec": round(now - start_time, 3),
                            "frame_number": frame.frame_number,
                            "frame_gap": frame_gap,
                            "packet_bytes": frame.packet_bytes,
                            "num_obj": frame.num_obj,
                            "num_tlv": frame.num_tlv,
                            "sub_frame_number": frame.sub_frame_number,
                            "raw_points": len(raw_points),
                            "filtered_points": len(filtered_points),
                            "clusters": len(clusters),
                            "tracks": len(tracks),
                            "parser_latency_ms": round(frame.parser_latency_ms, 3),
                            "pipeline_latency_ms": round(pipeline_latency_ms, 3),
                            "parse_failures_so_far": reader.stats.parse_failures,
                            "resync_events_so_far": reader.stats.resync_events,
                            "dropped_frames_estimate_so_far": reader.stats.dropped_frames_estimate,
                        }
                    )

                    elapsed_report = now - report_t0
                    if elapsed_report >= 1.0:
                        fps = processed_frames / elapsed_report
                        print(f"[PERF] fps={fps:.1f} window={elapsed_report:.2f}s")
                        report_t0 = now
                        processed_frames = 0

                if duration_sec is not None and (time.time() - start_time) >= duration_sec:
                    break
        finally:
            end_time = time.time()
            duration = max(end_time - start_time, 1e-9)
            frames = reader.stats.frames_ok
            summary = {
                "run_id": logger.run_id,
                "started_at": started_at.isoformat(timespec="seconds"),
                "ended_at": datetime.now().isoformat(timespec="seconds"),
                "duration_sec": round(duration, 3),
                "scenario": scenario,
                "roi_tag": roi_tag,
                "config_file": str(config_path),
                "frames_processed": frames,
                "avg_fps": round(frames / duration, 3),
                "avg_packet_bytes": round(total_packet_bytes / frames, 3) if frames else 0.0,
                "avg_num_obj": round(total_num_obj / frames, 3) if frames else 0.0,
                "avg_raw_points": round(total_raw_points / frames, 3) if frames else 0.0,
                "avg_filtered_points": round(total_filtered_points / frames, 3) if frames else 0.0,
                "avg_clusters": round(total_clusters / frames, 3) if frames else 0.0,
                "avg_tracks": round(total_tracks / frames, 3) if frames else 0.0,
                "avg_parser_latency_ms": round(total_parser_latency_ms / frames, 3) if frames else 0.0,
                "avg_pipeline_latency_ms": round(total_pipeline_latency_ms / frames, 3) if frames else 0.0,
                "bytes_received": reader.stats.bytes_received,
                "read_calls": reader.stats.read_calls,
                "parse_failures": reader.stats.parse_failures,
                "resync_events": reader.stats.resync_events,
                "invalid_packet_events": reader.stats.invalid_packet_events,
                "dropped_frames_estimate": reader.stats.dropped_frames_estimate,
                "snr_threshold": snr_threshold,
                "min_range": min_range,
                "max_range": max_range if max_range is not None else "",
                "dbscan_eps": dbscan_eps,
                "dbscan_min_samples": dbscan_min_samples,
                "association_gate": association_gate,
                "frame_log_path": str(logger.frame_log_path) if logger.frame_log_path else "",
            }
            logger.log_summary(summary)
            logger.close()

            if not disable_file_log:
                print(f"[LOG] frame_log={logger.frame_log_path}")
                print(f"[LOG] summary_log={logger.summary_log_path}")
            print(
                "[SUMMARY] "
                f"frames={frames} avg_fps={summary['avg_fps']:.2f} avg_packet={summary['avg_packet_bytes']:.1f}B "
                f"avg_parser_ms={summary['avg_parser_latency_ms']:.2f} parse_failures={reader.stats.parse_failures} "
                f"resyncs={reader.stats.resync_events} dropped_est={reader.stats.dropped_frames_estimate}"
            )


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
    parser.add_argument("--scenario", default="live_run", help="Scenario tag for runtime logs")
    parser.add_argument("--roi-tag", default="", help="ROI tag for runtime logs")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="Directory to store runtime CSV logs")
    parser.add_argument("--disable-file-log", action="store_true", help="Disable CSV runtime logging")

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
        scenario=args.scenario,
        roi_tag=args.roi_tag,
        log_dir=args.log_dir,
        disable_file_log=args.disable_file_log,
    )


if __name__ == "__main__":
    main()
