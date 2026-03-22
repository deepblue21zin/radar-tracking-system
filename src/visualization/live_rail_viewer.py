"""Simple 3D live viewer for radar points, clusters, and tracks."""

import argparse
from collections import deque
from dataclasses import dataclass
import math
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except ImportError as exc:
    raise ImportError(
        "live_rail_viewer requires matplotlib. Install it with `python -m pip install matplotlib`."
    ) from exc

try:
    from ..cluster.dbscan_cluster import normalize_adaptive_eps_bands
    from ..parser.runtime_pipeline import (
        RuntimeFrameHookPayload,
        run_realtime,
    )
    from ..runtime_params import GLOBAL_RUNTIME_PARAM_DEFAULTS, resolve_runtime_param_defaults
except ImportError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.cluster.dbscan_cluster import normalize_adaptive_eps_bands
    from src.parser.runtime_pipeline import (
        RuntimeFrameHookPayload,
        run_realtime,
    )
    from src.runtime_params import GLOBAL_RUNTIME_PARAM_DEFAULTS, resolve_runtime_param_defaults


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ERROR_LOG_DIR = PROJECT_ROOT / "docs" / "error"
VIEWER_PARAM_DEFAULT_KEYS = (
    "sensor_yaw_deg",
    "sensor_pitch_deg",
    "sensor_height_m",
    "snr_threshold",
    "max_noise",
    "min_range",
    "max_range",
    "filter_x_min",
    "filter_x_max",
    "filter_y_min",
    "filter_y_max",
    "filter_z_min",
    "filter_z_max",
    "disable_near_front_keepout",
    "near_front_distance",
    "near_front_half_width",
    "near_front_z_min",
    "near_front_z_max",
    "disable_right_rail_keepout",
    "right_rail_x",
    "right_rail_width",
    "right_rail_y_start",
    "right_rail_length",
    "right_rail_z_base",
    "right_rail_height",
    "right_rail_padding",
    "disable_static_clutter_filter",
    "static_clutter_padding",
    "static_v_min",
    "static_max_snr",
    "dbscan_eps",
    "dbscan_min_samples",
    "use_velocity_feature",
    "dbscan_velocity_weight",
    "dbscan_adaptive_eps_bands",
    "association_gate",
    "max_misses",
    "min_hits",
    "report_miss_tolerance",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
    "z_min",
    "z_max",
    "max_vis_fps",
    "point_persistence_frames",
    "track_history_sec",
    "track_history_points",
    "velocity_arrow_scale",
    "velocity_min_speed",
)
VIEWER_PARAM_DEFAULTS = {key: GLOBAL_RUNTIME_PARAM_DEFAULTS[key] for key in VIEWER_PARAM_DEFAULT_KEYS}

TRACK_COLOR_CYCLE = (
    "#2b8a3e",
    "#d94841",
    "#1d4ed8",
    "#b45309",
    "#7c3aed",
    "#0f766e",
    "#e11d48",
    "#0369a1",
)


@dataclass
class ViewerFrameSnapshot:
    frame_number: int
    frame_ts: float
    raw_points: List[dict]
    filtered_points: List[dict]
    clusters: List[dict]
    tracks: List[dict]
    filter_ratio: float
    removed_range: int
    removed_axis_roi: int
    removed_keepout: int
    removed_static_clutter: int
    parse_failures: int
    resync_events: int
    dropped_frames_estimate: int


def append_viewer_error_log(args: argparse.Namespace, exc: Exception, error_log_dir: Path) -> Path:
    error_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = error_log_dir / f"{datetime.now():%Y-%m-%d}.md"
    timestamp = datetime.now().isoformat(timespec="seconds")
    command = "python src/visualization/live_rail_viewer.py " + " ".join(sys.argv[1:])
    traceback_text = traceback.format_exc().strip()

    is_new_file = not log_path.exists()
    with log_path.open("a", encoding="utf-8") as fp:
        if is_new_file:
            fp.write(f"# {datetime.now():%Y-%m-%d} Error Log\n\n")
            fp.write("- 실행 중 발생한 오류를 날짜별로 누적 기록한다.\n")
            fp.write("- 같은 날짜에는 새 오류를 파일 아래쪽에 계속 추가한다.\n\n")

        fp.write(f"## Error {timestamp}\n")
        fp.write(f"- 명령: `{command}`\n")
        fp.write(f"- Params file: `{args.params_file}`\n")
        fp.write(f"- CLI port: `{args.cli_port}`\n")
        fp.write(f"- Data port: `{args.data_port}`\n")
        fp.write(f"- Config: `{args.config}`\n")
        fp.write("- Scenario: `live_viewer`\n")
        fp.write(f"- Error type: `{type(exc).__name__}`\n")
        fp.write(f"- Error message: `{exc}`\n\n")
        fp.write("```text\n")
        fp.write(traceback_text + "\n")
        fp.write("```\n\n")

    return log_path


