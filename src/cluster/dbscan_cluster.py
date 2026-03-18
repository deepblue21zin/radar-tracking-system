"""DBSCAN clustering for radar point clouds."""

import json
import math
import warnings
from typing import Iterable, List, Mapping, Optional


_ADAPTIVE_FALLBACK_WARNED = False
_ADAPTIVE_BOUNDARY_WARNED = False


def _effective_range(point: dict) -> float:
    range_val = float(point.get("range", 0.0))
    if math.isfinite(range_val) and range_val > 0.0:
        return range_val
    return math.sqrt((point["x"] * point["x"]) + (point["y"] * point["y"]) + (point.get("z", 0.0) ** 2))


def _normalize_band_float(value: object, field_name: str, allow_none: bool = False) -> Optional[float]:
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"Adaptive DBSCAN band field '{field_name}' is required.")

    if isinstance(value, str):
        lowered = value.strip().lower()
        if allow_none and lowered in {"", "none", "null", "inf", "+inf", "infinity", "+infinity"}:
            return None

    try:
        float_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Adaptive DBSCAN band field '{field_name}' must be numeric.") from exc

    if not math.isfinite(float_value):
        if allow_none:
            return None
        raise ValueError(f"Adaptive DBSCAN band field '{field_name}' must be finite.")

    return float_value


def _format_band_desc(r_min: float, r_max: Optional[float]) -> str:
    upper_text = "inf" if r_max is None else f"{r_max:.2f}"
    return f"{r_min:.2f}-{upper_text}m"


def normalize_adaptive_eps_bands(raw_bands: object) -> List[dict]:
    """Normalize adaptive DBSCAN bands.

    Accepted inputs:
    - ``None`` or empty string/list: disabled
    - JSON-style list of dicts
    - compact string form: ``r_min:r_max:eps[:min_samples],...``

    Each normalized band dict contains:
    - ``r_min``: inclusive lower range bound in meters
    - ``r_max``: exclusive upper range bound in meters, or ``None`` for infinity
    - ``eps``: DBSCAN eps for the band
    - ``min_samples``: optional band-specific min_samples override
    - ``description``: human-readable range label
    """
    if raw_bands is None or raw_bands == "":
        return []

    parsed_bands: object
    if isinstance(raw_bands, str):
        text = raw_bands.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed_bands = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSON for --dbscan-adaptive-eps-bands.") from exc
        else:
            parsed_bands = []
            for chunk in text.replace(";", ",").split(","):
                segment = chunk.strip()
                if not segment:
                    continue
                parts = [part.strip() for part in segment.split(":")]
                if len(parts) not in {3, 4}:
                    raise ValueError(
                        "Adaptive DBSCAN bands must use 'r_min:r_max:eps[:min_samples]' segments."
                    )

                band = {
                    "r_min": parts[0],
                    "r_max": parts[1],
                    "eps": parts[2],
                }
                if len(parts) == 4:
                    band["min_samples"] = parts[3]
                parsed_bands.append(band)
    else:
        parsed_bands = raw_bands

    if not isinstance(parsed_bands, (list, tuple)):
        raise ValueError("Adaptive DBSCAN bands must be a list/tuple or a compact string.")

    normalized: List[dict] = []
    previous_upper: Optional[float] = None
    for index, band in enumerate(parsed_bands):
        if not isinstance(band, Mapping):
            raise ValueError(f"Adaptive DBSCAN band #{index + 1} must be an object/dict.")

        r_min = _normalize_band_float(band.get("r_min"), "r_min")
        r_max = _normalize_band_float(band.get("r_max"), "r_max", allow_none=True)
        eps = _normalize_band_float(band.get("eps"), "eps")

        if r_min is None:
            raise ValueError(f"Adaptive DBSCAN band #{index + 1} is missing r_min.")
        if eps is None or eps <= 0.0:
            raise ValueError(f"Adaptive DBSCAN band #{index + 1} requires eps > 0.0.")
        if r_min < 0.0:
            raise ValueError(f"Adaptive DBSCAN band #{index + 1} requires r_min >= 0.0.")
        if r_max is not None and r_max <= r_min:
            raise ValueError(f"Adaptive DBSCAN band #{index + 1} requires r_max > r_min.")
        if previous_upper is not None and r_min < previous_upper:
            raise ValueError("Adaptive DBSCAN bands must be sorted and non-overlapping.")

        min_samples = band.get("min_samples")
        if min_samples is not None:
            try:
                min_samples = int(min_samples)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Adaptive DBSCAN band #{index + 1} has invalid min_samples."
                ) from exc
            if min_samples < 1:
                raise ValueError(f"Adaptive DBSCAN band #{index + 1} requires min_samples >= 1.")

        normalized_band = {
            "r_min": float(r_min),
            "r_max": None if r_max is None else float(r_max),
            "eps": float(eps),
            "description": _format_band_desc(float(r_min), None if r_max is None else float(r_max)),
        }
        if min_samples is not None:
            normalized_band["min_samples"] = min_samples

        normalized.append(normalized_band)
        previous_upper = None if r_max is None else float(r_max)
        if previous_upper is None and index != len(parsed_bands) - 1:
            raise ValueError("An adaptive DBSCAN band with r_max=None must be the last band.")

    return normalized


