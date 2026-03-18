"""DBSCAN clustering for radar point clouds."""

import math
from typing import Iterable, List


def cluster_points(
    points: Iterable[dict],
    eps: float = 0.6,
    min_samples: int = 4,
    use_velocity_feature: bool = False,
    velocity_weight: float = 0.25,
) -> List[dict]:
    """Cluster point cloud and return cluster-level measurements.

    Returns list of dicts containing:
    - x, y, z: centroid
    - v: mean radial velocity
    - size: number of points in cluster
    - confidence: heuristic confidence score in [0, 1]
    - spread_xy: RMS spread of points around centroid in XY plane
    - mean_snr: average cluster SNR when available

    Notes:
    - When ``use_velocity_feature`` is enabled, velocity is scaled by
      ``velocity_weight`` so that m/s does not dominate meter-based XY distance.
    - Cluster centroid falls back to a plain mean, but uses SNR-weighted mean
      when positive SNR values are available.
    """
    if velocity_weight < 0.0:
        raise ValueError("velocity_weight must be >= 0.0")

    point_list: List[dict] = []
    for point in points:
        try:
            x_val = float(point["x"])
            y_val = float(point["y"])
        except (KeyError, TypeError, ValueError):
            continue

        if not math.isfinite(x_val) or not math.isfinite(y_val):
            continue

        clean_point = dict(point)
        clean_point["x"] = x_val
        clean_point["y"] = y_val

        for key in ("z", "v", "snr", "noise", "range"):
            try:
                value = float(clean_point.get(key, 0.0))
            except (TypeError, ValueError):
                value = 0.0
            clean_point[key] = value if math.isfinite(value) else 0.0

        point_list.append(clean_point)

    if not point_list:
        return []

    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
    except ImportError as exc:
        raise ImportError(
            "DBSCAN requires numpy + scikit-learn. Install with `pip install numpy scikit-learn`."
        ) from exc

    if use_velocity_feature:
        feature_mat = np.array(
            [[p["x"], p["y"], p.get("v", 0.0) * velocity_weight] for p in point_list],
            dtype=float,
        )
    else:
        feature_mat = np.array([[p["x"], p["y"]] for p in point_list], dtype=float)

    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(feature_mat)

    clusters: List[dict] = []
    unique_labels = sorted(set(labels))
    for label in unique_labels:
        if label == -1:
            continue

        idx = np.where(labels == label)[0]
        if idx.size == 0:
            continue

        c_points = [point_list[i] for i in idx]
        size = len(c_points)

        x_vals = np.array([p["x"] for p in c_points], dtype=float)
        y_vals = np.array([p["y"] for p in c_points], dtype=float)
        z_vals = np.array([p.get("z", 0.0) for p in c_points], dtype=float)
        v_vals = np.array([p.get("v", 0.0) for p in c_points], dtype=float)
        snr_vals = np.array([max(p.get("snr", 0.0), 0.0) for p in c_points], dtype=float)

        use_snr_weights = float(np.sum(snr_vals)) > 0.0
        if use_snr_weights:
            x_mean = float(np.average(x_vals, weights=snr_vals))
            y_mean = float(np.average(y_vals, weights=snr_vals))
            z_mean = float(np.average(z_vals, weights=snr_vals))
            v_mean = float(np.average(v_vals, weights=snr_vals))
        else:
            x_mean = float(np.mean(x_vals))
            y_mean = float(np.mean(y_vals))
            z_mean = float(np.mean(z_vals))
            v_mean = float(np.mean(v_vals))

        spread_xy = float(np.sqrt(np.mean(np.square(np.hypot(x_vals - x_mean, y_vals - y_mean)))))
        mean_snr = float(np.mean(snr_vals)) if size > 0 else 0.0

        size_score = min(1.0, size / max(float(min_samples), 1.0))
        snr_score = 1.0 - math.exp(-mean_snr / 12.0) if mean_snr > 0.0 else size_score
        spread_score = max(0.0, 1.0 - (spread_xy / max(eps, 1e-6)))
        confidence = float(
            np.clip((0.5 * size_score) + (0.3 * snr_score) + (0.2 * spread_score), 0.0, 1.0)
        )

        clusters.append(
            {
                "x": x_mean,
                "y": y_mean,
                "z": z_mean,
                "v": v_mean,
                "size": size,
                "confidence": confidence,
                "label": int(label),
                "spread_xy": spread_xy,
                "mean_snr": mean_snr,
                "centroid_method": "snr_weighted" if use_snr_weights else "mean",
            }
        )

    return clusters