def _track_value(track: object, key: str, default: float | int = 0.0):
    if isinstance(track, dict):
        return track.get(key, default)
    return getattr(track, key, default)


def build_viewer_snapshot(payload: RuntimeFrameHookPayload) -> ViewerFrameSnapshot:
    return ViewerFrameSnapshot(
        frame_number=int(payload.frame.frame_number),
        frame_ts=float(payload.frame_ts),
        raw_points=[dict(point) for point in payload.raw_points],
        filtered_points=[dict(point) for point in payload.filtered_points],
        clusters=[dict(cluster) for cluster in payload.clusters],
        tracks=[
            {
                "track_id": int(_track_value(track, "track_id", -1)),
                "x": float(_track_value(track, "x", 0.0)),
                "y": float(_track_value(track, "y", 0.0)),
                "vx": float(_track_value(track, "vx", 0.0)),
                "vy": float(_track_value(track, "vy", 0.0)),
                "confidence": float(_track_value(track, "confidence", 0.0)),
            }
            for track in payload.tracks
        ],
        filter_ratio=float(payload.filter_stats.filter_ratio),
        removed_range=int(payload.filter_stats.removed_range),
        removed_axis_roi=int(payload.filter_stats.removed_axis_roi),
        removed_keepout=int(payload.filter_stats.removed_keepout),
        removed_static_clutter=int(payload.filter_stats.removed_static_clutter),
        parse_failures=int(payload.reader_stats.parse_failures),
        resync_events=int(payload.reader_stats.resync_events),
        dropped_frames_estimate=int(payload.reader_stats.dropped_frames_estimate),
    )


class LatestRuntimeFrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_snapshot: Optional[ViewerFrameSnapshot] = None
        self._stop_requested = False
        self.worker_error: Optional[BaseException] = None

    def request_stop(self) -> None:
        with self._lock:
            self._stop_requested = True

    def should_stop(self) -> bool:
        with self._lock:
            return self._stop_requested

    def push_from_runtime(self, payload: RuntimeFrameHookPayload) -> Optional[bool]:
        if self.should_stop():
            return False
        snapshot = build_viewer_snapshot(payload)
        with self._lock:
            self._latest_snapshot = snapshot
        return True

    def latest_snapshot(self) -> Optional[ViewerFrameSnapshot]:
        with self._lock:
            return self._latest_snapshot