def _range_matches_band(range_val: float, band: Mapping[str, object]) -> bool:
    band_min = float(band["r_min"])
    band_max = band.get("r_max")
    if range_val < band_min:
        return False
    if band_max is None:
        return True
    return range_val < float(band_max)


def _build_feature_matrix(np, point_list: List[dict], use_velocity_feature: bool, velocity_weight: float):
    if use_velocity_feature:
        return np.array(
            [[p["x"], p["y"], p.get("v", 0.0) * velocity_weight] for p in point_list],
            dtype=float,
        )
    return np.array([[p["x"], p["y"]] for p in point_list], dtype=float)


def _summarize_cluster_points(
    np,
    c_points: List[dict],
    label: int,
    eps: float,
    min_samples: int,
    range_band_desc: Optional[str] = None,
    band_r_min: Optional[float] = None,
    band_r_max: Optional[float] = None,
    boundary_merged: bool = False,
) -> dict:
    size = len(c_points)
    x_vals = np.array([p["x"] for p in c_points], dtype=float)
    y_vals = np.array([p["y"] for p in c_points], dtype=float)
    z_vals = np.array([p.get("z", 0.0) for p in c_points], dtype=float)
    v_vals = np.array([p.get("v", 0.0) for p in c_points], dtype=float)
    snr_vals = np.array([max(p.get("snr", 0.0), 0.0) for p in c_points], dtype=float)
    range_vals = np.array([_effective_range(p) for p in c_points], dtype=float)

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
    confidence = float(np.clip((0.5 * size_score) + (0.3 * snr_score) + (0.2 * spread_score), 0.0, 1.0))

    cluster = {
        "x": x_mean,
        "y": y_mean,
        "z": z_mean,
        "v": v_mean,
        "size": size,
        "confidence": confidence,
        "label": label,
        "spread_xy": spread_xy,
        "mean_snr": mean_snr,
        "centroid_method": "snr_weighted" if use_snr_weights else "mean",
        "eps_used": float(eps),
        "min_samples_used": int(min_samples),
        "_member_points": list(c_points),
        "_band_r_min": band_r_min,
        "_band_r_max": band_r_max,
        "_point_range_min": float(np.min(range_vals)),
        "_point_range_max": float(np.max(range_vals)),
    }
    if range_band_desc is not None:
        cluster["range_band"] = range_band_desc
    if boundary_merged:
        cluster["boundary_merged"] = True
    return cluster


def _cluster_single_batch(
    np,
    DBSCAN,
    point_list: List[dict],
    eps: float,
    min_samples: int,
    use_velocity_feature: bool,
    velocity_weight: float,
    label_offset: int = 0,
    range_band_desc: Optional[str] = None,
    band_r_min: Optional[float] = None,
    band_r_max: Optional[float] = None,
) -> tuple[List[dict], int]:
    feature_mat = _build_feature_matrix(np, point_list, use_velocity_feature, velocity_weight)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(feature_mat)

    clusters: List[dict] = []
    next_label = label_offset
    unique_labels = sorted(set(labels))
    for label in unique_labels:
        if label == -1:
            continue

        idx = np.where(labels == label)[0]
        if idx.size == 0:
            continue

        c_points = [point_list[i] for i in idx]
        cluster = _summarize_cluster_points(
            np=np,
            c_points=c_points,
            label=next_label,
            eps=eps,
            min_samples=min_samples,
            range_band_desc=range_band_desc,
            band_r_min=band_r_min,
            band_r_max=band_r_max,
        )
        clusters.append(cluster)
        next_label += 1

    return clusters, next_label


