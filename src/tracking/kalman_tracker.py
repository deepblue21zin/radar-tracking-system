"""Lightweight multi-target Kalman tracker using cluster centroids."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple
import sys

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment as _scipy_linear_sum_assignment
except ImportError:
    _scipy_linear_sum_assignment = None


class _SimpleKalmanFilter:
    """Minimal linear Kalman filter fallback used when filterpy/scipy is unavailable."""

    def __init__(self, dim_x: int, dim_z: int):
        self.dim_x = dim_x
        self.dim_z = dim_z
        self.x = np.zeros((dim_x, 1), dtype=float)
        self.F = np.eye(dim_x, dtype=float)
        self.H = np.zeros((dim_z, dim_x), dtype=float)
        self.P = np.eye(dim_x, dtype=float)
        self.Q = np.eye(dim_x, dtype=float)
        self.R = np.eye(dim_z, dtype=float)

    def predict(self) -> np.ndarray:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, z: np.ndarray) -> np.ndarray:
        y = z - (self.H @ self.x)
        pht = self.P @ self.H.T
        s = self.H @ pht + self.R
        try:
            k = np.linalg.solve(s, pht.T).T
        except np.linalg.LinAlgError:
            k = pht @ np.linalg.pinv(s)
        self.x = self.x + (k @ y)
        identity = np.eye(self.dim_x, dtype=float)
        kh = k @ self.H
        self.P = (identity - kh) @ self.P @ (identity - kh).T + k @ self.R @ k.T
        return self.x


def _fallback_q_discrete_white_noise(
    dim: int,
    dt: float = 1.0,
    var: float = 1.0,
    block_size: int = 1,
    order_by_dim: bool = True,
) -> np.ndarray:
    if dim != 2:
        raise NotImplementedError("Fallback Q builder only supports dim=2 constant-velocity models.")

    q = np.array(
        [[0.25 * dt**4, 0.5 * dt**3], [0.5 * dt**3, dt**2]],
        dtype=float,
    ) * float(var)

    if block_size == 1:
        return q
    if block_size < 1:
        raise ValueError("block_size must be positive.")

    if order_by_dim:
        return np.kron(np.eye(block_size, dtype=float), q)
    return np.kron(q, np.eye(block_size, dtype=float))


def _load_filterpy():
    """Import filterpy, falling back to a small local linear KF implementation."""
    try:
        from filterpy.common import Q_discrete_white_noise
        from filterpy.kalman import KalmanFilter
        return KalmanFilter, Q_discrete_white_noise
    except ImportError:
        vendor_root = Path(__file__).resolve().parents[1] / "filterpy-master"
        if vendor_root.exists() and str(vendor_root) not in sys.path:
            sys.path.insert(0, str(vendor_root))
        try:
            from filterpy.common import Q_discrete_white_noise
            from filterpy.kalman import KalmanFilter
            return KalmanFilter, Q_discrete_white_noise
        except ImportError:
            return _SimpleKalmanFilter, _fallback_q_discrete_white_noise


def _hungarian_fallback(cost_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Pure-numpy assignment fallback for rectangular cost matrices."""
    cost = np.asarray(cost_matrix, dtype=float)
    if cost.ndim != 2:
        raise ValueError("cost_matrix must be 2-dimensional.")
    if cost.size == 0:
        return np.array([], dtype=int), np.array([], dtype=int)

    transposed = False
    rows, cols = cost.shape
    if rows > cols:
        cost = cost.T
        rows, cols = cost.shape
        transposed = True

    u = np.zeros(rows + 1, dtype=float)
    v = np.zeros(cols + 1, dtype=float)
    p = np.zeros(cols + 1, dtype=int)
    way = np.zeros(cols + 1, dtype=int)

    for row in range(1, rows + 1):
        p[0] = row
        col0 = 0
        minv = np.full(cols + 1, np.inf, dtype=float)
        used = np.zeros(cols + 1, dtype=bool)
        while True:
            used[col0] = True
            row0 = p[col0]
            delta = np.inf
            col1 = 0
            for col in range(1, cols + 1):
                if used[col]:
                    continue
                cur = cost[row0 - 1, col - 1] - u[row0] - v[col]
                if cur < minv[col]:
                    minv[col] = cur
                    way[col] = col0
                if minv[col] < delta:
                    delta = minv[col]
                    col1 = col
            for col in range(cols + 1):
                if used[col]:
                    u[p[col]] += delta
                    v[col] -= delta
                else:
                    minv[col] -= delta
            col0 = col1
            if p[col0] == 0:
                break

        while True:
            col1 = way[col0]
            p[col0] = p[col1]
            col0 = col1
            if col0 == 0:
                break

    row_ind = []
    col_ind = []
    for col in range(1, cols + 1):
        if p[col] != 0:
            row_ind.append(p[col] - 1)
            col_ind.append(col - 1)

    row_ind_array = np.asarray(row_ind, dtype=int)
    col_ind_array = np.asarray(col_ind, dtype=int)
    order = np.argsort(row_ind_array)
    row_ind_array = row_ind_array[order]
    col_ind_array = col_ind_array[order]

    if transposed:
        return col_ind_array, row_ind_array
    return row_ind_array, col_ind_array


