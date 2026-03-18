"""Simple 3D live viewer for radar points, clusters, and tracks."""

import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import serial

try:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except ImportError as exc:
    raise ImportError(
        "live_rail_viewer requires matplotlib. Install it with `python -m pip install matplotlib`."
    ) from exc

try:
    from ..cluster.dbscan_cluster import cluster_points, normalize_adaptive_eps_bands
    from ..filter.noise_filter import points_dict_to_list, preprocess_points
    from ..parser.tlv_parse_runner import MMWaveSerialReader, build_keepout_boxes, build_static_clutter_boxes, send_config
    from ..tracking.kalman_tracker import MultiObjectKalmanTracker
    from ..runtime_params import GLOBAL_RUNTIME_PARAM_DEFAULTS, resolve_runtime_param_defaults
except ImportError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.cluster.dbscan_cluster import cluster_points, normalize_adaptive_eps_bands
    from src.filter.noise_filter import points_dict_to_list, preprocess_points
    from src.parser.tlv_parse_runner import MMWaveSerialReader, build_keepout_boxes, build_static_clutter_boxes, send_config
    from src.tracking.kalman_tracker import MultiObjectKalmanTracker
    from src.runtime_params import GLOBAL_RUNTIME_PARAM_DEFAULTS, resolve_runtime_param_defaults


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ERROR_LOG_DIR = PROJECT_ROOT / "docs" / "error"
VIEWER_PARAM_DEFAULT_KEYS = (
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
)
VIEWER_PARAM_DEFAULTS = {key: GLOBAL_RUNTIME_PARAM_DEFAULTS[key] for key in VIEWER_PARAM_DEFAULT_KEYS}


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


def build_arg_parser(defaults: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="3D live rail viewer for radar tracking debug")
    parser.add_argument("--params-file", default="config/runtime_params.json", help="JSON runtime parameter file")
    parser.add_argument("--cli-port", required=True, help="CLI port (e.g. COM11)")
    parser.add_argument("--data-port", required=True, help="Data port (e.g. COM10)")
    parser.add_argument("--config", required=True, help="Path to mmWave cfg file")
    parser.add_argument("--duration", type=int, default=None, help="Optional run duration in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable parser debug output")
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


def scatter_tracks(ax, tracks: Iterable[object]) -> None:
    track_list = list(tracks)
    if not track_list:
        return

    track_z = 0.15
    ax.scatter(
        [t.x for t in track_list],
        [t.y for t in track_list],
        [track_z] * len(track_list),
        c="#2b8a3e",
        s=110,
        marker="o",
        edgecolors="#14532d",
        linewidths=1.0,
        label="Tracks",
        depthshade=False,
    )
    for trk in track_list:
        ax.text(trk.x, trk.y, track_z + 0.06, f"T{trk.track_id}", color="#14532d", fontsize=9)


def add_legend(ax) -> None:
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#9aa0a6", markersize=6, label="Raw points"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4", markersize=6, label="Filtered points"),
        Line2D([0], [0], marker="x", color="#d94841", markersize=8, linewidth=0, label="Clusters"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2b8a3e", markeredgecolor="#14532d", markersize=8, label="Tracks"),
    ]
    ax.legend(handles=handles, loc="upper left")