def _shared_band_boundary(cluster_a: Mapping[str, object], cluster_b: Mapping[str, object]) -> Optional[float]:
    tolerance = 1e-6
    a_min = cluster_a.get("_band_r_min")
    a_max = cluster_a.get("_band_r_max")
    b_min = cluster_b.get("_band_r_min")
    b_max = cluster_b.get("_band_r_max")

    if a_max is not None and b_min is not None and abs(float(a_max) - float(b_min)) <= tolerance:
        return float(a_max)
    if b_max is not None and a_min is not None and abs(float(b_max) - float(a_min)) <= tolerance:
        return float(b_max)
    return None


def _merge_band_description(desc_a: Optional[str], desc_b: Optional[str]) -> Optional[str]:
    descriptions = [desc for desc in (desc_a, desc_b) if desc]
    if not descriptions:
        return None

    unique_descriptions: List[str] = []
    for description in descriptions:
        if description not in unique_descriptions:
            unique_descriptions.append(description)
    return "|".join(unique_descriptions)


def _merge_band_upper(a_max: Optional[float], b_max: Optional[float]) -> Optional[float]:
    if a_max is None or b_max is None:
        return None
    return max(float(a_max), float(b_max))


def _warn_adaptive_fallback_once() -> None:
    global _ADAPTIVE_FALLBACK_WARNED
    if _ADAPTIVE_FALLBACK_WARNED:
        return
    warnings.warn(
        "Adaptive DBSCAN received points outside configured range bands; "
        "those points are clustered with the base eps/min_samples fallback.",
        RuntimeWarning,
        stacklevel=3,
    )
    _ADAPTIVE_FALLBACK_WARNED = True


def _warn_adaptive_boundary_merge_once() -> None:
    global _ADAPTIVE_BOUNDARY_WARNED
    if _ADAPTIVE_BOUNDARY_WARNED:
        return
    warnings.warn(
        "Adaptive DBSCAN merged adjacent-band clusters near a range boundary "
        "to reduce split artifacts. Review band edges if this happens often.",
        RuntimeWarning,
        stacklevel=3,
    )
    _ADAPTIVE_BOUNDARY_WARNED = True


def _merge_adaptive_boundary_clusters(np, clusters: List[dict]) -> List[dict]:
    if len(clusters) < 2:
        return clusters

    merged_clusters = list(clusters)
    merged_any = False

    while True:
        best_pair: Optional[tuple[int, int]] = None
        best_distance: Optional[float] = None

        for i in range(len(merged_clusters)):
            for j in range(i + 1, len(merged_clusters)):
                cluster_a = merged_clusters[i]
                cluster_b = merged_clusters[j]
                shared_boundary = _shared_band_boundary(cluster_a, cluster_b)
                if shared_boundary is None:
                    continue

                merge_threshold = max(float(cluster_a["eps_used"]), float(cluster_b["eps_used"]))
                centroid_distance = math.hypot(
                    float(cluster_a["x"]) - float(cluster_b["x"]),
                    float(cluster_a["y"]) - float(cluster_b["y"]),
                )
                if centroid_distance > merge_threshold:
                    continue

                if float(cluster_a["_point_range_max"]) <= float(cluster_b["_point_range_min"]):
                    lower_cluster = cluster_a
                    upper_cluster = cluster_b
                else:
                    lower_cluster = cluster_b
                    upper_cluster = cluster_a

                lower_near_boundary = float(lower_cluster["_point_range_max"]) >= shared_boundary - merge_threshold
                upper_near_boundary = float(upper_cluster["_point_range_min"]) <= shared_boundary + merge_threshold
                if not (lower_near_boundary and upper_near_boundary):
                    continue

                if best_distance is None or centroid_distance < best_distance:
                    best_pair = (i, j)
                    best_distance = centroid_distance

        if best_pair is None:
            break

        left_index, right_index = best_pair
        left_cluster = merged_clusters[left_index]
        right_cluster = merged_clusters[right_index]
        combined_points = list(left_cluster["_member_points"]) + list(right_cluster["_member_points"])
        merged_cluster = _summarize_cluster_points(
            np=np,
            c_points=combined_points,
            label=min(int(left_cluster["label"]), int(right_cluster["label"])),
            eps=max(float(left_cluster["eps_used"]), float(right_cluster["eps_used"])),
            min_samples=max(int(left_cluster["min_samples_used"]), int(right_cluster["min_samples_used"])),
            range_band_desc=_merge_band_description(left_cluster.get("range_band"), right_cluster.get("range_band")),
            band_r_min=min(float(left_cluster["_band_r_min"]), float(right_cluster["_band_r_min"])),
            band_r_max=_merge_band_upper(left_cluster.get("_band_r_max"), right_cluster.get("_band_r_max")),
            boundary_merged=True,
        )

        merged_clusters[left_index] = merged_cluster
        del merged_clusters[right_index]
        merged_any = True

    if merged_any:
        _warn_adaptive_boundary_merge_once()
    return merged_clusters


