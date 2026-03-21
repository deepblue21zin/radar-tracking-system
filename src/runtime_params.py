"""Shared runtime parameter defaults and JSON loading helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_PARAMS_RELATIVE = Path("config") / "runtime_params.json"
DEFAULT_RUNTIME_PARAMS_PATH = PROJECT_ROOT / DEFAULT_RUNTIME_PARAMS_RELATIVE


GLOBAL_RUNTIME_PARAM_DEFAULTS: Dict[str, Any] = {
    "sensor_yaw_deg": 0.0,
    "sensor_pitch_deg": 0.0,
    "sensor_height_m": 0.0,
    "snr_threshold": 110.0,
    "max_noise": None,
    "min_range": 0.0,
    "max_range": 3.0,
    "filter_x_min": None,
    "filter_x_max": None,
    "filter_y_min": None,
    "filter_y_max": None,
    "filter_z_min": -0.6,
    "filter_z_max": 1.0,
    "disable_near_front_keepout": False,
    "near_front_distance": 0.3,
    "near_front_half_width": 1.1,
    "near_front_z_min": -0.5,
    "near_front_z_max": 1.5,
    "disable_right_rail_keepout": False,
    "right_rail_x": 1.8,
    "right_rail_width": 0.35,
    "right_rail_y_start": 0.0,
    "right_rail_length": 8.0,
    "right_rail_z_base": 0.0,
    "right_rail_height": 1.0,
    "right_rail_padding": 0.05,
    "disable_static_clutter_filter": False,
    "static_clutter_padding": 0.25,
    "static_v_min": 0.12,
    "static_max_snr": 180.0,
    "filter_sample_count": 2,
    "dbscan_eps": 0.35,
    "dbscan_min_samples": 3,
    "use_velocity_feature": False,
    "dbscan_velocity_weight": 0.25,
    "dbscan_adaptive_eps_bands": [
        {"r_min": 0.0, "r_max": 1.4, "eps": 0.22},
        {"r_min": 1.4, "r_max": None, "eps": 0.45},
    ],
    "association_gate": 1.5,
    "max_misses": 8,
    "min_hits": 2,
    "report_miss_tolerance": 0,
    "control_enabled": False,
    "control_zone_x_min": None,
    "control_zone_x_max": None,
    "control_zone_y_min": None,
    "control_zone_y_max": None,
    "control_zone_z_min": None,
    "control_zone_z_max": None,
    "control_slow_distance": 1.5,
    "control_stop_distance": 0.4,
    "control_resume_distance": 2.0,
    "control_slow_speed_ratio": 0.4,
    "control_approach_speed_threshold": 0.15,
    "control_stopped_speed_threshold": 0.06,
    "control_belt_axis_x": 0.0,
    "control_belt_axis_y": 1.0,
    "control_moving_confirm_sec": 0.3,
    "control_static_hold_sec": 0.8,
    "control_static_disp_window_sec": 0.8,
    "control_static_disp_threshold": 0.05,
    "control_clear_frames": 3,
    "control_out_port": None,
    "control_out_baudrate": 115200,
    "control_out_heartbeat_ms": 200,
    "scenario": "live_run",
    "roi_tag": "",
    "disable_file_log": False,
    "disable_text_log": False,
    "disable_overview_png": False,
    "experiment_title": "",
    "experiment_problem": "",
    "experiment_hypothesis": "",
    "experiment_change": "",
    "experiment_next_step": "",
    "coord_preview_count": 0,
    "coord_preview_every": 1,
    "x_min": -2.5,
    "x_max": 2.5,
    "y_min": 0.0,
    "y_max": 8.0,
    "z_min": -1.0,
    "z_max": 2.0,
    "max_vis_fps": 10.0,
    "point_persistence_frames": 6,
    "track_history_sec": 2.5,
    "track_history_points": 40,
    "velocity_arrow_scale": 0.8,
    "velocity_min_speed": 0.08,
}


def resolve_params_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()

    project_candidate = PROJECT_ROOT / path
    if project_candidate.exists() or path == DEFAULT_RUNTIME_PARAMS_RELATIVE:
        return project_candidate.resolve()

    return (Path.cwd() / path).resolve()


def _flatten_param_sections(data: Mapping[str, Any], flat: Dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            _flatten_param_sections(value, flat)
            continue

        if key in flat:
            raise ValueError(f"Duplicate runtime parameter key '{key}' in params file.")
        flat[key] = value


def load_runtime_param_overrides(path: str | Path) -> Tuple[Path, Dict[str, Any]]:
    resolved_path = resolve_params_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Runtime params file not found: {resolved_path}")

    try:
        raw_data = json.loads(resolved_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in runtime params file: {resolved_path}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError(f"Runtime params file must contain a JSON object: {resolved_path}")

    flat: Dict[str, Any] = {}
    _flatten_param_sections(raw_data, flat)

    unknown_keys = sorted(set(flat) - set(GLOBAL_RUNTIME_PARAM_DEFAULTS))
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ValueError(f"Unknown runtime parameter key(s) in {resolved_path}: {joined}")

    return resolved_path, flat


def resolve_runtime_param_defaults(
    argv: Sequence[str],
    selected_defaults: Mapping[str, Any],
) -> Tuple[Path, Dict[str, Any]]:
    preload_parser = argparse.ArgumentParser(add_help=False)
    preload_parser.add_argument("--params-file", default=str(DEFAULT_RUNTIME_PARAMS_RELATIVE))
    preload_args, _ = preload_parser.parse_known_args(list(argv))

    params_path, overrides = load_runtime_param_overrides(preload_args.params_file)
    merged = dict(selected_defaults)
    for key in selected_defaults:
        if key in overrides:
            merged[key] = overrides[key]

    return params_path, merged