def run_viewer(args: argparse.Namespace) -> None:
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection="3d")
    plt.ion()
    fig.show()

    tracker = MultiObjectKalmanTracker(
        association_gate=args.association_gate,
        max_misses=args.max_misses,
        min_hits=args.min_hits,
        report_miss_tolerance=args.report_miss_tolerance,
    )
    keepout_boxes = build_keepout_boxes(
        near_front_enabled=not args.disable_near_front_keepout,
        near_front_distance=args.near_front_distance,
        near_front_half_width=args.near_front_half_width,
        near_front_z_min=args.near_front_z_min,
        near_front_z_max=args.near_front_z_max,
        right_rail_enabled=not args.disable_right_rail_keepout,
        right_rail_x=args.right_rail_x,
        right_rail_width=args.right_rail_width,
        right_rail_y_start=args.right_rail_y_start,
        right_rail_length=args.right_rail_length,
        right_rail_z_base=args.right_rail_z_base,
        right_rail_height=args.right_rail_height,
        right_rail_padding=args.right_rail_padding,
    )
    static_clutter_boxes = build_static_clutter_boxes(
        enabled=not args.disable_static_clutter_filter,
        right_rail_x=args.right_rail_x,
        right_rail_width=args.right_rail_width,
        right_rail_y_start=args.right_rail_y_start,
        right_rail_length=args.right_rail_length,
        right_rail_z_base=args.right_rail_z_base,
        right_rail_height=args.right_rail_height,
        right_rail_padding=args.right_rail_padding,
        static_clutter_padding=args.static_clutter_padding,
    )

    with serial.Serial(args.cli_port, 115200, timeout=0.1) as cli_port, serial.Serial(
        args.data_port, 921600, timeout=0.05
    ) as data_port:
        send_config(cli_port, Path(args.config))
        time.sleep(0.2)
        data_port.reset_input_buffer()
        reader = MMWaveSerialReader(debug=args.debug)

        start_time = time.time()
        last_draw_time = 0.0

        try:
            while plt.fignum_exists(fig.number):
                frame = reader.read_frame(data_port)
                now = time.time()
                if args.duration is not None and (now - start_time) >= args.duration:
                    break

                if frame is None:
                    plt.pause(0.001)
                    continue

                raw_points = points_dict_to_list(frame.points, frame.num_obj)
                filtered_points, filter_stats = preprocess_points(
                    raw_points,
                    snr_threshold=args.snr_threshold,
                    max_noise=args.max_noise,
                    min_range=args.min_range,
                    max_range=args.max_range,
                    x_min=args.filter_x_min,
                    x_max=args.filter_x_max,
                    y_min=args.filter_y_min,
                    y_max=args.filter_y_max,
                    z_min=args.filter_z_min,
                    z_max=args.filter_z_max,
                    exclusion_boxes=keepout_boxes,
                    static_clutter_boxes=static_clutter_boxes,
                    static_v_min=args.static_v_min,
                    static_max_snr=args.static_max_snr,
                    return_stats=True,
                )
                clusters = cluster_points(
                    filtered_points,
                    eps=args.dbscan_eps,
                    min_samples=args.dbscan_min_samples,
                    use_velocity_feature=args.use_velocity_feature,
                    velocity_weight=args.dbscan_velocity_weight,
                    adaptive_eps_bands=args.dbscan_adaptive_eps_bands,
                )
                tracks = tracker.update(clusters, frame_ts=now)

                refresh_interval = 1.0 / max(args.max_vis_fps, 1.0)
                if (now - last_draw_time) < refresh_interval:
                    continue
                last_draw_time = now

                ax.cla()
                configure_axis(ax, args)
                draw_right_rail(ax, args)
                scatter_points(ax, raw_points, color="#9aa0a6", size=10, alpha=0.25, label="Raw")
                scatter_points(ax, filtered_points, color="#1f77b4", size=18, alpha=0.75, label="Filtered")
                scatter_clusters(ax, clusters)
                scatter_tracks(ax, tracks)
                add_legend(ax)
                ax.set_title(
                    f"frame={frame.frame_number} raw={len(raw_points)} filtered={len(filtered_points)} "
                    f"clusters={len(clusters)} tracks={len(tracks)} ratio={filter_stats.filter_ratio:.2f}"
                )
                fig.canvas.draw_idle()
                plt.pause(0.001)
        except KeyboardInterrupt:
            print("[VIEWER] stopped by user")
        finally:
            plt.ioff()
            plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    params_path, defaults = resolve_runtime_param_defaults(argv, VIEWER_PARAM_DEFAULTS)
    parser = build_arg_parser(defaults)
    args = parser.parse_args(argv)
    try:
        args.dbscan_adaptive_eps_bands = normalize_adaptive_eps_bands(args.dbscan_adaptive_eps_bands)
    except ValueError as exc:
        parser.error(str(exc))
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
