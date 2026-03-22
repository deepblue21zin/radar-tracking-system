"""Render a summary PNG from a runtime frame CSV log."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


_TRACK_PREVIEW_RE = re.compile(
    r"id=(?P<id>-?\d+), x=(?P<x>-?\d+\.\d+), y=(?P<y>-?\d+\.\d+), "
    r"vx=(?P<vx>-?\d+\.\d+), vy=(?P<vy>-?\d+\.\d+)"
)


def _safe_float(value: object) -> Optional[float]:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int:
    parsed = _safe_float(value)
    return int(parsed) if parsed is not None else 0


def _zero_value_streaks(values: Sequence[int], min_len: int = 20) -> List[Tuple[int, int]]:
    streaks: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for idx, value in enumerate(values):
        if value == 0:
            if start is None:
                start = idx
            continue
        if start is not None and idx - start >= min_len:
            streaks.append((start, idx - 1))
        start = None
    if start is not None and len(values) - start >= min_len:
        streaks.append((start, len(values) - 1))
    return streaks


def render_runtime_log_overview_png(csv_path: str | Path, output_path: str | Path | None = None) -> Path:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import Normalize
    except ImportError as exc:
        raise ImportError(
            "Runtime log PNG rendering requires matplotlib. Install it with `python -m pip install matplotlib`."
        ) from exc

    resolved_csv_path = Path(csv_path).resolve()
    if not resolved_csv_path.exists():
        raise FileNotFoundError(f"Runtime frame CSV not found: {resolved_csv_path}")

    resolved_output_path = (
        Path(output_path).resolve()
        if output_path is not None
        else resolved_csv_path.with_name(f"{resolved_csv_path.stem}_overview.png")
    )

    with resolved_csv_path.open(newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))

    if not rows:
        raise ValueError(f"Runtime frame CSV has no rows: {resolved_csv_path}")

    elapsed = [_safe_float(row.get("elapsed_sec")) or 0.0 for row in rows]
    raw_points = [_safe_int(row.get("raw_points")) for row in rows]
    filtered_points = [_safe_int(row.get("filtered_points")) for row in rows]
    clusters = [_safe_int(row.get("clusters")) for row in rows]
    tracks = [_safe_int(row.get("tracks")) for row in rows]
    removed_range = [_safe_int(row.get("removed_range")) for row in rows]
    removed_roi = [_safe_int(row.get("removed_axis_roi")) for row in rows]
    removed_keepout = [_safe_int(row.get("removed_keepout")) for row in rows]
    parser_ms = [_safe_float(row.get("parser_latency_ms")) or 0.0 for row in rows]
    pipeline_ms = [_safe_float(row.get("pipeline_latency_ms")) or 0.0 for row in rows]
    parse_failures = [_safe_int(row.get("parse_failures_so_far")) for row in rows]
    resync_events = [_safe_int(row.get("resync_events_so_far")) for row in rows]
    dropped_estimate = [_safe_int(row.get("dropped_frames_estimate_so_far")) for row in rows]
    filtered_range_min = [_safe_float(row.get("filtered_range_min")) for row in rows]
    filtered_range_max = [_safe_float(row.get("filtered_range_max")) for row in rows]
    filtered_range_min_plot = [value if value is not None else math.nan for value in filtered_range_min]
    filtered_range_max_plot = [value if value is not None else math.nan for value in filtered_range_max]
    zero_track_streaks = _zero_value_streaks(tracks, min_len=20)

    preview_points = []
    for row in rows:
        preview_text = (row.get("track_preview") or "").strip()
        if not preview_text:
            continue
        for match in _TRACK_PREVIEW_RE.finditer(preview_text):
            preview_points.append(
                {
                    "frame_number": _safe_int(row.get("frame_number")),
                    "elapsed_sec": _safe_float(row.get("elapsed_sec")) or 0.0,
                    "track_id": int(match.group("id")),
                    "x": float(match.group("x")),
                    "y": float(match.group("y")),
                    "vx": float(match.group("vx")),
                    "vy": float(match.group("vy")),
                }
            )

    figure = plt.figure(figsize=(16, 10), constrained_layout=True)
    grid = figure.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.05])
    ax_counts = figure.add_subplot(grid[0, 0])
    ax_range = figure.add_subplot(grid[0, 1])
    ax_removed = figure.add_subplot(grid[1, 0])
    ax_health = figure.add_subplot(grid[1, 1])
    ax_preview = figure.add_subplot(grid[2, :])

    ax_counts.plot(elapsed, raw_points, color="#9aa0a6", linewidth=1.0, label="raw points")
    ax_counts.plot(elapsed, filtered_points, color="#1f77b4", linewidth=1.2, label="filtered points")
    ax_counts.plot(elapsed, clusters, color="#d94841", linewidth=0.9, alpha=0.9, label="clusters")
    ax_counts.plot(elapsed, tracks, color="#2b8a3e", linewidth=0.9, alpha=0.9, label="tracks")
    for start_idx, end_idx in zero_track_streaks:
        ax_counts.axvspan(elapsed[start_idx], elapsed[end_idx], color="#fee2e2", alpha=0.35)
    ax_counts.set_title("Counts over time")
    ax_counts.set_xlabel("elapsed sec")
    ax_counts.set_ylabel("count")
    ax_counts.grid(alpha=0.25)
    ax_counts.legend(loc="upper right", fontsize=8)

    ax_range.plot(elapsed, filtered_range_min_plot, color="#0f766e", linewidth=1.2, label="filtered_range_min")
    ax_range.plot(elapsed, filtered_range_max_plot, color="#94a3b8", linewidth=1.0, alpha=0.9, label="filtered_range_max")
    for start_idx, end_idx in zero_track_streaks:
        ax_range.axvspan(elapsed[start_idx], elapsed[end_idx], color="#fee2e2", alpha=0.35)
    ax_range.set_title("Filtered range band")
    ax_range.set_xlabel("elapsed sec")
    ax_range.set_ylabel("meters")
    ax_range.grid(alpha=0.25)
    ax_range.legend(loc="upper right", fontsize=8)

    ax_removed.plot(elapsed, removed_range, color="#b91c1c", linewidth=1.1, label="removed_range")
    ax_removed.plot(elapsed, removed_roi, color="#7c3aed", linewidth=1.0, label="removed_roi")
    ax_removed.plot(elapsed, removed_keepout, color="#ea580c", linewidth=0.9, label="removed_keepout")
    ax_removed.set_title("Removal counts per frame")
    ax_removed.set_xlabel("elapsed sec")
    ax_removed.set_ylabel("points removed")
    ax_removed.grid(alpha=0.25)
    ax_removed.legend(loc="upper right", fontsize=8)

    ax_health.plot(elapsed, parser_ms, color="#2563eb", linewidth=0.9, alpha=0.9, label="parser ms")
    ax_health.plot(elapsed, pipeline_ms, color="#059669", linewidth=0.9, alpha=0.9, label="pipeline ms")
    ax_health_right = ax_health.twinx()
    ax_health_right.plot(elapsed, parse_failures, color="#dc2626", linewidth=1.0, linestyle="--", label="parse_failures")
    ax_health_right.plot(elapsed, resync_events, color="#7c2d12", linewidth=1.0, linestyle="--", label="resyncs")
    ax_health_right.plot(elapsed, dropped_estimate, color="#6d28d9", linewidth=1.0, linestyle="--", label="dropped_est")
    ax_health.set_title("Latency and parser health")
    ax_health.set_xlabel("elapsed sec")
    ax_health.set_ylabel("latency (ms)")
    ax_health_right.set_ylabel("cumulative events")
    ax_health.grid(alpha=0.25)
    health_lines, health_labels = ax_health.get_legend_handles_labels()
    health_right_lines, health_right_labels = ax_health_right.get_legend_handles_labels()
    ax_health.legend(health_lines + health_right_lines, health_labels + health_right_labels, loc="upper left", fontsize=8)

    if preview_points:
        preview_elapsed = [point["elapsed_sec"] for point in preview_points]
        scatter = ax_preview.scatter(
            [point["x"] for point in preview_points],
            [point["y"] for point in preview_points],
            c=preview_elapsed,
            cmap=plt.cm.viridis,
            s=30,
            alpha=0.85,
        )
        ax_preview.plot(
            [point["x"] for point in preview_points],
            [point["y"] for point in preview_points],
            color="#94a3b8",
            linewidth=0.8,
            alpha=0.45,
        )
        step = max(1, len(preview_points) // 10)
        for point in preview_points[::step]:
            ax_preview.text(point["x"], point["y"], str(point["frame_number"]), fontsize=7, color="#334155")
        color_bar = figure.colorbar(scatter, ax=ax_preview, pad=0.01)
        color_bar.set_label("elapsed sec")
    else:
        ax_preview.text(0.5, 0.5, "No track_preview data in CSV", ha="center", va="center", transform=ax_preview.transAxes)

    ax_preview.set_title("Track preview trajectory (sparse points from CSV preview)")
    ax_preview.set_xlabel("X (right +)")
    ax_preview.set_ylabel("Y (forward)")
    ax_preview.grid(alpha=0.25)
    ax_preview.set_aspect("equal", adjustable="box")

    rows_count = len(rows)
    avg_raw_points = sum(raw_points) / rows_count
    avg_filtered_points = sum(filtered_points) / rows_count
    avg_tracks = sum(tracks) / rows_count
    zero_track_frames = sum(1 for value in tracks if value == 0)
    avg_removed_range = sum(removed_range) / rows_count
    avg_removed_roi = sum(removed_roi) / rows_count

    summary_text = (
        f"frames={rows_count}  avg raw->filtered={avg_raw_points:.2f}->{avg_filtered_points:.2f}  "
        f"avg tracks={avg_tracks:.2f}  zero-track={zero_track_frames}/{rows_count}\n"
        f"avg removed range={avg_removed_range:.2f}  avg removed roi={avg_removed_roi:.2f}  "
        f"final parser health: fail={parse_failures[-1]} resync={resync_events[-1]} dropped={dropped_estimate[-1]}"
    )
    figure.suptitle(f"Run Overview: {resolved_csv_path.stem}", fontsize=16, y=1.02)
    figure.text(0.5, 0.995, summary_text, ha="center", va="top", fontsize=10)
    figure.savefig(resolved_output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return resolved_output_path