def _linear_sum_assignment(cost_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if _scipy_linear_sum_assignment is not None:
        return _scipy_linear_sum_assignment(cost_matrix)
    return _hungarian_fallback(cost_matrix)


class TrackState(Enum):
    TENTATIVE = auto()
    CONFIRMED = auto()
    LOST = auto()


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
        self.state = TrackState.TENTATIVE
        self.consecutive_hits = 1


class MultiObjectKalmanTracker:
    def __init__(
        self,
        process_var: float = 1.0,
        measurement_var: float = 0.4,
        association_gate: float = 5.99,
        max_misses: int = 8,
        min_hits: int = 2,
        report_miss_tolerance: int = 2,
        lost_gate_factor: float = 1.2,
        tentative_gate_factor: float = 0.5,
    ):
        if process_var <= 0:
            raise ValueError("process_var must be positive.")
        if measurement_var <= 0:
            raise ValueError("measurement_var must be positive.")
        if association_gate <= 0:
            raise ValueError("association_gate must be positive.")
        if max_misses < 0:
            raise ValueError("max_misses must be non-negative.")
        if min_hits < 1:
            raise ValueError("min_hits must be at least 1.")
        if report_miss_tolerance < 0:
            raise ValueError("report_miss_tolerance must be non-negative.")
        if lost_gate_factor <= 0:
            raise ValueError("lost_gate_factor must be positive.")
        if tentative_gate_factor <= 0:
            raise ValueError("tentative_gate_factor must be positive.")

        KalmanFilter, Q_discrete_white_noise = _load_filterpy()
        self._KalmanFilter = KalmanFilter
        self._Q_discrete_white_noise = Q_discrete_white_noise

        self.process_var = float(process_var)
        self.measurement_var = float(measurement_var)
        self.association_gate = float(association_gate)
        self.max_misses = int(max_misses)
        self.min_hits = int(min_hits)
        self.report_miss_tolerance = int(report_miss_tolerance)
        self.lost_gate_factor = float(lost_gate_factor)
        self.tentative_gate_factor = float(tentative_gate_factor)

        self._tracks: List[_Track] = []
        self._next_track_id = 1
        self._last_frame_ts: Optional[float] = None

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
        kf.Q = self._Q_discrete_white_noise(
            dim=2,
            dt=0.1,
            var=self.process_var,
            block_size=2,
            order_by_dim=False,
        )
        return kf

    @staticmethod
    def _mahalanobis_sq(track: _Track, meas: dict) -> float:
        z = np.array([[float(meas["x"])], [float(meas["y"])]], dtype=float)
        innovation = z - (track.kf.H @ track.kf.x)
        innovation_cov = track.kf.H @ track.kf.P @ track.kf.H.T + track.kf.R
        try:
            solved = np.linalg.solve(innovation_cov, innovation)
        except np.linalg.LinAlgError:
            return np.inf
        return float((innovation.T @ solved)[0, 0])

    def _compute_dt(self, frame_ts: Optional[float]) -> float:
        if frame_ts is None or self._last_frame_ts is None:
            return 0.1

        delta = frame_ts - self._last_frame_ts
        if delta <= 0:
            return 0.1
        return max(0.03, min(0.5, delta))

    def _predict(self, dt: float) -> None:
        q_matrix = self._Q_discrete_white_noise(
            dim=2,
            dt=dt,
            var=self.process_var,
            block_size=2,
            order_by_dim=False,
        )

        for trk in self._tracks:
            trk.kf.F[0, 2] = dt
            trk.kf.F[1, 3] = dt
            trk.kf.Q = q_matrix
            trk.kf.predict()
            trk.age += 1
            trk.misses += 1

    def _run_hungarian(
        self,
        measurements: List[dict],
        track_indices: List[int],
        meas_indices: List[int],
        gate: float,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not track_indices or not meas_indices:
            return [], track_indices[:], meas_indices[:]

        invalid_cost = 1e9
        cost_matrix = np.full((len(track_indices), len(meas_indices)), invalid_cost, dtype=float)

        for row, track_idx in enumerate(track_indices):
            for col, meas_idx in enumerate(meas_indices):
                cost = self._mahalanobis_sq(self._tracks[track_idx], measurements[meas_idx])
                if cost <= gate:
                    cost_matrix[row, col] = cost

        row_ind, col_ind = _linear_sum_assignment(cost_matrix)

        pairs = []
        used_rows = set()
        used_cols = set()
        for row, col in zip(row_ind, col_ind):
            if cost_matrix[row, col] >= invalid_cost:
                continue
            pairs.append((track_indices[row], meas_indices[col]))
            used_rows.add(int(row))
            used_cols.add(int(col))

        unmatched_tracks = [track_indices[row] for row in range(len(track_indices)) if row not in used_rows]
        unmatched_meas = [meas_indices[col] for col in range(len(meas_indices)) if col not in used_cols]
        return pairs, unmatched_tracks, unmatched_meas

    def _associate(self, measurements: List[dict]) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not self._tracks or not measurements:
            return [], list(range(len(self._tracks))), list(range(len(measurements)))

        all_meas = list(range(len(measurements)))
        confirmed_idx = [idx for idx, track in enumerate(self._tracks) if track.state == TrackState.CONFIRMED]
        lost_idx = [idx for idx, track in enumerate(self._tracks) if track.state == TrackState.LOST]
        tentative_idx = [idx for idx, track in enumerate(self._tracks) if track.state == TrackState.TENTATIVE]

        reacquire_gate = self.association_gate * self.lost_gate_factor
        tentative_gate = self.association_gate * self.tentative_gate_factor

        pairs1, unmatched_confirmed, remaining_meas = self._run_hungarian(
            measurements,
            confirmed_idx,
            all_meas,
            self.association_gate,
        )
        pairs2, unmatched_confirmed2, remaining_meas = self._run_hungarian(
            measurements,
            unmatched_confirmed,
            remaining_meas,
            reacquire_gate,
        )
        pairs3, unmatched_lost, remaining_meas = self._run_hungarian(
            measurements,
            lost_idx,
            remaining_meas,
            reacquire_gate,
        )
        pairs4, unmatched_tentative, birth_meas = self._run_hungarian(
            measurements,
            tentative_idx,
            remaining_meas,
            tentative_gate,
        )

        return (
            pairs1 + pairs2 + pairs3 + pairs4,
            unmatched_confirmed2 + unmatched_lost + unmatched_tentative,
            birth_meas,
        )

    def update(self, measurements: List[dict], frame_ts: Optional[float] = None) -> List[TrackOutput]:
        dt = self._compute_dt(frame_ts)
        self._predict(dt)
        if frame_ts is not None:
            self._last_frame_ts = frame_ts

        matched, unmatched_tracks, unmatched_meas = self._associate(measurements)

        for track_idx, meas_idx in matched:
            trk = self._tracks[track_idx]
            prev_state = trk.state
            meas = measurements[meas_idx]
            z = np.array([[float(meas["x"])], [float(meas["y"])]], dtype=float)

            trk.kf.update(z)
            trk.hits += 1
            trk.consecutive_hits += 1
            trk.misses = 0
            if frame_ts is not None:
                trk.last_update_ts = frame_ts
            trk.confidence = max(trk.confidence, float(meas.get("confidence", 0.5)))

            if prev_state == TrackState.LOST or trk.consecutive_hits >= self.min_hits:
                trk.state = TrackState.CONFIRMED
            else:
                trk.state = TrackState.TENTATIVE

        for track_idx in unmatched_tracks:
            trk = self._tracks[track_idx]
            trk.consecutive_hits = 0
            if trk.state == TrackState.CONFIRMED:
                trk.state = TrackState.LOST

        for meas_idx in unmatched_meas:
            meas = measurements[meas_idx]
            kf = self._build_kf(meas)
            trk = _Track(
                self._next_track_id,
                meas,
                kf,
                frame_ts if frame_ts is not None else 0.0,
            )
            self._next_track_id += 1
            self._tracks.append(trk)

        self._tracks = [
            trk for trk in self._tracks
            if not (trk.state == TrackState.TENTATIVE and trk.misses > 1)
            and trk.misses <= self.max_misses
        ]

        outputs: List[TrackOutput] = []
        for trk in self._tracks:
            if trk.state == TrackState.TENTATIVE:
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
