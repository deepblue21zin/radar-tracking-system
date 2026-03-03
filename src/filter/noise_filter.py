"""Point-cloud preprocessing utilities for radar tracking pipeline."""

from typing import Dict, Iterable, List, Optional


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


def preprocess_points(
    points: Iterable[dict],
    snr_threshold: float = 8.0,
    max_noise: Optional[float] = None,
    min_range: float = 0.0,
    max_range: Optional[float] = None,
    z_min: Optional[float] = None,
    z_max: Optional[float] = None,
) -> List[dict]:
    """Apply point-level quality and ROI filters.

    Filter order:
    1) SNR threshold
    2) noise upper bound (optional)
    3) range gate
    4) z-axis gate (optional)
    """
    filtered = []
    for p in points:
        snr = float(p.get("snr", 0.0))
        noise = float(p.get("noise", 0.0))
        rng = float(p.get("range", 0.0))
        z_val = float(p.get("z", 0.0))

        if snr < snr_threshold:
            continue
        if max_noise is not None and noise > max_noise:
            continue
        if rng < min_range:
            continue
        if max_range is not None and rng > max_range:
            continue
        if z_min is not None and z_val < z_min:
            continue
        if z_max is not None and z_val > z_max:
            continue

        filtered.append(p)

    return filtered
