"""Shared runtime dataclasses used across runner, processing, and viewer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, List, Optional, Sequence

try:
    from ..filter.noise_filter import AxisAlignedBox, FilterStats
except ImportError:
    src_root = Path(__file__).resolve().parents[1]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from filter.noise_filter import AxisAlignedBox, FilterStats


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


@dataclass
class RuntimeProcessingContext:
    sensor_yaw_deg: float = 0.0
    sensor_pitch_deg: float = 0.0
    sensor_height_m: float = 0.0
    snr_threshold: float = 8.0
    max_noise: Optional[float] = None
    min_range: float = 0.0
    max_range: Optional[float] = None
    filter_x_min: Optional[float] = None
    filter_x_max: Optional[float] = None
    filter_y_min: Optional[float] = None
    filter_y_max: Optional[float] = None
    filter_z_min: Optional[float] = None
    filter_z_max: Optional[float] = None
    keepout_boxes: Sequence[AxisAlignedBox] = ()
    static_clutter_boxes: Sequence[AxisAlignedBox] = ()
    static_v_min: Optional[float] = None
    static_max_snr: Optional[float] = None
    filter_sample_count: int = 0
    dbscan_eps: float = 0.35
    dbscan_min_samples: int = 4
    use_velocity_feature: bool = False
    dbscan_velocity_weight: float = 0.25
    dbscan_adaptive_eps_bands: object = None


@dataclass
class RuntimeFrameProcessingResult:
    raw_points: List[dict]
    filtered_points: List[dict]
    filter_stats: FilterStats
    clusters: List[dict]
    tracks: List[object]
    pipeline_latency_ms: float
    dbscan_import_error: Optional[Exception] = None


@dataclass
class RuntimeFrameHookPayload:
    frame: ParsedFrame
    frame_gap: int
    frame_ts: float
    raw_points: List[dict]
    filtered_points: List[dict]
    filter_stats: FilterStats
    clusters: List[dict]
    tracks: List[object]
    pipeline_latency_ms: float
    reader_stats: ReaderStats
    control_decision: Optional[object] = None
