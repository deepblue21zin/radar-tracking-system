"""Lightweight multi-target Kalman tracker using cluster centroids."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import math
import sys

import numpy as np


def _load_filterpy():
    """Import filterpy from site-packages or local vendor folder."""
    try:
        from filterpy.common import Q_discrete_white_noise
        from filterpy.kalman import KalmanFilter
        return KalmanFilter, Q_discrete_white_noise
    except ImportError:
        vendor_root = Path(__file__).resolve().parents[1] / "filterpy-master"
        if vendor_root.exists():
            sys.path.insert(0, str(vendor_root))
            from filterpy.common import Q_discrete_white_noise
            from filterpy.kalman import KalmanFilter
            return KalmanFilter, Q_discrete_white_noise
        raise


@dataclass
class TrackOutput:
    track_id: int
    x: float
    y: float
    vx: float
    vy: float
    age: int
    hits: int
    misses: int
    confidence: float


class _Track:
    def __init__(self, track_id: int, measurement: dict, kf, frame_ts: float):
        self.track_id = track_id
        self.kf = kf
        self.age = 1
        self.hits = 1
        self.misses = 0
        self.last_update_ts = frame_ts
        self.confidence = float(measurement.get("confidence", 0.5))


class MultiObjectKalmanTracker:
    def __init__(
        self,
        process_var: float = 1.0,
        measurement_var: float = 0.4,
        association_gate: float = 1.5,
        max_misses: int = 8,
        min_hits: int = 2,
        report_miss_tolerance: int = 0,
    ):
        KalmanFilter, Q_discrete_white_noise = _load_filterpy()
        self._KalmanFilter = KalmanFilter
        self._Q_discrete_white_noise = Q_discrete_white_noise

        self.process_var = process_var
        self.measurement_var = measurement_var
        self.association_gate = association_gate
        self.max_misses = max_misses
        self.min_hits = min_hits
        self.report_miss_tolerance = max(0, int(report_miss_tolerance))

        self._tracks: List[_Track] = []
        self._next_track_id = 1

    def _build_kf(self, measurement: dict):
        kf = self._KalmanFilter(dim_x=4, dim_z=2)
        kf.x = np.array([[measurement["x"]], [measurement["y"]], [0.0], [0.0]], dtype=float)
        kf.F = np.array(
            [[1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            dtype=float,
        )
        kf.H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
        kf.P = np.eye(4, dtype=float) * 20.0
        kf.R = np.eye(2, dtype=float) * self.measurement_var
        q = self._Q_discrete_white_noise(dim=2, dt=1.0, var=self.process_var)
        zeros = np.zeros((2, 2), dtype=float)
        kf.Q = np.block([[q, zeros], [zeros, q]])
        return kf

    @staticmethod
    def _distance(track: _Track, meas: dict) -> float:
        tx = float(track.kf.x[0][0])
        ty = float(track.kf.x[1][0])
        return math.hypot(tx - float(meas["x"]), ty - float(meas["y"]))

    def _predict(self, dt: float) -> None:
        for trk in self._tracks:
            trk.kf.F[0, 2] = dt
            trk.kf.F[1, 3] = dt
            trk.kf.predict()
            trk.age += 1
            trk.misses += 1

    def _associate(self, measurements: List[dict]) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not self._tracks or not measurements:
            return [], list(range(len(self._tracks))), list(range(len(measurements)))

        pairs = []
        used_tracks = set()
        used_meas = set()

        candidates = []
        for ti, trk in enumerate(self._tracks):
            for mi, meas in enumerate(measurements):
                d = self._distance(trk, meas)
                if d <= self.association_gate:
                    candidates.append((d, ti, mi))

        candidates.sort(key=lambda x: x[0])

        for _, ti, mi in candidates:
            if ti in used_tracks or mi in used_meas:
                continue
            used_tracks.add(ti)
            used_meas.add(mi)
            pairs.append((ti, mi))

        unmatched_tracks = [i for i in range(len(self._tracks)) if i not in used_tracks]
        unmatched_meas = [i for i in range(len(measurements)) if i not in used_meas]
        return pairs, unmatched_tracks, unmatched_meas

    def update(self, measurements: List[dict], frame_ts: Optional[float] = None) -> List[TrackOutput]:
        if frame_ts is None:
            frame_ts = 0.0

        if self._tracks:
            ref_ts = self._tracks[0].last_update_ts
            dt = max(0.03, min(0.5, frame_ts - ref_ts)) if frame_ts > 0 else 0.1
        else:
            dt = 0.1

        self._predict(dt)
        matched, _, unmatched_meas = self._associate(measurements)

        for ti, mi in matched:
            trk = self._tracks[ti]
            meas = measurements[mi]
            z = np.array([[float(meas["x"])], [float(meas["y"])]], dtype=float)
            trk.kf.update(z)
            trk.hits += 1
            trk.misses = 0
            trk.last_update_ts = frame_ts
            trk.confidence = max(trk.confidence, float(meas.get("confidence", 0.5)))

        for mi in unmatched_meas:
            meas = measurements[mi]
            kf = self._build_kf(meas)
            trk = _Track(self._next_track_id, meas, kf, frame_ts)
            self._next_track_id += 1
            self._tracks.append(trk)

        self._tracks = [t for t in self._tracks if t.misses <= self.max_misses]

        outputs: List[TrackOutput] = []
        for trk in self._tracks:
            if trk.hits < self.min_hits:
                continue
            if trk.misses > self.report_miss_tolerance:
                continue
            outputs.append(
                TrackOutput(
                    track_id=trk.track_id,
                    x=float(trk.kf.x[0][0]),
                    y=float(trk.kf.x[1][0]),
                    vx=float(trk.kf.x[2][0]),
                    vy=float(trk.kf.x[3][0]),
                    age=trk.age,
                    hits=trk.hits,
                    misses=trk.misses,
                    confidence=trk.confidence,
                )
            )

        return outputs
