"""Generate structured runtime experiment markdown reports from run artifacts."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


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
    target_path = Path(target).resolve()
    return os.path.relpath(target_path, start=base_dir).replace("\\", "/")


def analyze_frame_csv(frame_csv_path: str | Path) -> Dict[str, Any]:
    path = Path(frame_csv_path)
    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    if not rows:
        return {
            "frames": 0,
            "zero_track_frames": 0,
            "tracks_ge_2_frames": 0,
            "longest_zero_track_streak": None,
        }

    tracks = [_to_int(row.get("tracks")) for row in rows]
    frame_numbers = [_to_int(row.get("frame_number")) for row in rows]

    streaks = []
    start_frame: Optional[int] = None
    last_frame: Optional[int] = None
    for frame_number, track_count in zip(frame_numbers, tracks):
        if track_count == 0 and start_frame is None:
            start_frame = frame_number
        if track_count != 0 and start_frame is not None:
            streaks.append((start_frame, last_frame or start_frame, (last_frame or start_frame) - start_frame + 1))
            start_frame = None
        last_frame = frame_number

    if start_frame is not None:
        streaks.append((start_frame, last_frame or start_frame, (last_frame or start_frame) - start_frame + 1))

    streaks.sort(key=lambda item: item[2], reverse=True)

    return {
        "frames": len(rows),
        "zero_track_frames": sum(1 for value in tracks if value == 0),
        "tracks_ge_2_frames": sum(1 for value in tracks if value >= 2),
        "longest_zero_track_streak": streaks[0] if streaks else None,
    }


def _build_auto_findings(summary: Mapping[str, Any], frame_analysis: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []

    parse_failures = _to_int(summary.get("parse_failures"))
    resync_events = _to_int(summary.get("resync_events"))
    dropped_estimate = _to_int(summary.get("dropped_frames_estimate"))
    avg_removed_range = _to_float(summary.get("avg_removed_range"))
    avg_removed_roi = _to_float(summary.get("avg_removed_axis_roi"))
    avg_removed_keepout = _to_float(summary.get("avg_removed_keepout"))
    avg_parser_ms = _to_float(summary.get("avg_parser_latency_ms"))
    avg_pipeline_ms = _to_float(summary.get("avg_pipeline_latency_ms"))
    avg_tracks = _to_float(summary.get("avg_tracks"))
    frames_processed = max(1, _to_int(summary.get("frames_processed")))
    zero_track_frames = _to_int(frame_analysis.get("zero_track_frames"))
    tracks_ge_2_frames = _to_int(frame_analysis.get("tracks_ge_2_frames"))

    if parse_failures or resync_events or dropped_estimate:
        findings.append(
            f"Parser continuity summary: parse_fail={parse_failures}, resync={resync_events}, dropped={dropped_estimate}."
        )
    else:
        findings.append("Parser continuity summary: parse_fail/resync/dropped were all zero in this run.")

    dominant_filters = [
        ("range gate", avg_removed_range),
        ("ROI gate", avg_removed_roi),
        ("keepout", avg_removed_keepout),
    ]
    dominant_filter, dominant_value = max(dominant_filters, key=lambda item: item[1])
    if dominant_value > 0.0:
        findings.append(f"Filtering impact: {dominant_filter} was the largest average removal source ({dominant_value:.2f} points/frame).")

    if zero_track_frames > 0:
        zero_ratio = zero_track_frames / frames_processed
        findings.append(
            f"Tracking continuity: zero-track frames were {zero_track_frames}/{frames_processed} ({zero_ratio:.1%})."
        )

    longest_streak = frame_analysis.get("longest_zero_track_streak")
    if longest_streak is not None:
        start_frame, end_frame, length = longest_streak
        findings.append(f"Longest zero-track streak: frame {start_frame}-{end_frame} ({length} frames).")

    if tracks_ge_2_frames > 0:
        split_ratio = tracks_ge_2_frames / frames_processed
        findings.append(
            f"Multi-target tendency: frames with 2+ tracks were {tracks_ge_2_frames}/{frames_processed} ({split_ratio:.1%}), which can indicate human-body splitting."
        )

    findings.append(
        f"Latency summary: avg parser={avg_parser_ms:.2f} ms, avg pipeline={avg_pipeline_ms:.2f} ms, avg tracks={avg_tracks:.2f}."
    )
    return findings


def render_runtime_experiment_report(
    summary: Mapping[str, Any],
    frame_csv_path: str | Path,
    report_root: str | Path,
    text_log_path: str | Path | None = None,
    overview_png_path: str | Path | None = None,
    experiment_title: str = "",
    experiment_problem: str = "",
    experiment_hypothesis: str = "",
    experiment_change: str = "",
    experiment_next_step: str = "",
) -> Path:
    report_root_path = Path(report_root).resolve()
    report_date = str(summary.get("started_at", datetime.now().isoformat()))[:10]
    run_id = str(summary.get("run_id", "unknown_run"))
    report_dir = report_root_path / report_date
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}.md"

    frame_analysis = analyze_frame_csv(frame_csv_path)
    auto_findings = _build_auto_findings(summary, frame_analysis)

    frame_csv_rel = _relpath(frame_csv_path, report_dir)
    text_log_rel = _relpath(text_log_path, report_dir)
    overview_png_rel = _relpath(overview_png_path, report_dir)
    params_file_rel = _relpath(summary.get("params_file"), report_dir)
    config_file_rel = _relpath(summary.get("config_file"), report_dir)

    problem_text = experiment_problem.strip() or "[직접 입력] 이 run에서 눈으로 본 문제/현상을 적는다."
    hypothesis_text = experiment_hypothesis.strip() or "[직접 입력] 왜 이런 문제가 생겼다고 생각하는지 적는다."
    change_text = experiment_change.strip() or "[직접 입력] 이번 run 전에 어떤 파라미터/코드/설치를 바꿨는지 적는다."
    next_step_text = experiment_next_step.strip() or "[직접 입력] 다음 run에서 무엇을 바꿔볼지 적는다."

    lines = [
        f"# Experiment Report {run_id}",
        "",
        f"- Title: {experiment_title.strip() or run_id}",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Scenario: `{summary.get('scenario', '')}`",
        f"- ROI tag: `{summary.get('roi_tag', '')}`",
        f"- Config: `{config_file_rel or summary.get('config_file', '')}`",
        f"- Params: `{params_file_rel or summary.get('params_file', '')}`",
        "",
        "## 1. Problem Check",
        f"- Problem: {problem_text}",
        "- Auto findings:",
    ]
    lines.extend([f"  - {finding}" for finding in auto_findings])
    lines.extend(
        [
            "",
            "## 2. Hypothesis",
            f"- Hypothesis: {hypothesis_text}",
            "",
            "## 3. Change Applied",
            f"- Change: {change_text}",
            "",
            "## 4. Verification",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Frames processed | {summary.get('frames_processed', '')} |",
            f"| Avg FPS | {summary.get('avg_fps', '')} |",
            f"| Avg parser latency (ms) | {summary.get('avg_parser_latency_ms', '')} |",
            f"| Avg pipeline latency (ms) | {summary.get('avg_pipeline_latency_ms', '')} |",
            f"| Avg raw points | {summary.get('avg_raw_points', '')} |",
            f"| Avg filtered points | {summary.get('avg_filtered_points', '')} |",
            f"| Avg clusters | {summary.get('avg_clusters', '')} |",
            f"| Avg tracks | {summary.get('avg_tracks', '')} |",
            f"| Avg removed range | {summary.get('avg_removed_range', '')} |",
            f"| Avg removed ROI | {summary.get('avg_removed_axis_roi', '')} |",
            f"| Parse failures | {summary.get('parse_failures', '')} |",
            f"| Resync events | {summary.get('resync_events', '')} |",
            f"| Dropped frame estimate | {summary.get('dropped_frames_estimate', '')} |",
            f"| Zero-track frames | {frame_analysis.get('zero_track_frames', '')} |",
            f"| 2+ track frames | {frame_analysis.get('tracks_ge_2_frames', '')} |",
            "",
            "## 5. Artifacts",
            f"- Frame CSV: `{frame_csv_rel}`",
            f"- Text log: `{text_log_rel}`" if text_log_rel else "- Text log: not generated",
            f"- Overview PNG: `{overview_png_rel}`" if overview_png_rel else "- Overview PNG: not generated",
            "",
            "## 6. Next Hypothesis / Next Step",
            f"- Next step: {next_step_text}",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def update_experiment_report_index(report_root: str | Path) -> Path:
    report_root_path = Path(report_root).resolve()
    report_root_path.mkdir(parents=True, exist_ok=True)
    index_path = report_root_path / "README.md"

    report_files = sorted(
        (
            path
            for path in report_root_path.rglob("*.md")
            if path.name.lower() != "readme.md"
        ),
        key=lambda path: path.as_posix(),
    )

    lines = [
        "# Experiment Reports",
        "",
        "자동 생성된 run별 실험 리포트 목록이다.",
        "",
        "| Date | Run ID | File |",
        "|---|---|---|",
    ]
    for path in report_files:
        run_id = path.stem
        date_part = path.parent.name
        rel_path = os.path.relpath(path, start=report_root_path).replace("\\", "/")
        lines.append(f"| {date_part} | `{run_id}` | `{rel_path}` |")

    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path
