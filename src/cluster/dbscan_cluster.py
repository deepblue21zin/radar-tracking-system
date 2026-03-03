"""DBSCAN clustering for radar point clouds."""

from typing import Iterable, List


def cluster_points(
    points: Iterable[dict],
    eps: float = 0.6,
    min_samples: int = 4,
    use_velocity_feature: bool = False,
) -> List[dict]:
    """Cluster point cloud and return cluster-level measurements.

    Returns list of dicts containing:
    - x, y, z: centroid
    - v: mean radial velocity
    - size: number of points in cluster
    - confidence: simple confidence score in [0, 1]
    """
    point_list = list(points)
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
        feature_mat = np.array([[p["x"], p["y"], p.get("v", 0.0)] for p in point_list], dtype=float)
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

        x_mean = float(np.mean([p["x"] for p in c_points]))
        y_mean = float(np.mean([p["y"] for p in c_points]))
        z_mean = float(np.mean([p.get("z", 0.0) for p in c_points]))
        v_mean = float(np.mean([p.get("v", 0.0) for p in c_points]))

        # Confidence is point-count based; replace with better metric when available.
        confidence = min(1.0, size / max(float(min_samples), 1.0))

        clusters.append(
            {
                "x": x_mean,
                "y": y_mean,
                "z": z_mean,
                "v": v_mean,
                "size": size,
                "confidence": confidence,
                "label": int(label),
            }
        )

    return clusters
