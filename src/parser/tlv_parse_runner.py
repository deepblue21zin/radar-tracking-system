"""Real-time UART reader for IWR6843 TLV point-cloud frames."""

import argparse
import csv
import sys
import time
import traceback
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
    from ..filter.noise_filter import AxisAlignedBox, FilterStats, points_dict_to_list, preprocess_points
    from ..cluster.dbscan_cluster import cluster_points
    from ..tracking.kalman_tracker import MultiObjectKalmanTracker
except ImportError:
    src_root = Path(__file__).resolve().parents[1]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from filter.noise_filter import AxisAlignedBox, FilterStats, points_dict_to_list, preprocess_points
    from cluster.dbscan_cluster import cluster_points
    from tracking.kalman_tracker import MultiObjectKalmanTracker


WORD = [1, 2**8, 2**16, 2**24]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "evidence" / "runtime_logs"
DEFAULT_ERROR_LOG_DIR = PROJECT_ROOT / "docs" / "error"


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
        self.text_log_path: Optional[Path] = None
        self.summary_log_path: Optional[Path] = None
        self._frame_fp = None
        self._frame_writer = None
        self._text_fp = None

        if not enabled:
            return

        log_dir.mkdir(parents=True, exist_ok=True)
        self.frame_log_path = log_dir / f"frames_{self.run_id}.csv"
        self.text_log_path = log_dir / f"frames_{self.run_id}.log"
        self.summary_log_path = log_dir / "run_summary.csv"

        self._frame_fp = self.frame_log_path.open("w", newline="", encoding="utf-8")
        self._text_fp = self.text_log_path.open("w", encoding="utf-8")
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
                "filter_ratio",
                "raw_snr_min",
                "raw_snr_avg",
                "raw_snr_p90",
                "filtered_snr_min",
                "filtered_snr_avg",
                "filtered_snr_p90",
                "raw_range_min",
                "raw_range_max",
                "filtered_range_min",
                "filtered_range_max",
                "removed_snr",
                "removed_noise",
                "removed_range",
                "removed_axis_roi",
                "removed_keepout",
                "removed_near_front_keepout",
                "removed_right_rail_keepout",
                "removed_static_clutter",
                "parse_failures_so_far",
                "resync_events_so_far",
                "dropped_frames_estimate_so_far",
                "frame_summary",
                "filter_stats_summary",
                "filter_sample_preview",
                "filtered_preview",
                "cluster_preview",
                "track_preview",
            ],
        )
        self._frame_writer.writeheader()

    def log_frame(self, row: Dict[str, object]) -> None:
        if not self.enabled or self._frame_writer is None:
            return
        self._frame_writer.writerow(row)
        self._frame_fp.flush()

    def log_text(self, line: str) -> None:
        if not self.enabled or self._text_fp is None:
            return
        self._text_fp.write(line.rstrip("\n") + "\n")
        self._text_fp.flush()

    def log_summary(self, row: Dict[str, object]) -> None:
        if not self.enabled or self.summary_log_path is None:
            return

        fieldnames = [
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
            "avg_filter_ratio",
            "avg_removed_snr",
            "avg_removed_noise",
            "avg_removed_range",
            "avg_removed_axis_roi",
            "avg_removed_keepout",
            "avg_removed_near_front_keepout",
            "avg_removed_right_rail_keepout",
            "avg_removed_static_clutter",
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
        ]
        file_exists = self.summary_log_path.exists()
        existing_rows: List[Dict[str, str]] = []
        rewrite_header = False

        if file_exists:
            with self.summary_log_path.open("r", newline="", encoding="utf-8") as read_fp:
                reader = csv.DictReader(read_fp)
                existing_fieldnames = reader.fieldnames or []
                if existing_fieldnames != fieldnames:
                    rewrite_header = True
                    existing_rows = list(reader)

        mode = "w" if rewrite_header or not file_exists else "a"
        with self.summary_log_path.open(mode, newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=fieldnames,
            )
            if not file_exists or rewrite_header:
                writer.writeheader()
            if rewrite_header:
                for existing_row in existing_rows:
                    writer.writerow({key: existing_row.get(key, "") for key in fieldnames})
            writer.writerow(row)

    def close(self) -> None:
        if self._frame_fp is not None:
            self._frame_fp.close()
            self._frame_fp = None
        if self._text_fp is not None:
            self._text_fp.close()
            self._text_fp = None


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


