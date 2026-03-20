"""Generate a readable performance log markdown from runtime run summaries."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .runtime_experiment_report import analyze_frame_csv


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    if value in ("", None):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _relpath(target: Optional[str | Path], base_dir: Path) -> str:
    if target in ("", None):
        return ""
    return os.path.relpath(Path(target).resolve(), start=base_dir).replace("\\", "/")


def _format_delta(current: float, previous: float, digits: int = 2, better_when_lower: bool = False) -> str:
    delta = current - previous
    sign = "+" if delta >= 0 else ""
    direction = "same"
    if abs(delta) > 1e-9:
        improved = (delta < 0) if better_when_lower else (delta > 0)
        direction = "better" if improved else "worse"
    return f"{current:.{digits}f} ({sign}{delta:.{digits}f} vs prev, {direction})"


def _format_delta_int(current: int, previous: int, better_when_lower: bool = False) -> str:
    delta = current - previous
    sign = "+" if delta >= 0 else ""
    direction = "same"
    if delta != 0:
        improved = (delta < 0) if better_when_lower else (delta > 0)
        direction = "better" if improved else "worse"
    return f"{current} ({sign}{delta} vs prev, {direction})"


def _dominant_issue(metrics: Mapping[str, Any]) -> str:
    removed_range = _to_float(metrics.get("avg_removed_range"))
    removed_roi = _to_float(metrics.get("avg_removed_axis_roi"))
    removed_keepout = _to_float(metrics.get("avg_removed_keepout"))
    zero_track_frames = _to_int(metrics.get("zero_track_frames"))
    split_frames = _to_int(metrics.get("tracks_ge_2_frames"))
    frames_processed = max(1, _to_int(metrics.get("frames_processed")))

    candidates = [
        ("range gate", removed_range),
        ("ROI gate", removed_roi),
        ("keepout", removed_keepout),
        ("zero-track continuity", zero_track_frames / frames_processed),
        ("multi-track split", split_frames / frames_processed),
    ]
    label, value = max(candidates, key=lambda item: item[1])
    if label in {"zero-track continuity", "multi-track split"}:
        return label
    return f"{label} ({value:.2f} avg removed/frame)"


def _load_run_entries(run_summary_path: str | Path) -> List[Dict[str, Any]]:
    summary_path = Path(run_summary_path)
    rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8", newline="")))
    entries: List[Dict[str, Any]] = []

    for row in rows:
        frame_csv_path = row.get("frame_log_path", "")
        frame_analysis = {
            "frames": 0,
            "zero_track_frames": 0,
            "tracks_ge_2_frames": 0,
            "longest_zero_track_streak": None,
        }
        if frame_csv_path and Path(frame_csv_path).exists():
            frame_analysis = analyze_frame_csv(frame_csv_path)

        entry = dict(row)
        entry.update(frame_analysis)
        entries.append(entry)

    return entries


def render_performance_log(
    run_summary_path: str | Path,
    output_path: str | Path,
    experiment_report_root: str | Path,
) -> Path:
    entries = _load_run_entries(run_summary_path)
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_root = Path(experiment_report_root).resolve()

    lines = [
        "# Performance Log",
        "",
        "이 문서는 `run_summary.csv`와 frame CSV를 기준으로 자동 생성되는 성능 기록이다.",
        "표 대신 run별 핵심 변화, 이전 run 대비 증감, continuity/분할/제거 원인을 바로 읽을 수 있게 정리한다.",
        "",
    ]

    if not entries:
        lines.append("- 아직 기록된 run이 없다.")
        lines.append("")
        output_file.write_text("\n".join(lines), encoding="utf-8")
        return output_file

    latest = entries[-1]
    previous = entries[-2] if len(entries) >= 2 else None
    latest_run_id = str(latest.get("run_id", ""))
    latest_date = str(latest.get("started_at", datetime.now().isoformat()))[:10]

    lines.extend(
        [
            "## Latest Snapshot",
            f"- Latest run: `{latest_run_id}` ({latest_date})",
            f"- Scenario: `{latest.get('scenario', '')}`",
            f"- Avg FPS: `{latest.get('avg_fps', '')}`",
            f"- Parser health: `parse_fail={latest.get('parse_failures', '')}, resync={latest.get('resync_events', '')}, dropped={latest.get('dropped_frames_estimate', '')}`",
            f"- Tracking continuity: `zero_track={latest.get('zero_track_frames', '')}/{latest.get('frames_processed', '')}`, `tracks>=2={latest.get('tracks_ge_2_frames', '')}/{latest.get('frames_processed', '')}`",
            f"- Dominant issue: `{_dominant_issue(latest)}`",
            "",
        ]
    )

    if previous is not None:
        lines.extend(
            [
                "## Change Vs Previous",
                f"- Previous run: `{previous.get('run_id', '')}`",
                f"- Avg FPS: `{_format_delta(_to_float(latest.get('avg_fps')), _to_float(previous.get('avg_fps')), digits=3)}`",
                f"- Avg parser ms: `{_format_delta(_to_float(latest.get('avg_parser_latency_ms')), _to_float(previous.get('avg_parser_latency_ms')), better_when_lower=True)}`",
                f"- Avg pipeline ms: `{_format_delta(_to_float(latest.get('avg_pipeline_latency_ms')), _to_float(previous.get('avg_pipeline_latency_ms')), better_when_lower=True)}`",
                f"- Parse failures: `{_format_delta_int(_to_int(latest.get('parse_failures')), _to_int(previous.get('parse_failures')), better_when_lower=True)}`",
                f"- Resync events: `{_format_delta_int(_to_int(latest.get('resync_events')), _to_int(previous.get('resync_events')), better_when_lower=True)}`",
                f"- Dropped estimate: `{_format_delta_int(_to_int(latest.get('dropped_frames_estimate')), _to_int(previous.get('dropped_frames_estimate')), better_when_lower=True)}`",
                f"- Zero-track frames: `{_format_delta_int(_to_int(latest.get('zero_track_frames')), _to_int(previous.get('zero_track_frames')), better_when_lower=True)}`",
                f"- 2+ track frames: `{_format_delta_int(_to_int(latest.get('tracks_ge_2_frames')), _to_int(previous.get('tracks_ge_2_frames')), better_when_lower=True)}`",
                f"- Avg removed range: `{_format_delta(_to_float(latest.get('avg_removed_range')), _to_float(previous.get('avg_removed_range')), better_when_lower=True)}`",
                f"- Avg removed ROI: `{_format_delta(_to_float(latest.get('avg_removed_axis_roi')), _to_float(previous.get('avg_removed_axis_roi')), better_when_lower=True)}`",
                "",
            ]
        )

    lines.append("## Runs")
    lines.append("")

    for idx, entry in enumerate(reversed(entries), start=1):
        previous_entry = entries[-(idx + 1)] if idx < len(entries) else None
        run_id = str(entry.get("run_id", ""))
        started_date = str(entry.get("started_at", datetime.now().isoformat()))[:10]
        frame_csv_path = entry.get("frame_log_path", "")
        experiment_report_path = report_root / started_date / f"{run_id}.md"
        experiment_report_rel = _relpath(experiment_report_path, output_file.parent) if experiment_report_path.exists() else ""
        frame_csv_rel = _relpath(frame_csv_path, output_file.parent)

        lines.extend(
            [
                f"### {started_date} / {run_id}",
                f"- Scenario: `{entry.get('scenario', '')}`",
                f"- Summary: FPS `{entry.get('avg_fps', '')}`, parser/pipe `{entry.get('avg_parser_latency_ms', '')} / {entry.get('avg_pipeline_latency_ms', '')} ms`, raw->filtered `{entry.get('avg_raw_points', '')} -> {entry.get('avg_filtered_points', '')}`, avg tracks `{entry.get('avg_tracks', '')}`",
                f"- Parser health: `parse_fail={entry.get('parse_failures', '')}, resync={entry.get('resync_events', '')}, dropped={entry.get('dropped_frames_estimate', '')}`",
                f"- Continuity: `zero_track={entry.get('zero_track_frames', '')}/{entry.get('frames_processed', '')}`, `tracks>=2={entry.get('tracks_ge_2_frames', '')}/{entry.get('frames_processed', '')}`",
                f"- Filtering: `removed_range={entry.get('avg_removed_range', '')}`, `removed_roi={entry.get('avg_removed_axis_roi', '')}`, `removed_keepout={entry.get('avg_removed_keepout', '')}`",
            ]
        )

        streak = entry.get("longest_zero_track_streak")
        if streak:
            lines.append(f"- Longest zero-track streak: `frame {streak[0]}-{streak[1]} ({streak[2]} frames)`")

        lines.append(f"- Dominant issue: `{_dominant_issue(entry)}`")

        if previous_entry is not None:
            lines.append(
                f"- Change vs prev `{previous_entry.get('run_id', '')}`: parser fail `{_format_delta_int(_to_int(entry.get('parse_failures')), _to_int(previous_entry.get('parse_failures')), better_when_lower=True)}`, resync `{_format_delta_int(_to_int(entry.get('resync_events')), _to_int(previous_entry.get('resync_events')), better_when_lower=True)}`, zero-track `{_format_delta_int(_to_int(entry.get('zero_track_frames')), _to_int(previous_entry.get('zero_track_frames')), better_when_lower=True)}`"
            )

        if frame_csv_rel:
            lines.append(f"- Artifacts: frame CSV `{frame_csv_rel}`")
        if experiment_report_rel:
            lines.append(f"- Artifacts: experiment report `{experiment_report_rel}`")
        lines.append("")

    lines.extend(
        [
            "## Reading Guide",
            "- `Parser health`는 UART/parser 연속성 상태를 본다.",
            "- `Continuity`는 사람이 실제로 지속적으로 track로 남는지 본다.",
            "- `Filtering`은 range/ROI/keepout이 사람 점군을 얼마나 자르는지 본다.",
            "- `Dominant issue`는 현재 run에서 가장 먼저 의심할 병목을 자동으로 요약한다.",
            "",
            f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
            "",
        ]
    )

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file