def build_arg_parser(defaults: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="3D live rail viewer for radar tracking debug")
    parser.add_argument("--params-file", default="config/runtime_params.json", help="JSON runtime parameter file")
    parser.add_argument("--cli-port", required=True, help="CLI port (e.g. COM11)")
    parser.add_argument("--data-port", required=True, help="Data port (e.g. COM10)")
    parser.add_argument("--config", required=True, help="Path to mmWave cfg file")
    parser.add_argument("--duration", type=int, default=None, help="Optional run duration in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable parser debug output")
    parser.add_argument("--sensor-yaw-deg", type=float, default=defaults["sensor_yaw_deg"], help="Planar sensor yaw rotation in degrees")
    parser.add_argument("--sensor-pitch-deg", type=float, default=defaults["sensor_pitch_deg"], help="Downward sensor pitch in degrees")
    parser.add_argument("--sensor-height-m", type=float, default=defaults["sensor_height_m"], help="Sensor mounting height in meters")
    parser.add_argument(
        "--error-log-dir",
        default=str(DEFAULT_ERROR_LOG_DIR),
        help="Directory for markdown error logs",
    )
    parser.add_argument("--disable-error-log", action="store_true", help="Disable markdown error logging")

    parser.add_argument("--snr-threshold", type=float, default=defaults["snr_threshold"], help="Minimum SNR for preprocessing")
    parser.add_argument("--max-noise", type=float, default=defaults["max_noise"], help="Maximum noise threshold")
    parser.add_argument("--min-range", type=float, default=defaults["min_range"], help="Minimum detection range")
    parser.add_argument("--max-range", type=float, default=defaults["max_range"], help="Maximum detection range")
    parser.add_argument("--filter-x-min", type=float, default=defaults["filter_x_min"], help="Inclusive filter ROI minimum X")
    parser.add_argument("--filter-x-max", type=float, default=defaults["filter_x_max"], help="Inclusive filter ROI maximum X")
    parser.add_argument("--filter-y-min", type=float, default=defaults["filter_y_min"], help="Inclusive filter ROI minimum Y")
    parser.add_argument("--filter-y-max", type=float, default=defaults["filter_y_max"], help="Inclusive filter ROI maximum Y")
    parser.add_argument("--filter-z-min", type=float, default=defaults["filter_z_min"], help="Inclusive filter ROI minimum Z")
    parser.add_argument("--filter-z-max", type=float, default=defaults["filter_z_max"], help="Inclusive filter ROI maximum Z")
    parser.add_argument("--disable-near-front-keepout", action="store_true", default=defaults["disable_near_front_keepout"], help="Disable near-front 1 m keepout box")
    parser.add_argument("--near-front-distance", type=float, default=defaults["near_front_distance"], help="Near-front keepout depth in meters")
    parser.add_argument("--near-front-half-width", type=float, default=defaults["near_front_half_width"], help="Half-width of near-front keepout box")
    parser.add_argument("--near-front-z-min", type=float, default=defaults["near_front_z_min"], help="Near-front keepout minimum Z")
    parser.add_argument("--near-front-z-max", type=float, default=defaults["near_front_z_max"], help="Near-front keepout maximum Z")
    parser.add_argument("--right-rail-padding", type=float, default=defaults["right_rail_padding"], help="Padding around right rail keepout")
    parser.add_argument("--disable-right-rail-keepout", action="store_true", default=defaults["disable_right_rail_keepout"], help="Disable right-rail keepout box")
    parser.add_argument("--disable-static-clutter-filter", action="store_true", default=defaults["disable_static_clutter_filter"], help="Disable low-velocity static clutter reject")
    parser.add_argument("--static-clutter-padding", type=float, default=defaults["static_clutter_padding"], help="Extra padding for static clutter box")
    parser.add_argument("--static-v-min", type=float, default=defaults["static_v_min"], help="Low-velocity threshold for static clutter reject")
    parser.add_argument("--static-max-snr", type=float, default=defaults["static_max_snr"], help="Only reject static clutter when SNR is at most this value")
    parser.add_argument("--dbscan-eps", type=float, default=defaults["dbscan_eps"], help="DBSCAN eps parameter")
    parser.add_argument("--dbscan-min-samples", type=int, default=defaults["dbscan_min_samples"], help="DBSCAN min_samples parameter")
    parser.add_argument("--use-velocity-feature", action="store_true", default=defaults["use_velocity_feature"], help="Use (x, y, v) DBSCAN features")
    parser.add_argument("--dbscan-velocity-weight", type=float, default=defaults["dbscan_velocity_weight"], help="Velocity scaling weight for DBSCAN")
    parser.add_argument(
        "--dbscan-adaptive-eps-bands",
        default=defaults["dbscan_adaptive_eps_bands"],
        help="Adaptive DBSCAN range bands in JSON or 'r_min:r_max:eps[:min_samples],...' format",
    )
    parser.add_argument("--association-gate", type=float, default=defaults["association_gate"], help="Tracker association gate in meters")
    parser.add_argument("--max-misses", type=int, default=defaults["max_misses"], help="Maximum consecutive misses before track deletion")
    parser.add_argument("--min-hits", type=int, default=defaults["min_hits"], help="Minimum hits before a track is reported")
    parser.add_argument(
        "--report-miss-tolerance",
        type=int,
        default=defaults["report_miss_tolerance"],
        help="Only draw tracks whose miss count is at most this value",
    )

    parser.add_argument("--x-min", type=float, default=defaults["x_min"], help="3D view minimum X")
    parser.add_argument("--x-max", type=float, default=defaults["x_max"], help="3D view maximum X")
    parser.add_argument("--y-min", type=float, default=defaults["y_min"], help="3D view minimum Y")
    parser.add_argument("--y-max", type=float, default=defaults["y_max"], help="3D view maximum Y")
    parser.add_argument("--z-min", type=float, default=defaults["z_min"], help="3D view minimum Z")
    parser.add_argument("--z-max", type=float, default=defaults["z_max"], help="3D view maximum Z")
    parser.add_argument("--max-vis-fps", type=float, default=defaults["max_vis_fps"], help="Maximum visualization refresh rate")
    parser.add_argument(
        "--point-persistence-frames",
        type=int,
        default=defaults["point_persistence_frames"],
        help="Number of recent filtered frames to keep for motion persistence",
    )
    parser.add_argument(
        "--track-history-sec",
        type=float,
        default=defaults["track_history_sec"],
        help="Seconds of track trail history to draw",
    )
    parser.add_argument(
        "--track-history-points",
        type=int,
        default=defaults["track_history_points"],
        help="Maximum stored points per track trail",
    )
    parser.add_argument(
        "--velocity-arrow-scale",
        type=float,
        default=defaults["velocity_arrow_scale"],
        help="Velocity arrow length scale in seconds",
    )
    parser.add_argument(
        "--velocity-min-speed",
        type=float,
        default=defaults["velocity_min_speed"],
        help="Minimum speed to draw a velocity arrow",
    )

    parser.add_argument("--rail-x", "--right-rail-x", dest="right_rail_x", type=float, default=defaults["right_rail_x"], help="Right rail center X position")
    parser.add_argument("--rail-width", "--right-rail-width", dest="right_rail_width", type=float, default=defaults["right_rail_width"], help="Right rail width")
    parser.add_argument("--rail-y-start", "--right-rail-y-start", dest="right_rail_y_start", type=float, default=defaults["right_rail_y_start"], help="Right rail start Y position")
    parser.add_argument("--rail-length", "--right-rail-length", dest="right_rail_length", type=float, default=defaults["right_rail_length"], help="Right rail length along Y")
    parser.add_argument("--rail-z-base", "--right-rail-z-base", dest="right_rail_z_base", type=float, default=defaults["right_rail_z_base"], help="Right rail base Z position")
    parser.add_argument("--rail-height", "--right-rail-height", dest="right_rail_height", type=float, default=defaults["right_rail_height"], help="Right rail height")
    return parser