def _strip_internal_cluster_fields(clusters: List[dict]) -> List[dict]:
    public_clusters: List[dict] = []
    for cluster in clusters:
        public_clusters.append({key: value for key, value in cluster.items() if not key.startswith("_")})
    return public_clusters


def cluster_points(
    points: Iterable[dict],
    eps: float = 0.6,
    min_samples: int = 4,
    use_velocity_feature: bool = False,
    velocity_weight: float = 0.25,
    adaptive_eps_bands: object = None,
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
    - ``adaptive_eps_bands`` may be provided to run DBSCAN separately for
      different range bands. Each band uses ``r_min``, ``r_max``, ``eps``,
      and optional ``min_samples``.
    """
    if velocity_weight < 0.0:
        raise ValueError("velocity_weight must be >= 0.0")
    if eps <= 0.0:
        raise ValueError("eps must be > 0.0")
    if min_samples < 1:
        raise ValueError("min_samples must be >= 1")

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

    normalized_bands = normalize_adaptive_eps_bands(adaptive_eps_bands)
    if not normalized_bands:
        clusters, _ = _cluster_single_batch(
            np=np,
            DBSCAN=DBSCAN,
            point_list=point_list,
            eps=eps,
            min_samples=min_samples,
            use_velocity_feature=use_velocity_feature,
            velocity_weight=velocity_weight,
            label_offset=0,
        )
        return _strip_internal_cluster_fields(clusters)

    band_point_lists: List[List[dict]] = [[] for _ in normalized_bands]
    fallback_points: List[dict] = []
    for point in point_list:
        point_range = _effective_range(point)
        matched = False
        for band_index, band in enumerate(normalized_bands):
            if _range_matches_band(point_range, band):
                band_point_lists[band_index].append(point)
                matched = True
                break
        if not matched:
            fallback_points.append(point)

    if fallback_points:
        _warn_adaptive_fallback_once()

    clusters: List[dict] = []
    next_label = 0
    for band, band_points in zip(normalized_bands, band_point_lists):
        if not band_points:
            continue

        band_clusters, next_label = _cluster_single_batch(
            np=np,
            DBSCAN=DBSCAN,
            point_list=band_points,
            eps=float(band["eps"]),
            min_samples=int(band.get("min_samples", min_samples)),
            use_velocity_feature=use_velocity_feature,
            velocity_weight=velocity_weight,
            label_offset=next_label,
            range_band_desc=str(band["description"]),
            band_r_min=float(band["r_min"]),
            band_r_max=None if band.get("r_max") is None else float(band["r_max"]),
        )
        clusters.extend(band_clusters)

    if fallback_points:
        fallback_clusters, next_label = _cluster_single_batch(
            np=np,
            DBSCAN=DBSCAN,
            point_list=fallback_points,
            eps=eps,
            min_samples=min_samples,
            use_velocity_feature=use_velocity_feature,
            velocity_weight=velocity_weight,
            label_offset=next_label,
            range_band_desc="fallback",
        )
        clusters.extend(fallback_clusters)

    clusters = _merge_adaptive_boundary_clusters(np, clusters)
    return _strip_internal_cluster_fields(clusters)
