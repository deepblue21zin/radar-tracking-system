"""Runtime frame processing helpers kept separate from serial orchestration."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import time
from typing import List, Optional

try:
    from ..cluster.dbscan_cluster import cluster_points, normalize_adaptive_eps_bands
    from ..filter.noise_filter import AxisAlignedBox, points_dict_to_list, preprocess_points
    from ..tracking.kalman_tracker import MultiObjectKalmanTracker
    from .models import ParsedFrame, RuntimeFrameProcessingResult, RuntimeProcessingContext
except ImportError:
    src_root = Path(__file__).resolve().parents[1]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from cluster.dbscan_cluster import cluster_points, normalize_adaptive_eps_bands
    from filter.noise_filter import AxisAlignedBox, points_dict_to_list, preprocess_points
    from tracking.kalman_tracker import MultiObjectKalmanTracker
    from runtime.models import ParsedFrame, RuntimeFrameProcessingResult, RuntimeProcessingContext


def transform_points_to_world(
    points: List[dict],
    yaw_deg: float = 0.0,
    pitch_deg: float = 0.0,
    sensor_height_m: float = 0.0,
) -> List[dict]:
    if not points:
        return points

    yaw_rad = math.radians(float(yaw_deg))
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)
    pitch_rad = math.radians(float(pitch_deg))
    cos_pitch = math.cos(pitch_rad)
    sin_pitch = math.sin(pitch_rad)
    transformed_points: List[dict] = []
    for point in points:
        x_val = float(point.get("x", 0.0))
        y_val = float(point.get("y", 0.0))
        z_val = float(point.get("z", 0.0))

        # Positive pitch means the sensor is tilted downward. Convert the
        # sensor-frame point into a leveled frame before applying yaw.
        leveled_x = x_val
        leveled_y = (y_val * cos_pitch) + (z_val * sin_pitch)
        leveled_z = (-y_val * sin_pitch) + (z_val * cos_pitch)

        transformed_point = dict(point)
        transformed_point["x"] = (leveled_x * cos_yaw) - (leveled_y * sin_yaw)
        transformed_point["y"] = (leveled_x * sin_yaw) + (leveled_y * cos_yaw)
        transformed_point["z"] = leveled_z + float(sensor_height_m)
        transformed_point["ground_range"] = math.hypot(transformed_point["x"], transformed_point["y"])
        transformed_points.append(transformed_point)
    return transformed_points


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
    static_clutter_padding: float,
) -> List[AxisAlignedBox]:
    if not enabled:
        return []

    half_width = right_rail_width / 2.0
    return [
        AxisAlignedBox(
            label="static_clutter",
            x_min=right_rail_x - half_width - static_clutter_padding,
            x_max=right_rail_x + half_width + static_clutter_padding,
            y_min=right_rail_y_start - static_clutter_padding,
            y_max=right_rail_y_start + right_rail_length + static_clutter_padding,
            z_min=right_rail_z_base - static_clutter_padding,
            z_max=right_rail_z_base + right_rail_height + static_clutter_padding,
        )
    ]


def build_runtime_processing_context(
    sensor_yaw_deg: float = 0.0,
    sensor_pitch_deg: float = 0.0,
    sensor_height_m: float = 0.0,
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
    near_front_half_width: float = 1.0,
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
    static_v_min: Optional[float] = 0.12,
    static_max_snr: Optional[float] = 18.0,
    filter_sample_count: int = 0,
    dbscan_eps: float = 0.35,
    dbscan_min_samples: int = 4,
    use_velocity_feature: bool = False,
    dbscan_velocity_weight: float = 0.25,
    dbscan_adaptive_eps_bands: object = None,
) -> RuntimeProcessingContext:
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
        static_clutter_padding=static_clutter_padding,
    )
    return RuntimeProcessingContext(
        sensor_yaw_deg=float(sensor_yaw_deg),
        sensor_pitch_deg=float(sensor_pitch_deg),
        sensor_height_m=float(sensor_height_m),
        snr_threshold=float(snr_threshold),
        max_noise=None if max_noise is None else float(max_noise),
        min_range=float(min_range),
        max_range=None if max_range is None else float(max_range),
        filter_x_min=None if filter_x_min is None else float(filter_x_min),
        filter_x_max=None if filter_x_max is None else float(filter_x_max),
        filter_y_min=None if filter_y_min is None else float(filter_y_min),
        filter_y_max=None if filter_y_max is None else float(filter_y_max),
        filter_z_min=None if filter_z_min is None else float(filter_z_min),
        filter_z_max=None if filter_z_max is None else float(filter_z_max),
        keepout_boxes=keepout_boxes,
        static_clutter_boxes=static_clutter_boxes,
        static_v_min=None if static_v_min is None else float(static_v_min),
        static_max_snr=None if static_max_snr is None else float(static_max_snr),
        filter_sample_count=max(0, int(filter_sample_count)),
        dbscan_eps=float(dbscan_eps),
        dbscan_min_samples=max(1, int(dbscan_min_samples)),
        use_velocity_feature=bool(use_velocity_feature),
        dbscan_velocity_weight=max(0.0, float(dbscan_velocity_weight)),
        dbscan_adaptive_eps_bands=normalize_adaptive_eps_bands(dbscan_adaptive_eps_bands),
    )


def process_runtime_frame(
    frame: ParsedFrame,
    processing_context: RuntimeProcessingContext,
    tracker: Optional[MultiObjectKalmanTracker] = None,
    frame_ts: Optional[float] = None,
) -> RuntimeFrameProcessingResult:
    process_t0 = time.perf_counter()
    effective_frame_ts = time.time() if frame_ts is None else float(frame_ts)

    raw_points = points_dict_to_list(frame.points, frame.num_obj)
    raw_points = transform_points_to_world(
        raw_points,
        yaw_deg=processing_context.sensor_yaw_deg,
        pitch_deg=processing_context.sensor_pitch_deg,
        sensor_height_m=processing_context.sensor_height_m,
    )
    filtered_points, filter_stats = preprocess_points(
        raw_points,
        snr_threshold=processing_context.snr_threshold,
        max_noise=processing_context.max_noise,
        min_range=processing_context.min_range,
        max_range=processing_context.max_range,
        x_min=processing_context.filter_x_min,
        x_max=processing_context.filter_x_max,
        y_min=processing_context.filter_y_min,
        y_max=processing_context.filter_y_max,
        z_min=processing_context.filter_z_min,
        z_max=processing_context.filter_z_max,
        exclusion_boxes=processing_context.keepout_boxes,
        static_clutter_boxes=processing_context.static_clutter_boxes,
        static_v_min=processing_context.static_v_min,
        static_max_snr=processing_context.static_max_snr,
        sample_preview_count=processing_context.filter_sample_count,
        return_stats=True,
    )

    clusters: List[dict] = []
    dbscan_import_error: Optional[Exception] = None
    try:
        clusters = cluster_points(
            filtered_points,
            eps=processing_context.dbscan_eps,
            min_samples=processing_context.dbscan_min_samples,
            use_velocity_feature=processing_context.use_velocity_feature,
            velocity_weight=processing_context.dbscan_velocity_weight,
            adaptive_eps_bands=processing_context.dbscan_adaptive_eps_bands,
        )
    except ImportError as exc:
        dbscan_import_error = exc

    tracks: List[object] = []
    if tracker is not None:
        tracks = tracker.update(clusters, frame_ts=effective_frame_ts)

    return RuntimeFrameProcessingResult(
        raw_points=raw_points,
        filtered_points=filtered_points,
        filter_stats=filter_stats,
        clusters=clusters,
        tracks=tracks,
        pipeline_latency_ms=(time.perf_counter() - process_t0) * 1000.0,
        dbscan_import_error=dbscan_import_error,
    )