def configure_axis(ax, args: argparse.Namespace) -> None:
    ax.set_xlim(args.x_min, args.x_max)
    ax.set_ylim(args.y_min, args.y_max)
    ax.set_zlim(args.z_min, args.z_max)
    ax.set_xlabel("X (right +)")
    ax.set_ylabel("Y (forward)")
    ax.set_zlabel("Z (up)")
    ax.view_init(elev=20, azim=-62)
    ax.set_box_aspect((args.x_max - args.x_min, args.y_max - args.y_min, args.z_max - args.z_min))


def configure_plan_axis(ax, args: argparse.Namespace) -> None:
    ax.set_xlim(args.x_min, args.x_max)
    ax.set_ylim(args.y_min, args.y_max)
    ax.set_xlabel("X (right +)")
    ax.set_ylabel("Y (forward)")
    ax.set_title("Top-down motion")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.28)


def draw_right_rail(ax, args: argparse.Namespace) -> None:
    x0 = args.right_rail_x - (args.right_rail_width / 2.0)
    x1 = args.right_rail_x + (args.right_rail_width / 2.0)
    y0 = args.right_rail_y_start
    y1 = args.right_rail_y_start + args.right_rail_length
    z0 = args.right_rail_z_base
    z1 = args.right_rail_z_base + args.right_rail_height

    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    faces = [
        [vertices[i] for i in [0, 1, 2, 3]],
        [vertices[i] for i in [4, 5, 6, 7]],
        [vertices[i] for i in [0, 1, 5, 4]],
        [vertices[i] for i in [1, 2, 6, 5]],
        [vertices[i] for i in [2, 3, 7, 6]],
        [vertices[i] for i in [3, 0, 4, 7]],
    ]

    rail = Poly3DCollection(faces, facecolors="#f08c2b", edgecolors="#c46b18", linewidths=0.8, alpha=0.18)
    ax.add_collection3d(rail)
    ax.text(args.right_rail_x, y1, z1 + 0.05, "Right Rail", color="#b55e12", fontsize=9, ha="center")