def append_error_log(args: argparse.Namespace, exc: Exception, error_log_dir: Path) -> Path:
    error_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = error_log_dir / f"{datetime.now():%Y-%m-%d}.md"
    timestamp = datetime.now().isoformat(timespec="seconds")
    command = "python src/parser/tlv_parse_runner.py " + " ".join(sys.argv[1:])
    traceback_text = traceback.format_exc().strip()

    is_new_file = not log_path.exists()
    with log_path.open("a", encoding="utf-8") as fp:
        if is_new_file:
            fp.write(f"# {datetime.now():%Y-%m-%d} Error Log\n\n")
            fp.write("- 실행 중 발생한 오류를 날짜별로 누적 기록한다.\n")
            fp.write("- 같은 날짜에는 새 오류를 파일 아래쪽에 계속 추가한다.\n\n")

        fp.write(f"## Error {timestamp}\n")
        fp.write(f"- 명령: `{command}`\n")
        fp.write(f"- CLI port: `{args.cli_port}`\n")
        fp.write(f"- Data port: `{args.data_port}`\n")
        fp.write(f"- Config: `{args.config}`\n")
        fp.write(f"- Scenario: `{args.scenario}`\n")
        fp.write(f"- Error type: `{type(exc).__name__}`\n")
        fp.write(f"- Error message: `{exc}`\n\n")
        fp.write("```text\n")
        fp.write(traceback_text + "\n")
        fp.write("```\n\n")

    return log_path


def format_point_preview(points: List[dict], limit: int) -> str:
    if limit <= 0 or not points:
        return ""

    preview_items = []
    for point in points[:limit]:
        preview_items.append(
            f"({point.get('x', 0.0):.2f}, {point.get('y', 0.0):.2f}, {point.get('z', 0.0):.2f})"
        )
    return "[" + ", ".join(preview_items) + "]"


def format_cluster_preview(clusters: List[dict], limit: int) -> str:
    if limit <= 0 or not clusters:
        return ""

    preview_items = []
    for cluster in clusters[:limit]:
        preview_items.append(
            "{" +
            f"x={cluster.get('x', 0.0):.2f}, y={cluster.get('y', 0.0):.2f}, "
            f"z={cluster.get('z', 0.0):.2f}, size={cluster.get('size', 0)}" +
            "}"
        )
    return "[" + ", ".join(preview_items) + "]"


def format_track_preview(tracks: List[object], limit: int) -> str:
    if limit <= 0 or not tracks:
        return ""

    preview_items = []
    for track in tracks[:limit]:
        preview_items.append(
            "{" +
            f"id={getattr(track, 'track_id', -1)}, x={getattr(track, 'x', 0.0):.2f}, "
            f"y={getattr(track, 'y', 0.0):.2f}, vx={getattr(track, 'vx', 0.0):.2f}, "
            f"vy={getattr(track, 'vy', 0.0):.2f}" +
            "}"
        )
    return "[" + ", ".join(preview_items) + "]"


def format_frame_summary(
    frame: ParsedFrame,
    frame_gap: int,
    raw_count: int,
    filtered_count: int,
    cluster_count: int,
    track_count: int,
    pipeline_latency_ms: float,
    stats: ReaderStats,
) -> str:
    return (
        f"frame={frame.frame_number} gap={frame_gap} packet={frame.packet_bytes}B "
        f"num_obj={frame.num_obj} num_tlv={frame.num_tlv} subframe={frame.sub_frame_number} "
        f"raw={raw_count} filtered={filtered_count} clusters={cluster_count} tracks={track_count} "
        f"parser_ms={frame.parser_latency_ms:.2f} pipe_ms={pipeline_latency_ms:.2f} "
        f"parse_failures={stats.parse_failures} resyncs={stats.resync_events} "
        f"dropped_est={stats.dropped_frames_estimate}"
    )


