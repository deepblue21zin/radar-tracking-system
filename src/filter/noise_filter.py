"""Point-cloud preprocessing utilities for radar tracking pipeline."""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class AxisAlignedBox:
    label: str
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    z_min: Optional[float] = None
    z_max: Optional[float] = None


@dataclass
class FilterStats:
    raw_points: int = 0
    filtered_points: int = 0
    filter_ratio: float = 0.0
    raw_snr_min: Optional[float] = None
    raw_snr_avg: Optional[float] = None
    raw_snr_p90: Optional[float] = None
    filtered_snr_min: Optional[float] = None
    filtered_snr_avg: Optional[float] = None
    filtered_snr_p90: Optional[float] = None
    raw_range_min: Optional[float] = None
    raw_range_max: Optional[float] = None
    filtered_range_min: Optional[float] = None
    filtered_range_max: Optional[float] = None
    removed_snr: int = 0
    removed_noise: int = 0
    removed_range: int = 0
    removed_axis_roi: int = 0
    removed_keepout: int = 0
    removed_near_front_keepout: int = 0
    removed_right_rail_keepout: int = 0
    removed_static_clutter: int = 0
    sample_points: List[dict] = field(default_factory=list)
    sample_source: str = ""


def filter_points(points: Iterable[dict], snr_threshold: float = 8.0) -> List[dict]:
    """Return points with SNR above threshold.

    points: iterable of dict-like objects containing key `snr`.
    """
    return [p for p in points if p.get("snr", 0.0) >= snr_threshold]


def points_dict_to_list(points_dict: Dict[str, list], num_obj: Optional[int] = None) -> List[dict]:
    """Convert parser output dict-of-arrays into a list of point dictionaries."""
    keys = ("x", "y", "z", "v", "range", "snr", "noise")
    if num_obj is None:
        num_obj = max((len(points_dict.get(k, [])) for k in keys), default=0)

    rows: List[dict] = []
    for i in range(num_obj):
        rows.append(
            {
                "x": float(points_dict.get("x", [0.0] * num_obj)[i]) if i < len(points_dict.get("x", [])) else 0.0,
                "y": float(points_dict.get("y", [0.0] * num_obj)[i]) if i < len(points_dict.get("y", [])) else 0.0,
                "z": float(points_dict.get("z", [0.0] * num_obj)[i]) if i < len(points_dict.get("z", [])) else 0.0,
                "v": float(points_dict.get("v", [0.0] * num_obj)[i]) if i < len(points_dict.get("v", [])) else 0.0,
                "range": float(points_dict.get("range", [0.0] * num_obj)[i]) if i < len(points_dict.get("range", [])) else 0.0,
                "snr": float(points_dict.get("snr", [0.0] * num_obj)[i]) if i < len(points_dict.get("snr", [])) else 0.0,
                "noise": float(points_dict.get("noise", [0.0] * num_obj)[i]) if i < len(points_dict.get("noise", [])) else 0.0,
            }
        )
    return rows


def _percentile(values: Sequence[float], p: float) -> Optional[float]:
    if not values:
        return None

    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _safe_min(values: Sequence[float]) -> Optional[float]:
    return min(values) if values else None


def _safe_max(values: Sequence[float]) -> Optional[float]:
    return max(values) if values else None


def _safe_avg(values: Sequence[float]) -> Optional[float]:
    return (sum(values) / len(values)) if values else None


def _point_in_box(point: dict, box: AxisAlignedBox) -> bool:
    x_val = float(point.get("x", 0.0))
    y_val = float(point.get("y", 0.0))
    z_val = float(point.get("z", 0.0))

    if box.x_min is not None and x_val < box.x_min:
        return False
    if box.x_max is not None and x_val > box.x_max:
        return False
    if box.y_min is not None and y_val < box.y_min:
        return False
    if box.y_max is not None and y_val > box.y_max:
        return False
    if box.z_min is not None and z_val < box.z_min:
        return False
    if box.z_max is not None and z_val > box.z_max:
        return False
    return True


def _find_matching_box(point: dict, boxes: Sequence[AxisAlignedBox]) -> Optional[AxisAlignedBox]:
    for box in boxes:
        if _point_in_box(point, box):
            return box
    return None