def draw_right_rail_plan(ax, args: argparse.Namespace) -> None:
    x0 = args.right_rail_x - (args.right_rail_width / 2.0)
    y0 = args.right_rail_y_start
    rail = Rectangle(
        (x0, y0),
        args.right_rail_width,
        args.right_rail_length,
        facecolor="#f08c2b",
        edgecolor="#c46b18",
        linewidth=1.2,
        alpha=0.18,
    )
    ax.add_patch(rail)
    ax.text(args.right_rail_x, y0 + args.right_rail_length + 0.12, "Right Rail", color="#b55e12", fontsize=9, ha="center")


def get_track_color(track_id: int) -> str:
    return TRACK_COLOR_CYCLE[(max(1, int(track_id)) - 1) % len(TRACK_COLOR_CYCLE)]


def build_track_z_map(tracks: Iterable[object], clusters: Iterable[dict], default_z: float = 0.15) -> Dict[int, float]:
    cluster_list = list(clusters)
    z_map: Dict[int, float] = {}
    for track in tracks:
        best_distance = float("inf")
        best_z = default_z
        for cluster in cluster_list:
            distance = math.hypot(
                float(_track_value(track, "x", 0.0)) - float(cluster["x"]),
                float(_track_value(track, "y", 0.0)) - float(cluster["y"]),
            )
            if distance < best_distance:
                best_distance = distance
                best_z = float(cluster.get("z", default_z))
        z_map[int(_track_value(track, "track_id", -1))] = best_z if best_distance <= 1.5 else default_z
    return z_map


def update_track_history(
    history: Dict[int, Deque[Tuple[float, float, float, float]]],
    tracks: Iterable[object],
    track_z_map: Dict[int, float],
    frame_ts: float,
    history_sec: float,
    max_points: int,
) -> None:
    cutoff = frame_ts - history_sec
    for track in tracks:
        track_id = int(_track_value(track, "track_id", -1))
        trail = history.get(track_id)
        if trail is None or trail.maxlen != max_points:
            trail = deque(trail or [], maxlen=max_points)
            history[track_id] = trail
        trail.append(
            (
                frame_ts,
                float(_track_value(track, "x", 0.0)),
                float(_track_value(track, "y", 0.0)),
                float(track_z_map.get(track_id, 0.15)),
            )
        )

    stale_track_ids: List[int] = []
    for track_id, trail in history.items():
        while trail and trail[0][0] < cutoff:
            trail.popleft()
        if not trail:
            stale_track_ids.append(track_id)

    for track_id in stale_track_ids:
        history.pop(track_id, None)


def scatter_points(ax, points: Iterable[dict], color: str, size: float, alpha: float, label: str) -> None:
    point_list = list(points)
    if not point_list:
        return
    ax.scatter(
        [p["x"] for p in point_list],
        [p["y"] for p in point_list],
        [p.get("z", 0.0) for p in point_list],
        c=color,
        s=size,
        alpha=alpha,
        label=label,
        depthshade=False,
    )


def scatter_points_plan(ax, points: Iterable[dict], color: str, size: float, alpha: float, label: str = "") -> None:
    point_list = list(points)
    if not point_list:
        return
    ax.scatter(
        [p["x"] for p in point_list],
        [p["y"] for p in point_list],
        c=color,
        s=size,
        alpha=alpha,
        label=label or None,
    )


def scatter_persistent_points_3d(ax, history: Deque[List[dict]]) -> None:
    frame_list = list(history)
    if len(frame_list) <= 1:
        return

    older_frames = frame_list[:-1]
    total = len(older_frames)
    for index, points in enumerate(older_frames, start=1):
        if not points:
            continue
        weight = index / max(total, 1)
        ax.scatter(
            [p["x"] for p in points],
            [p["y"] for p in points],
            [p.get("z", 0.0) for p in points],
            c="#74a9cf",
            s=7 + (5 * weight),
            alpha=0.05 + (0.18 * weight),
            depthshade=False,
        )


def scatter_persistent_points_plan(ax, history: Deque[List[dict]]) -> None:
    frame_list = list(history)
    if len(frame_list) <= 1:
        return

    older_frames = frame_list[:-1]
    total = len(older_frames)
    for index, points in enumerate(older_frames, start=1):
        if not points:
            continue
        weight = index / max(total, 1)
        ax.scatter(
            [p["x"] for p in points],
            [p["y"] for p in points],
            c="#74a9cf",
            s=7 + (4 * weight),
            alpha=0.05 + (0.16 * weight),
        )