def _fmt_metric(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "na"
    return f"{value:.{digits}f}"


def format_filter_stats_summary(stats: FilterStats) -> str:
    return (
        f"filter_ratio={stats.filter_ratio:.2f} "
        f"raw_snr[min/avg/p90]={_fmt_metric(stats.raw_snr_min)}/{_fmt_metric(stats.raw_snr_avg)}/{_fmt_metric(stats.raw_snr_p90)} "
        f"filtered_snr[min/avg/p90]={_fmt_metric(stats.filtered_snr_min)}/{_fmt_metric(stats.filtered_snr_avg)}/{_fmt_metric(stats.filtered_snr_p90)} "
        f"raw_range[min,max]={_fmt_metric(stats.raw_range_min)}/{_fmt_metric(stats.raw_range_max)} "
        f"filtered_range[min,max]={_fmt_metric(stats.filtered_range_min)}/{_fmt_metric(stats.filtered_range_max)} "
        f"removed={{snr:{stats.removed_snr}, noise:{stats.removed_noise}, range:{stats.removed_range}, "
        f"roi:{stats.removed_axis_roi}, keepout:{stats.removed_keepout}, "
        f"near_front:{stats.removed_near_front_keepout}, right_rail:{stats.removed_right_rail_keepout}, "
        f"static:{stats.removed_static_clutter}}}"
    )


def format_filter_sample_preview(points: List[dict], sample_source: str) -> str:
    if not points:
        return ""

    preview_items = []
    for point in points:
        preview_items.append(
            "{" +
            f"x={point.get('x', 0.0):.2f}, y={point.get('y', 0.0):.2f}, z={point.get('z', 0.0):.2f}, "
            f"snr={point.get('snr', 0.0):.2f}, noise={point.get('noise', 0.0):.2f}, "
            f"v={point.get('v', 0.0):.2f}" +
            "}"
        )
    prefix = f"{sample_source}=" if sample_source else ""
    return prefix + "[" + ", ".join(preview_items) + "]"


def build_keepout_boxes(
    near_front_enabled: bool,
    near_front_distance: float,
    near_front_half_width: float,
    near_front_z_min: float,
    near_front_z_max: float,
    right_rail_enabled: bool,
    right_rail_x: float,
    right_rail_width: float,
    right_rail_y_start: float,
    right_rail_length: float,
    right_rail_z_base: float,
    right_rail_height: float,
    right_rail_padding: float,
) -> List[AxisAlignedBox]:
    boxes: List[AxisAlignedBox] = []
    if near_front_enabled:
        boxes.append(
            AxisAlignedBox(
                label="near_front",
                x_min=-abs(near_front_half_width),
                x_max=abs(near_front_half_width),
                y_min=0.0,
                y_max=max(0.0, near_front_distance),
                z_min=near_front_z_min,
                z_max=near_front_z_max,
            )
        )
    if right_rail_enabled:
        half_width = right_rail_width / 2.0
        boxes.append(
            AxisAlignedBox(
                label="right_rail",
                x_min=right_rail_x - half_width - right_rail_padding,
                x_max=right_rail_x + half_width + right_rail_padding,
                y_min=right_rail_y_start - right_rail_padding,
                y_max=right_rail_y_start + right_rail_length + right_rail_padding,
                z_min=right_rail_z_base - right_rail_padding,
                z_max=right_rail_z_base + right_rail_height + right_rail_padding,
            )
        )
    return boxes


def build_static_clutter_boxes(
    enabled: bool,
    right_rail_x: float,
    right_rail_width: float,
    right_rail_y_start: float,
    right_rail_length: float,
    right_rail_z_base: float,
    right_rail_height: float,
    right_rail_padding: float,
    static_clutter_padding: float,
) -> List[AxisAlignedBox]:
    if not enabled:
        return []

    half_width = right_rail_width / 2.0
    padding = right_rail_padding + static_clutter_padding
    return [
        AxisAlignedBox(
            label="right_rail_static",
            x_min=right_rail_x - half_width - padding,
            x_max=right_rail_x + half_width + padding,
            y_min=right_rail_y_start - padding,
            y_max=right_rail_y_start + right_rail_length + padding,
            z_min=right_rail_z_base - padding,
            z_max=right_rail_z_base + right_rail_height + padding,
        )
    ]


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
    filter_x_min: Optional[float] = None,
    filter_x_max: Optional[float] = None,
    filter_y_min: Optional[float] = None,
    filter_y_max: Optional[float] = None,
    filter_z_min: Optional[float] = None,
    filter_z_max: Optional[float] = None,
    disable_near_front_keepout: bool = False,
    near_front_distance: float = 1.0,
    near_front_half_width: float = 1.1,
    near_front_z_min: float = -0.5,
    near_front_z_max: float = 1.5,
    disable_right_rail_keepout: bool = False,
    right_rail_x: float = 1.8,
    right_rail_width: float = 0.35,
    right_rail_y_start: float = 0.0,
    right_rail_length: float = 8.0,
    right_rail_z_base: float = 0.0,
    right_rail_height: float = 1.0,
    right_rail_padding: float = 0.15,
    disable_static_clutter_filter: bool = False,
    static_clutter_padding: float = 0.25,
    static_v_min: float = 0.12,
    static_max_snr: float = 18.0,
    filter_sample_count: int = 2,
    dbscan_eps: float = 0.6,
    dbscan_min_samples: int = 4,
    use_velocity_feature: bool = False,
    association_gate: float = 1.5,
    max_misses: int = 8,
    min_hits: int = 2,
    report_miss_tolerance: int = 0,
    scenario: str = "live_run",
    roi_tag: str = "",
    log_dir: Optional[str] = None,
    disable_file_log: bool = False,
    coord_preview_count: int = 0,
    coord_preview_every: int = 1,
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

    def emit_log(line: str) -> None:
        print(line)
        logger.log_text(line)

    total_packet_bytes = 0
    total_num_obj = 0
    total_raw_points = 0
    total_filtered_points = 0
    total_clusters = 0
    total_tracks = 0
    total_parser_latency_ms = 0.0
    total_pipeline_latency_ms = 0.0
    total_filter_ratio = 0.0
    total_removed_snr = 0
    total_removed_noise = 0
    total_removed_range = 0
    total_removed_axis_roi = 0
    total_removed_keepout = 0
    total_removed_near_front_keepout = 0
    total_removed_right_rail_keepout = 0
    total_removed_static_clutter = 0
    prev_frame_number: Optional[int] = None

    keepout_boxes = build_keepout_boxes(
        near_front_enabled=not disable_near_front_keepout,
        near_front_distance=near_front_distance,
        near_front_half_width=near_front_half_width,
        near_front_z_min=near_front_z_min,
        near_front_z_max=near_front_z_max,
        right_rail_enabled=not disable_right_rail_keepout,
        right_rail_x=right_rail_x,
        right_rail_width=right_rail_width,
        right_rail_y_start=right_rail_y_start,
        right_rail_length=right_rail_length,
        right_rail_z_base=right_rail_z_base,
        right_rail_height=right_rail_height,
        right_rail_padding=right_rail_padding,
    )
    static_clutter_boxes = build_static_clutter_boxes(
        enabled=not disable_static_clutter_filter,
        right_rail_x=right_rail_x,
        right_rail_width=right_rail_width,
        right_rail_y_start=right_rail_y_start,
        right_rail_length=right_rail_length,
        right_rail_z_base=right_rail_z_base,
        right_rail_height=right_rail_height,
        right_rail_padding=right_rail_padding,
        static_clutter_padding=static_clutter_padding,
    )

    try:
        tracker = MultiObjectKalmanTracker(
            association_gate=association_gate,
            max_misses=max_misses,
            min_hits=min_hits,
            report_miss_tolerance=report_miss_tolerance,
        )
    except ImportError as exc:
        print(f"[WARN] Kalman tracker disabled: {exc}")

    with serial.Serial(cli_port_name, 115200, timeout=0.1) as cli_port, serial.Serial(
        data_port_name, 921600, timeout=0.05
    ) as data_port:
        emit_log(
            "[FILTER_CFG] "
            f"axis_roi=x[{filter_x_min if filter_x_min is not None else '-inf'},{filter_x_max if filter_x_max is not None else 'inf'}] "
            f"y[{filter_y_min if filter_y_min is not None else '-inf'},{filter_y_max if filter_y_max is not None else 'inf'}] "
            f"z[{filter_z_min if filter_z_min is not None else '-inf'},{filter_z_max if filter_z_max is not None else 'inf'}] "
            f"near_front={'on' if not disable_near_front_keepout else 'off'} "
            f"right_rail={'on' if not disable_right_rail_keepout else 'off'} "
            f"static_clutter={'on' if not disable_static_clutter_filter else 'off'} "
            f"static_v_min={static_v_min:.2f} static_max_snr={static_max_snr:.2f}"
        )
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
                    filtered_points, filter_stats = preprocess_points(
                        raw_points,
                        snr_threshold=snr_threshold,
                        max_noise=max_noise,
                        min_range=min_range,
                        max_range=max_range,
                        x_min=filter_x_min,
                        x_max=filter_x_max,
                        y_min=filter_y_min,
                        y_max=filter_y_max,
                        z_min=filter_z_min,
                        z_max=filter_z_max,
                        exclusion_boxes=keepout_boxes,
                        static_clutter_boxes=static_clutter_boxes,
                        static_v_min=static_v_min,
                        static_max_snr=static_max_snr,
                        sample_preview_count=filter_sample_count,
                        return_stats=True,
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
                    total_filter_ratio += filter_stats.filter_ratio
                    total_removed_snr += filter_stats.removed_snr
                    total_removed_noise += filter_stats.removed_noise
                    total_removed_range += filter_stats.removed_range
                    total_removed_axis_roi += filter_stats.removed_axis_roi
                    total_removed_keepout += filter_stats.removed_keepout
                    total_removed_near_front_keepout += filter_stats.removed_near_front_keepout
                    total_removed_right_rail_keepout += filter_stats.removed_right_rail_keepout
                    total_removed_static_clutter += filter_stats.removed_static_clutter

                    filtered_preview = ""
                    cluster_preview = ""
                    track_preview = ""
                    filter_sample_preview = format_filter_sample_preview(
                        filter_stats.sample_points,
                        filter_stats.sample_source,
                    )
                    filter_stats_summary = format_filter_stats_summary(filter_stats)
                    should_log_preview = coord_preview_count > 0 and (
                        coord_preview_every <= 1 or frame.frame_number % coord_preview_every == 0
                    )
                    if should_log_preview:
                        filtered_preview = format_point_preview(filtered_points, coord_preview_count)
                        cluster_preview = format_cluster_preview(clusters, coord_preview_count)
                        track_preview = format_track_preview(tracks, coord_preview_count)

                    frame_summary = format_frame_summary(
                        frame=frame,
                        frame_gap=frame_gap,
                        raw_count=len(raw_points),
                        filtered_count=len(filtered_points),
                        cluster_count=len(clusters),
                        track_count=len(tracks),
                        pipeline_latency_ms=pipeline_latency_ms,
                        stats=reader.stats,
                    )
                    emit_log(frame_summary)
                    emit_log(f"  {filter_stats_summary}")
                    if filter_sample_preview:
                        emit_log(f"  filter_sample={filter_sample_preview}")
                    if filtered_preview:
                        emit_log(f"  filtered_xyz={filtered_preview}")
                    if cluster_preview:
                        emit_log(f"  clusters_xyz={cluster_preview}")
                    if track_preview:
                        emit_log(f"  tracks_xy={track_preview}")

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
                            "filter_ratio": round(filter_stats.filter_ratio, 4),
                            "raw_snr_min": round(filter_stats.raw_snr_min, 3) if filter_stats.raw_snr_min is not None else "",
                            "raw_snr_avg": round(filter_stats.raw_snr_avg, 3) if filter_stats.raw_snr_avg is not None else "",
                            "raw_snr_p90": round(filter_stats.raw_snr_p90, 3) if filter_stats.raw_snr_p90 is not None else "",
                            "filtered_snr_min": round(filter_stats.filtered_snr_min, 3) if filter_stats.filtered_snr_min is not None else "",
                            "filtered_snr_avg": round(filter_stats.filtered_snr_avg, 3) if filter_stats.filtered_snr_avg is not None else "",
                            "filtered_snr_p90": round(filter_stats.filtered_snr_p90, 3) if filter_stats.filtered_snr_p90 is not None else "",
                            "raw_range_min": round(filter_stats.raw_range_min, 3) if filter_stats.raw_range_min is not None else "",
                            "raw_range_max": round(filter_stats.raw_range_max, 3) if filter_stats.raw_range_max is not None else "",
                            "filtered_range_min": round(filter_stats.filtered_range_min, 3) if filter_stats.filtered_range_min is not None else "",
                            "filtered_range_max": round(filter_stats.filtered_range_max, 3) if filter_stats.filtered_range_max is not None else "",
                            "removed_snr": filter_stats.removed_snr,
                            "removed_noise": filter_stats.removed_noise,
                            "removed_range": filter_stats.removed_range,
                            "removed_axis_roi": filter_stats.removed_axis_roi,
                            "removed_keepout": filter_stats.removed_keepout,
                            "removed_near_front_keepout": filter_stats.removed_near_front_keepout,
                            "removed_right_rail_keepout": filter_stats.removed_right_rail_keepout,
                            "removed_static_clutter": filter_stats.removed_static_clutter,
                            "parse_failures_so_far": reader.stats.parse_failures,
                            "resync_events_so_far": reader.stats.resync_events,
                            "dropped_frames_estimate_so_far": reader.stats.dropped_frames_estimate,
                            "frame_summary": frame_summary,
                            "filter_stats_summary": filter_stats_summary,
                            "filter_sample_preview": filter_sample_preview,
                            "filtered_preview": filtered_preview,
                            "cluster_preview": cluster_preview,
                            "track_preview": track_preview,
                        }
                    )

                    elapsed_report = now - report_t0
                    if elapsed_report >= 1.0:
                        fps = processed_frames / elapsed_report
                        emit_log(f"[PERF] fps={fps:.1f} window={elapsed_report:.2f}s")
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
                "avg_filter_ratio": round(total_filter_ratio / frames, 4) if frames else 0.0,
                "avg_removed_snr": round(total_removed_snr / frames, 3) if frames else 0.0,
                "avg_removed_noise": round(total_removed_noise / frames, 3) if frames else 0.0,
                "avg_removed_range": round(total_removed_range / frames, 3) if frames else 0.0,
                "avg_removed_axis_roi": round(total_removed_axis_roi / frames, 3) if frames else 0.0,
                "avg_removed_keepout": round(total_removed_keepout / frames, 3) if frames else 0.0,
                "avg_removed_near_front_keepout": round(total_removed_near_front_keepout / frames, 3) if frames else 0.0,
                "avg_removed_right_rail_keepout": round(total_removed_right_rail_keepout / frames, 3) if frames else 0.0,
                "avg_removed_static_clutter": round(total_removed_static_clutter / frames, 3) if frames else 0.0,
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

            if not disable_file_log:
                emit_log(f"[LOG] frame_log={logger.frame_log_path}")
                if logger.text_log_path is not None:
                    emit_log(f"[LOG] text_log={logger.text_log_path}")
                emit_log(f"[LOG] summary_log={logger.summary_log_path}")
            emit_log(
                "[SUMMARY] "
                f"frames={frames} avg_fps={summary['avg_fps']:.2f} avg_packet={summary['avg_packet_bytes']:.1f}B "
                f"avg_parser_ms={summary['avg_parser_latency_ms']:.2f} avg_filter_ratio={summary['avg_filter_ratio']:.2f} "
                f"parse_failures={reader.stats.parse_failures} resyncs={reader.stats.resync_events} "
                f"dropped_est={reader.stats.dropped_frames_estimate}"
            )
            logger.close()


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
    parser.add_argument("--filter-x-min", type=float, default=None, help="Inclusive filter ROI minimum X")
    parser.add_argument("--filter-x-max", type=float, default=None, help="Inclusive filter ROI maximum X")
    parser.add_argument("--filter-y-min", type=float, default=None, help="Inclusive filter ROI minimum Y")
    parser.add_argument("--filter-y-max", type=float, default=None, help="Inclusive filter ROI maximum Y")
    parser.add_argument("--filter-z-min", type=float, default=None, help="Inclusive filter ROI minimum Z")
    parser.add_argument("--filter-z-max", type=float, default=None, help="Inclusive filter ROI maximum Z")
    parser.add_argument("--disable-near-front-keepout", action="store_true", help="Disable near-front 1 m keepout box")
    parser.add_argument("--near-front-distance", type=float, default=1.0, help="Near-front keepout depth in meters")
    parser.add_argument("--near-front-half-width", type=float, default=1.1, help="Half-width of near-front keepout box")
    parser.add_argument("--near-front-z-min", type=float, default=-0.5, help="Near-front keepout minimum Z")
    parser.add_argument("--near-front-z-max", type=float, default=1.5, help="Near-front keepout maximum Z")
    parser.add_argument("--disable-right-rail-keepout", action="store_true", help="Disable right-rail keepout box")
    parser.add_argument("--right-rail-x", type=float, default=1.8, help="Right rail center X position")
    parser.add_argument("--right-rail-width", type=float, default=0.35, help="Right rail width")
    parser.add_argument("--right-rail-y-start", type=float, default=0.0, help="Right rail start Y position")
    parser.add_argument("--right-rail-length", type=float, default=8.0, help="Right rail length along Y")
    parser.add_argument("--right-rail-z-base", type=float, default=0.0, help="Right rail base Z position")
    parser.add_argument("--right-rail-height", type=float, default=1.0, help="Right rail height")
    parser.add_argument("--right-rail-padding", type=float, default=0.15, help="Padding around right rail keepout")
    parser.add_argument("--disable-static-clutter-filter", action="store_true", help="Disable low-velocity static clutter reject")
    parser.add_argument("--static-clutter-padding", type=float, default=0.25, help="Extra padding for static clutter box")
    parser.add_argument("--static-v-min", type=float, default=0.12, help="Low-velocity threshold for static clutter reject")
    parser.add_argument("--static-max-snr", type=float, default=18.0, help="Only reject static clutter when SNR is at most this value")
    parser.add_argument("--filter-sample-count", type=int, default=2, help="Number of sample points to store with x/y/z/snr/noise")

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
    parser.add_argument(
        "--report-miss-tolerance",
        type=int,
        default=0,
        help="Only report tracks whose miss count is at most this value",
    )
    parser.add_argument("--scenario", default="live_run", help="Scenario tag for runtime logs")
    parser.add_argument("--roi-tag", default="", help="ROI tag for runtime logs")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="Directory to store runtime CSV logs")
    parser.add_argument("--disable-file-log", action="store_true", help="Disable CSV runtime logging")
    parser.add_argument(
        "--coord-preview-count",
        type=int,
        default=0,
        help="Print and store the first N filtered points/clusters/tracks as coordinate previews",
    )
    parser.add_argument(
        "--coord-preview-every",
        type=int,
        default=1,
        help="Only print coordinate previews every Nth frame",
    )
    parser.add_argument(
        "--error-log-dir",
        default=str(DEFAULT_ERROR_LOG_DIR),
        help="Directory to store date-based markdown error logs",
    )
    parser.add_argument("--disable-error-log", action="store_true", help="Disable markdown error logging")

    args = parser.parse_args()

    try:
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
            filter_x_min=args.filter_x_min,
            filter_x_max=args.filter_x_max,
            filter_y_min=args.filter_y_min,
            filter_y_max=args.filter_y_max,
            filter_z_min=args.filter_z_min,
            filter_z_max=args.filter_z_max,
            disable_near_front_keepout=args.disable_near_front_keepout,
            near_front_distance=args.near_front_distance,
            near_front_half_width=args.near_front_half_width,
            near_front_z_min=args.near_front_z_min,
            near_front_z_max=args.near_front_z_max,
            disable_right_rail_keepout=args.disable_right_rail_keepout,
            right_rail_x=args.right_rail_x,
            right_rail_width=args.right_rail_width,
            right_rail_y_start=args.right_rail_y_start,
            right_rail_length=args.right_rail_length,
            right_rail_z_base=args.right_rail_z_base,
            right_rail_height=args.right_rail_height,
            right_rail_padding=args.right_rail_padding,
            disable_static_clutter_filter=args.disable_static_clutter_filter,
            static_clutter_padding=args.static_clutter_padding,
            static_v_min=args.static_v_min,
            static_max_snr=args.static_max_snr,
            filter_sample_count=args.filter_sample_count,
            dbscan_eps=args.dbscan_eps,
            dbscan_min_samples=args.dbscan_min_samples,
            use_velocity_feature=args.use_velocity_feature,
            association_gate=args.association_gate,
            max_misses=args.max_misses,
            min_hits=args.min_hits,
            report_miss_tolerance=args.report_miss_tolerance,
            scenario=args.scenario,
            roi_tag=args.roi_tag,
            log_dir=args.log_dir,
            disable_file_log=args.disable_file_log,
            coord_preview_count=args.coord_preview_count,
            coord_preview_every=args.coord_preview_every,
        )
    except Exception as exc:
        if not args.disable_error_log:
            error_log_path = append_error_log(args, exc, Path(args.error_log_dir))
            print(f"[ERROR_LOG] saved={error_log_path}")
        raise


if __name__ == "__main__":
    main()