def _summarize_points(points: Sequence[dict], stats: FilterStats, prefix: str) -> None:
    snr_values = [float(p.get("snr", 0.0)) for p in points]
    range_values = [float(p.get("range", 0.0)) for p in points]

    setattr(stats, f"{prefix}_snr_min", _safe_min(snr_values))
    setattr(stats, f"{prefix}_snr_avg", _safe_avg(snr_values))
    setattr(stats, f"{prefix}_snr_p90", _percentile(snr_values, 0.90))
    setattr(stats, f"{prefix}_range_min", _safe_min(range_values))
    setattr(stats, f"{prefix}_range_max", _safe_max(range_values))


def preprocess_points(
    points: Iterable[dict],
    snr_threshold: float = 8.0,
    max_noise: Optional[float] = None,
    min_range: float = 0.0,
    max_range: Optional[float] = None,
    x_min: Optional[float] = None,
    x_max: Optional[float] = None,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
    exclusion_boxes: Optional[Sequence[AxisAlignedBox]] = None,
    static_clutter_boxes: Optional[Sequence[AxisAlignedBox]] = None,
    static_v_min: Optional[float] = None,
    static_max_snr: Optional[float] = None,
    sample_preview_count: int = 0,
    return_stats: bool = False,
):
    """Apply point-level quality, ROI, and static-clutter filters.

    Filter order:
    1) SNR threshold
    2) noise upper bound (optional)
    3) range gate
    4) axis-aligned include ROI (optional)
    5) exclude keepout boxes (optional)
    6) low-velocity static clutter boxes with SNR guard (optional)
    """
    point_list = list(points)
    stats = FilterStats(raw_points=len(point_list))
    _summarize_points(point_list, stats, "raw")

    filtered: List[dict] = []
    keepout_boxes = list(exclusion_boxes or [])
    clutter_boxes = list(static_clutter_boxes or [])

    for point in point_list:
        snr = float(point.get("snr", 0.0))
        noise = float(point.get("noise", 0.0))
        rng = float(point.get("range", 0.0))
        x_val = float(point.get("x", 0.0))
        y_val = float(point.get("y", 0.0))
        z_val = float(point.get("z", 0.0))
        velocity = abs(float(point.get("v", 0.0)))

        if snr < snr_threshold:
            stats.removed_snr += 1
            continue
        if max_noise is not None and noise > max_noise:
            stats.removed_noise += 1
            continue
        if rng < min_range or (max_range is not None and rng > max_range):
            stats.removed_range += 1
            continue
        if x_min is not None and x_val < x_min:
            stats.removed_axis_roi += 1
            continue
        if x_max is not None and x_val > x_max:
            stats.removed_axis_roi += 1
            continue
        if y_min is not None and y_val < y_min:
            stats.removed_axis_roi += 1
            continue
        if y_max is not None and y_val > y_max:
            stats.removed_axis_roi += 1
            continue
        if z_min is not None and z_val < z_min:
            stats.removed_axis_roi += 1
            continue
        if z_max is not None and z_val > z_max:
            stats.removed_axis_roi += 1
            continue

        matched_keepout = _find_matching_box(point, keepout_boxes)
        if matched_keepout is not None:
            stats.removed_keepout += 1
            if matched_keepout.label == "near_front":
                stats.removed_near_front_keepout += 1
            elif matched_keepout.label == "right_rail":
                stats.removed_right_rail_keepout += 1
            continue

        matched_clutter = _find_matching_box(point, clutter_boxes)
        if matched_clutter is not None and static_v_min is not None and velocity < static_v_min:
            if static_max_snr is None or snr <= static_max_snr:
                stats.removed_static_clutter += 1
                continue

        filtered.append(point)

    stats.filtered_points = len(filtered)
    stats.filter_ratio = (len(filtered) / len(point_list)) if point_list else 0.0
    _summarize_points(filtered, stats, "filtered")

    if sample_preview_count > 0:
        sample_source_points = filtered if filtered else point_list
        stats.sample_points = sample_source_points[:sample_preview_count]
        stats.sample_source = "filtered" if filtered else "raw"

    if return_stats:
        return filtered, stats
    return filtered