def scatter_clusters(ax, clusters: List[dict]) -> None:
    if not clusters:
        return
    ax.scatter(
        [c["x"] for c in clusters],
        [c["y"] for c in clusters],
        [c.get("z", 0.0) for c in clusters],
        c="#d94841",
        s=90,
        marker="x",
        linewidths=2.0,
        label="Clusters",
        depthshade=False,
    )


def scatter_clusters_plan(ax, clusters: List[dict]) -> None:
    if not clusters:
        return
    ax.scatter(
        [c["x"] for c in clusters],
        [c["y"] for c in clusters],
        c="#d94841",
        s=70,
        marker="x",
        linewidths=2.0,
    )


def draw_track_trails_3d(ax, history: Dict[int, Deque[Tuple[float, float, float, float]]]) -> None:
    for track_id, trail in history.items():
        if len(trail) < 2:
            continue
        color = get_track_color(track_id)
        xs = [sample[1] for sample in trail]
        ys = [sample[2] for sample in trail]
        zs = [sample[3] for sample in trail]
        ax.plot(xs, ys, zs, color=color, linewidth=2.2, alpha=0.85)


def draw_track_trails_plan(ax, history: Dict[int, Deque[Tuple[float, float, float, float]]]) -> None:
    for track_id, trail in history.items():
        if len(trail) < 2:
            continue
        color = get_track_color(track_id)
        xs = [sample[1] for sample in trail]
        ys = [sample[2] for sample in trail]
        ax.plot(xs, ys, color=color, linewidth=2.2, alpha=0.85)


def scatter_tracks(ax, tracks: Iterable[object], track_z_map: Dict[int, float], args: argparse.Namespace) -> None:
    track_list = list(tracks)
    if not track_list:
        return

    for trk in track_list:
        track_id = int(_track_value(trk, "track_id", -1))
        color = get_track_color(track_id)
        track_z = float(track_z_map.get(track_id, 0.15))
        track_x = float(_track_value(trk, "x", 0.0))
        track_y = float(_track_value(trk, "y", 0.0))
        track_vx = float(_track_value(trk, "vx", 0.0))
        track_vy = float(_track_value(trk, "vy", 0.0))
        speed = math.hypot(track_vx, track_vy)
        ax.scatter(
            [track_x],
            [track_y],
            [track_z],
            c=color,
            s=120,
            marker="o",
            edgecolors="#14532d",
            linewidths=1.0,
            depthshade=False,
        )
        if speed >= args.velocity_min_speed:
            ax.quiver(
                track_x,
                track_y,
                track_z,
                track_vx * args.velocity_arrow_scale,
                track_vy * args.velocity_arrow_scale,
                0.0,
                color=color,
                linewidth=1.6,
                alpha=0.95,
                arrow_length_ratio=0.22,
            )
        ax.text(
            track_x,
            track_y,
            track_z + 0.08,
            f"T{track_id} {speed:.2f}m/s",
            color=color,
            fontsize=9,
        )


def scatter_tracks_plan(ax, tracks: Iterable[object], args: argparse.Namespace) -> None:
    track_list = list(tracks)
    if not track_list:
        return

    for trk in track_list:
        track_id = int(_track_value(trk, "track_id", -1))
        color = get_track_color(track_id)
        track_x = float(_track_value(trk, "x", 0.0))
        track_y = float(_track_value(trk, "y", 0.0))
        track_vx = float(_track_value(trk, "vx", 0.0))
        track_vy = float(_track_value(trk, "vy", 0.0))
        speed = math.hypot(track_vx, track_vy)
        ax.scatter([track_x], [track_y], c=color, s=95, edgecolors="#14532d", linewidths=1.0, zorder=5)
        if speed >= args.velocity_min_speed:
            ax.quiver(
                [track_x],
                [track_y],
                [track_vx * args.velocity_arrow_scale],
                [track_vy * args.velocity_arrow_scale],
                angles="xy",
                scale_units="xy",
                scale=1.0,
                color=color,
                width=0.004,
                alpha=0.95,
                zorder=4,
            )
        ax.text(track_x + 0.04, track_y + 0.04, f"T{track_id} {speed:.2f}m/s", color=color, fontsize=9)


def add_legend(ax) -> None:
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#9aa0a6", markersize=6, label="Raw points"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#74a9cf", markersize=6, label="Motion cloud"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4", markersize=6, label="Current filtered"),
        Line2D([0], [0], marker="x", color="#d94841", markersize=8, linewidth=0, label="Clusters"),
        Line2D([0], [0], color="#2b8a3e", linewidth=2.2, label="Track trails"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2b8a3e", markeredgecolor="#14532d", markersize=8, label="Tracks / velocity"),
    ]
    ax.legend(handles=handles, loc="upper left")


def add_status_overlay(ax, args: argparse.Namespace, snapshot: ViewerFrameSnapshot) -> None:
    lines = [
        f"max_range={args.max_range if args.max_range is not None else 'inf'} m",
        f"sensor_yaw={args.sensor_yaw_deg:.1f} deg",
        f"sensor_pitch={args.sensor_pitch_deg:.1f} deg height={args.sensor_height_m:.2f} m",
        (
            f"removed range={snapshot.removed_range} "
            f"roi={snapshot.removed_axis_roi} "
            f"keepout={snapshot.removed_keepout} "
            f"static={snapshot.removed_static_clutter}"
        ),
        (
            f"parser fail={snapshot.parse_failures} "
            f"resync={snapshot.resync_events} "
            f"dropped={snapshot.dropped_frames_estimate}"
        ),
    ]
    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        color="#1f2937",
        bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.92},
    )


class LiveRuntimeFrameRenderer:
    """Matplotlib renderer that draws the latest runtime snapshot."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.fig = plt.figure(figsize=(15, 7))
        self.ax_3d = self.fig.add_subplot(121, projection="3d")
        self.ax_plan = self.fig.add_subplot(122)
        self.fig.subplots_adjust(top=0.90, wspace=0.08)
        plt.ion()
        self.fig.show()
        self.filtered_history: Deque[List[dict]] = deque(maxlen=max(1, args.point_persistence_frames))
        self.track_history: Dict[int, Deque[Tuple[float, float, float, float]]] = {}
        self.last_draw_time = 0.0
        self.last_rendered_frame_number = -1

    def close(self) -> None:
        plt.ioff()
        plt.close(self.fig)

    def draw_snapshot(self, snapshot: ViewerFrameSnapshot) -> Optional[bool]:
        if not plt.fignum_exists(self.fig.number):
            return False

        if snapshot.frame_number == self.last_rendered_frame_number:
            return True

        refresh_interval = 1.0 / max(self.args.max_vis_fps, 1.0)
        if (snapshot.frame_ts - self.last_draw_time) < refresh_interval:
            return True
        self.last_draw_time = snapshot.frame_ts
        self.last_rendered_frame_number = snapshot.frame_number

        self.filtered_history.append([dict(point) for point in snapshot.filtered_points])
        track_z_map = build_track_z_map(snapshot.tracks, snapshot.clusters)
        update_track_history(
            self.track_history,
            snapshot.tracks,
            track_z_map,
            snapshot.frame_ts,
            history_sec=self.args.track_history_sec,
            max_points=self.args.track_history_points,
        )

        self.ax_3d.cla()
        self.ax_plan.cla()
        configure_axis(self.ax_3d, self.args)
        configure_plan_axis(self.ax_plan, self.args)
        draw_right_rail(self.ax_3d, self.args)
        draw_right_rail_plan(self.ax_plan, self.args)
        scatter_points(self.ax_3d, snapshot.raw_points, color="#9aa0a6", size=10, alpha=0.12, label="Raw")
        scatter_persistent_points_3d(self.ax_3d, self.filtered_history)
        scatter_points(
            self.ax_3d,
            snapshot.filtered_points,
            color="#1f77b4",
            size=20,
            alpha=0.82,
            label="Filtered",
        )
        scatter_clusters(self.ax_3d, snapshot.clusters)
        draw_track_trails_3d(self.ax_3d, self.track_history)
        scatter_tracks(self.ax_3d, snapshot.tracks, track_z_map, self.args)
        add_legend(self.ax_3d)

        scatter_points_plan(self.ax_plan, snapshot.raw_points, color="#9aa0a6", size=10, alpha=0.10)
        scatter_persistent_points_plan(self.ax_plan, self.filtered_history)
        scatter_points_plan(self.ax_plan, snapshot.filtered_points, color="#1f77b4", size=16, alpha=0.80)
        scatter_clusters_plan(self.ax_plan, snapshot.clusters)
        draw_track_trails_plan(self.ax_plan, self.track_history)
        scatter_tracks_plan(self.ax_plan, snapshot.tracks, self.args)
        add_status_overlay(self.ax_plan, self.args, snapshot)

        self.ax_3d.set_title("3D space")
        self.fig.suptitle(
            f"frame={snapshot.frame_number} raw={len(snapshot.raw_points)} "
            f"filtered={len(snapshot.filtered_points)} clusters={len(snapshot.clusters)} "
            f"tracks={len(snapshot.tracks)} ratio={snapshot.filter_ratio:.2f}",
            fontsize=16,
        )
        self.fig.canvas.draw_idle()
        return True


def _runtime_worker(args: argparse.Namespace, frame_buffer: LatestRuntimeFrameBuffer) -> None:
    try:
        run_realtime(
            cli_port_name=args.cli_port,
            data_port_name=args.data_port,
            config_file=args.config,
            duration_sec=args.duration,
            debug=args.debug,
            sensor_yaw_deg=args.sensor_yaw_deg,
            sensor_pitch_deg=args.sensor_pitch_deg,
            sensor_height_m=args.sensor_height_m,
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
            dbscan_eps=args.dbscan_eps,
            dbscan_min_samples=args.dbscan_min_samples,
            use_velocity_feature=args.use_velocity_feature,
            dbscan_velocity_weight=args.dbscan_velocity_weight,
            dbscan_adaptive_eps_bands=args.dbscan_adaptive_eps_bands,
            association_gate=args.association_gate,
            max_misses=args.max_misses,
            min_hits=args.min_hits,
            report_miss_tolerance=args.report_miss_tolerance,
            scenario="live_viewer",
            disable_file_log=True,
            params_file=args.params_file,
            console_output=False,
            frame_hook=frame_buffer.push_from_runtime,
        )
    except BaseException as exc:
        frame_buffer.worker_error = exc
    finally:
        frame_buffer.request_stop()


def run_viewer(args: argparse.Namespace) -> None:
    frame_buffer = LatestRuntimeFrameBuffer()
    renderer = LiveRuntimeFrameRenderer(args)
    worker = threading.Thread(
        target=_runtime_worker,
        args=(args, frame_buffer),
        name="live-runtime-worker",
        daemon=True,
    )
    worker.start()
    try:
        while True:
            if not plt.fignum_exists(renderer.fig.number):
                frame_buffer.request_stop()
                break

            snapshot = frame_buffer.latest_snapshot()
            if snapshot is not None:
                renderer.draw_snapshot(snapshot)

            plt.pause(0.001)

            if frame_buffer.should_stop() and not worker.is_alive():
                latest_snapshot = frame_buffer.latest_snapshot()
                if latest_snapshot is None or latest_snapshot.frame_number == renderer.last_rendered_frame_number:
                    break
    except KeyboardInterrupt:
        frame_buffer.request_stop()
        print("[VIEWER] stopped by user")
    finally:
        worker.join(timeout=1.0)
        if frame_buffer.worker_error is not None and not isinstance(frame_buffer.worker_error, KeyboardInterrupt):
            raise frame_buffer.worker_error
        renderer.close()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    params_path, defaults = resolve_runtime_param_defaults(argv, VIEWER_PARAM_DEFAULTS)
    parser = build_arg_parser(defaults)
    args = parser.parse_args(argv)
    try:
        args.dbscan_adaptive_eps_bands = normalize_adaptive_eps_bands(args.dbscan_adaptive_eps_bands)
    except ValueError as exc:
        parser.error(str(exc))
    args.point_persistence_frames = max(1, int(args.point_persistence_frames))
    args.track_history_sec = max(0.5, float(args.track_history_sec))
    args.track_history_points = max(2, int(args.track_history_points))
    args.velocity_arrow_scale = max(0.05, float(args.velocity_arrow_scale))
    args.velocity_min_speed = max(0.0, float(args.velocity_min_speed))
    args.params_file = str(params_path)
    return args


def main() -> None:
    args = parse_args()
    try:
        run_viewer(args)
    except Exception as exc:
        if not args.disable_error_log:
            error_log_path = append_viewer_error_log(args, exc, Path(args.error_log_dir))
            print(f"[ERROR_LOG] saved={error_log_path}")
        raise


if __name__ == "__main__":
    main()
