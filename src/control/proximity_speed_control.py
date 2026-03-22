"""Zone-based proximity control for conveyor speed decisions."""

from collections import deque
from dataclasses import dataclass, field
import math
import time
from typing import Deque, Dict, Iterable, List, Optional, Tuple


def _get_raw_value(track: object, key: str, default: object = None) -> object:
    if isinstance(track, dict):
        return track.get(key, default)
    return getattr(track, key, default)


def _get_value(track: object, key: str, default: float = 0.0) -> float:
    value = _get_raw_value(track, key, default)
    try:
        value_f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return value_f if math.isfinite(value_f) else float(default)


def _get_optional_value(track: object, key: str) -> Optional[float]:
    value = _get_raw_value(track, key, None)
    if value is None:
        return None
    try:
        value_f = float(value)
    except (TypeError, ValueError):
        return None
    return value_f if math.isfinite(value_f) else None


def _get_track_id(track: object) -> Optional[int]:
    value = _get_raw_value(track, "track_id", None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ControlZone:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: Optional[float] = None
    z_max: Optional[float] = None

    def __post_init__(self) -> None:
        if self.x_min > self.x_max:
            raise ValueError("x_min must be <= x_max")
        if self.y_min > self.y_max:
            raise ValueError("y_min must be <= y_max")
        if self.z_min is not None and self.z_max is not None and self.z_min > self.z_max:
            raise ValueError("z_min must be <= z_max")

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) * 0.5

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) * 0.5

    @property
    def center_z(self) -> float:
        if self.z_min is None or self.z_max is None:
            return 0.0
        return (self.z_min + self.z_max) * 0.5

    def contains(self, x: float, y: float, z: float = 0.0) -> bool:
        if x < self.x_min or x > self.x_max:
            return False
        if y < self.y_min or y > self.y_max:
            return False
        if self.z_min is not None and z < self.z_min:
            return False
        if self.z_max is not None and z > self.z_max:
            return False
        return True

    def distance_to(self, x: float, y: float, z: float = 0.0) -> float:
        dx = max(self.x_min - x, 0.0, x - self.x_max)
        dy = max(self.y_min - y, 0.0, y - self.y_max)

        if self.z_min is None and self.z_max is None:
            dz = 0.0
        else:
            z_min = self.z_min if self.z_min is not None else z
            z_max = self.z_max if self.z_max is not None else z
            dz = max(z_min - z, 0.0, z - z_max)

        return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))

    def describe(self) -> str:
        z_desc = ""
        if self.z_min is not None or self.z_max is not None:
            z_desc = f",z=[{self.z_min if self.z_min is not None else '-inf'},{self.z_max if self.z_max is not None else 'inf'}]"
        return f"x=[{self.x_min},{self.x_max}],y=[{self.y_min},{self.y_max}]{z_desc}"


@dataclass
class TrackAssessment:
    track_id: Optional[int]
    x: float
    y: float
    z: float
    vx: float
    vy: float
    speed_mps: float
    zone_distance_m: float
    inside_zone: bool
    closing_speed_mps: float
    approaching: bool
    stopped: bool
    belt_position_m: float
    belt_speed_mps: Optional[float]
    belt_displacement_m: Optional[float]
    motion_state: str


@dataclass
class ControlDecision:
    command: str
    speed_ratio: float
    primary_event: str
    track_id: Optional[int]
    target_x: Optional[float]
    target_y: Optional[float]
    target_z: Optional[float]
    zone_distance_m: Optional[float]
    closing_speed_mps: Optional[float]
    inside_zone: bool
    approaching: bool
    state: str
    reason: str
    changed: bool = False
    events: Optional[List[str]] = None
    belt_speed_mps: Optional[float] = None
    belt_displacement_m: Optional[float] = None


@dataclass
class _TrackMotionMemory:
    motion_state: str = "UNKNOWN"
    last_seen_ts: float = 0.0
    static_candidate_since: Optional[float] = None
    moving_candidate_since: Optional[float] = None
    position_history: Deque[Tuple[float, float]] = field(default_factory=deque)


class ProximitySpeedController:
    """Convert tracked object motion into conveyor speed commands."""

    def __init__(
        self,
        control_zone: ControlZone,
        slow_distance: float = 1.5,
        stop_distance: float = 0.4,
        resume_distance: float = 2.0,
        slow_speed_ratio: float = 0.4,
        approach_speed_threshold: float = 0.15,
        stationary_speed_threshold: float = 0.06,
        clear_frames_required: int = 3,
<<<<<<< HEAD
        target_lock_frames: int = 6,
=======
        belt_axis_x: float = 0.0,
        belt_axis_y: float = 1.0,
        moving_confirm_sec: float = 0.3,
        static_hold_sec: float = 0.8,
        static_disp_window_sec: float = 0.8,
        static_disp_threshold: float = 0.05,
>>>>>>> dev
    ):
        if slow_distance < 0.0 or stop_distance < 0.0 or resume_distance < 0.0:
            raise ValueError("Distances must be >= 0.0")
        if stop_distance > slow_distance:
            raise ValueError("stop_distance must be <= slow_distance")
        if slow_distance > resume_distance:
            raise ValueError("resume_distance must be >= slow_distance")
        if not 0.0 <= slow_speed_ratio <= 1.0:
            raise ValueError("slow_speed_ratio must be in [0, 1]")
        if clear_frames_required < 1:
            raise ValueError("clear_frames_required must be >= 1")
<<<<<<< HEAD
        if target_lock_frames < 0:
            raise ValueError("target_lock_frames must be >= 0")
=======
        if stationary_speed_threshold < 0.0 or approach_speed_threshold < 0.0:
            raise ValueError("Speed thresholds must be >= 0.0")
        if stationary_speed_threshold > approach_speed_threshold:
            raise ValueError("stationary_speed_threshold must be <= approach_speed_threshold")
        if moving_confirm_sec < 0.0 or static_hold_sec < 0.0:
            raise ValueError("Motion confirmation times must be >= 0.0")
        if static_disp_window_sec < 0.0 or static_disp_threshold < 0.0:
            raise ValueError("Static displacement parameters must be >= 0.0")

        axis_norm = math.hypot(belt_axis_x, belt_axis_y)
        if axis_norm <= 1e-6:
            raise ValueError("belt axis vector must be non-zero")
>>>>>>> dev

        self.control_zone = control_zone
        self.slow_distance = slow_distance
        self.stop_distance = stop_distance
        self.resume_distance = resume_distance
        self.slow_speed_ratio = slow_speed_ratio
        self.approach_speed_threshold = approach_speed_threshold
        self.stationary_speed_threshold = stationary_speed_threshold
        self.clear_frames_required = clear_frames_required
<<<<<<< HEAD
        self.target_lock_frames = int(target_lock_frames)
=======
        self.moving_confirm_sec = moving_confirm_sec
        self.static_hold_sec = static_hold_sec
        self.static_disp_window_sec = static_disp_window_sec
        self.static_disp_threshold = static_disp_threshold
        self.belt_axis_x = belt_axis_x / axis_norm
        self.belt_axis_y = belt_axis_y / axis_norm
>>>>>>> dev

        self._last_command = "RESUME"
        self._last_primary_event = "CLEAR"
        self._last_state = "CLEAR"
        self._clear_frames = clear_frames_required
<<<<<<< HEAD
        self._locked_track_id: Optional[int] = None
        self._lock_frames_remaining = 0
=======
        self._track_memory: Dict[int, _TrackMotionMemory] = {}
>>>>>>> dev

    def _project_to_belt_axis(self, x_value: float, y_value: float) -> float:
        return (x_value * self.belt_axis_x) + (y_value * self.belt_axis_y)

    def _cleanup_track_memory(self, frame_ts: float) -> None:
        stale_after = max(
            2.0,
            self.resume_distance,
            self.static_disp_window_sec * 2.0,
            self.static_hold_sec * 2.0,
            self.moving_confirm_sec * 4.0,
        )
        stale_ids = [
            track_id
            for track_id, memory in self._track_memory.items()
            if frame_ts - memory.last_seen_ts > stale_after
        ]
        for track_id in stale_ids:
            self._track_memory.pop(track_id, None)

    def _trim_position_history(self, memory: _TrackMotionMemory, frame_ts: float) -> None:
        cutoff = frame_ts - self.static_disp_window_sec
        while len(memory.position_history) > 1 and memory.position_history[1][0] <= cutoff:
            memory.position_history.popleft()

    def _get_window_displacement(self, memory: _TrackMotionMemory, frame_ts: float) -> Optional[float]:
        self._trim_position_history(memory, frame_ts)
        if not memory.position_history:
            return None

        oldest_ts, oldest_pos = memory.position_history[0]
        newest_ts, newest_pos = memory.position_history[-1]
        if newest_ts - oldest_ts < self.static_disp_window_sec:
            return None
        return abs(newest_pos - oldest_pos)

    def _update_motion_state(
        self,
        track_id: Optional[int],
        belt_speed_mps: Optional[float],
        belt_position_m: float,
        frame_ts: float,
    ) -> Tuple[str, Optional[float]]:
        if track_id is None or belt_speed_mps is None:
            return "UNKNOWN", None

        memory = self._track_memory.setdefault(track_id, _TrackMotionMemory())
        memory.last_seen_ts = frame_ts
        memory.position_history.append((frame_ts, belt_position_m))
        displacement_m = self._get_window_displacement(memory, frame_ts)
        abs_speed = abs(belt_speed_mps)

        if abs_speed <= self.stationary_speed_threshold:
            if memory.static_candidate_since is None:
                memory.static_candidate_since = frame_ts
            memory.moving_candidate_since = None
            static_duration = frame_ts - memory.static_candidate_since
            displacement_ok = displacement_m is not None and displacement_m <= self.static_disp_threshold
            if static_duration >= self.static_hold_sec and displacement_ok:
                memory.motion_state = "STATIC"
        elif abs_speed >= self.approach_speed_threshold:
            if memory.moving_candidate_since is None:
                memory.moving_candidate_since = frame_ts
            memory.static_candidate_since = None
            moving_duration = frame_ts - memory.moving_candidate_since
            if moving_duration >= self.moving_confirm_sec:
                memory.motion_state = "MOVING"
        else:
            # Hysteresis band: keep the previous confirmed state.
            pass

        return memory.motion_state, displacement_m

    def _assess_track(self, track: object, frame_ts: float) -> TrackAssessment:
        x_val = _get_value(track, "x")
        y_val = _get_value(track, "y")
        z_val = _get_value(track, "z")
        vx_opt = _get_optional_value(track, "vx")
        vy_opt = _get_optional_value(track, "vy")
        vx_val = float(vx_opt) if vx_opt is not None else 0.0
        vy_val = float(vy_opt) if vy_opt is not None else 0.0

        speed_mps = math.hypot(vx_val, vy_val)
        zone_distance_m = self.control_zone.distance_to(x_val, y_val, z_val)
        inside_zone = self.control_zone.contains(x_val, y_val, z_val)

        rel_x = self.control_zone.center_x - x_val
        rel_y = self.control_zone.center_y - y_val
        rel_norm = math.hypot(rel_x, rel_y)
        if rel_norm > 1e-6:
            closing_speed_mps = ((vx_val * rel_x) + (vy_val * rel_y)) / rel_norm
        else:
            closing_speed_mps = 0.0

        belt_position_m = self._project_to_belt_axis(x_val, y_val)
        track_id = _get_track_id(track)
        if vx_opt is not None and vy_opt is not None:
            belt_speed_mps = (vx_val * self.belt_axis_x) + (vy_val * self.belt_axis_y)
            motion_state, belt_displacement_m = self._update_motion_state(
                track_id,
                belt_speed_mps,
                belt_position_m,
                frame_ts,
            )
            approaching = belt_speed_mps >= self.approach_speed_threshold
        else:
            belt_speed_mps = None
            belt_displacement_m = None
            motion_state = "UNKNOWN"
            approaching = False

        stopped = motion_state == "STATIC"

        return TrackAssessment(
            track_id=track_id,
            x=x_val,
            y=y_val,
            z=z_val,
            vx=vx_val,
            vy=vy_val,
            speed_mps=speed_mps,
            zone_distance_m=zone_distance_m,
            inside_zone=inside_zone,
            closing_speed_mps=closing_speed_mps,
            approaching=approaching,
            stopped=stopped,
            belt_position_m=belt_position_m,
            belt_speed_mps=belt_speed_mps,
            belt_displacement_m=belt_displacement_m,
            motion_state=motion_state,
        )

    @staticmethod
    def _sort_key(assessment: TrackAssessment) -> tuple:
        motion_rank = {"STATIC": 0, "MOVING": 1, "UNKNOWN": 2}
        belt_speed_abs = abs(assessment.belt_speed_mps) if assessment.belt_speed_mps is not None else assessment.speed_mps
        return (
            0 if assessment.inside_zone else 1,
            assessment.zone_distance_m,
            motion_rank.get(assessment.motion_state, 3),
            -belt_speed_abs,
        )

<<<<<<< HEAD
    def _select_candidate(self, assessments: List[TrackAssessment]) -> Optional[TrackAssessment]:
        if not assessments:
            if self._locked_track_id is not None:
                if self._lock_frames_remaining > 0:
                    self._lock_frames_remaining -= 1
                else:
                    self._locked_track_id = None
            return None

        if self._locked_track_id is not None:
            for assessment in assessments:
                if assessment.track_id == self._locked_track_id:
                    self._lock_frames_remaining = self.target_lock_frames
                    return assessment

            if self._lock_frames_remaining > 0:
                self._lock_frames_remaining -= 1
            else:
                self._locked_track_id = None

        candidate = assessments[0]
        if candidate.track_id is not None and self.target_lock_frames > 0:
            self._locked_track_id = candidate.track_id
            self._lock_frames_remaining = self.target_lock_frames

        return candidate

    def update(self, tracks: Iterable[object]) -> ControlDecision:
        assessments = [self._assess_track(track) for track in tracks]
=======
    def update(self, tracks: Iterable[object], frame_ts: Optional[float] = None) -> ControlDecision:
        frame_ts = time.monotonic() if frame_ts is None else float(frame_ts)
        self._cleanup_track_memory(frame_ts)

        assessments = [self._assess_track(track, frame_ts) for track in tracks]
>>>>>>> dev
        assessments.sort(key=self._sort_key)
        candidate = self._select_candidate(assessments)

        if candidate is None:
            self._clear_frames += 1
            if self._clear_frames < self.clear_frames_required:
                command = self._last_command
                primary_event = self._last_primary_event
                state = self._last_state
                reason = "holding previous command until clear condition persists"
                speed_ratio = 0.0 if command == "STOP" else self.slow_speed_ratio if command == "SLOW" else 1.0
            else:
                command = "RESUME"
                primary_event = "CLEAR"
                state = "CLEAR"
                reason = "no tracks near control zone"
                speed_ratio = 1.0

            changed = (
                command != self._last_command
                or primary_event != self._last_primary_event
                or state != self._last_state
            )
            self._last_command = command
            self._last_primary_event = primary_event
            self._last_state = state
            return ControlDecision(
                command=command,
                speed_ratio=speed_ratio,
                primary_event=primary_event,
                track_id=None,
                target_x=None,
                target_y=None,
                target_z=None,
                zone_distance_m=None,
                closing_speed_mps=None,
                inside_zone=False,
                approaching=False,
                state=state,
                reason=reason,
                changed=changed,
                events=[primary_event],
            )

        self._clear_frames = 0
        events: List[str] = []

        if candidate.inside_zone:
            events.append("OBJECT_IN_ZONE")
        if candidate.approaching:
            events.append("OBJECT_APPROACHING")
        if candidate.stopped:
            events.append("OBJECT_STOPPED")

        state = "MOVING_TO_BELT" if candidate.approaching else "CLEAR"
        if candidate.inside_zone or candidate.zone_distance_m <= self.stop_distance:
            command = "STOP"
            speed_ratio = 0.0
            if candidate.stopped:
                state = "STATIC_HOLD"
                primary_event = "OBJECT_STOPPED"
                reason = "confirmed static track is holding at the belt"
            else:
                state = "SLOW_NEAR_BELT"
                primary_event = "EMERGENCY_STOP" if candidate.approaching else "OBJECT_IN_ZONE"
                reason = "track is inside zone or within stop distance"
        elif candidate.zone_distance_m <= self.slow_distance:
            if candidate.stopped:
                command = "STOP"
                speed_ratio = 0.0
                state = "STATIC_HOLD"
                primary_event = "OBJECT_STOPPED"
                reason = "confirmed static track near the control zone"
            else:
                command = "SLOW"
                speed_ratio = self.slow_speed_ratio
                state = "SLOW_NEAR_BELT"
                if candidate.approaching:
                    primary_event = "OBJECT_APPROACHING"
                    reason = "track is moving toward the belt inside the slow zone"
                else:
                    primary_event = "OBJECT_IN_ZONE"
                    reason = "track remains near the control zone"
        elif self._last_state in {"SLOW_NEAR_BELT", "STATIC_HOLD"} and candidate.zone_distance_m <= self.resume_distance:
            command = "SLOW"
            speed_ratio = self.slow_speed_ratio
            state = "SLOW_NEAR_BELT"
            primary_event = "OBJECT_IN_ZONE"
            reason = "holding slow state until track clears resume distance"
        elif candidate.approaching:
            command = "RESUME"
            speed_ratio = 1.0
            state = "MOVING_TO_BELT"
            primary_event = "OBJECT_APPROACHING"
            reason = "track is moving toward the belt outside the slow zone"
        else:
            command = "RESUME"
            speed_ratio = 1.0
            state = "CLEAR"
            primary_event = "CLEAR"
            reason = "nearest track is outside the control envelope"

        if primary_event not in events:
            events.insert(0, primary_event)

        changed = (
            command != self._last_command
            or primary_event != self._last_primary_event
            or state != self._last_state
        )
        self._last_command = command
        self._last_primary_event = primary_event
        self._last_state = state

        return ControlDecision(
            command=command,
            speed_ratio=speed_ratio,
            primary_event=primary_event,
            track_id=candidate.track_id,
            target_x=candidate.x,
            target_y=candidate.y,
            target_z=candidate.z,
            zone_distance_m=candidate.zone_distance_m,
            closing_speed_mps=candidate.closing_speed_mps,
            inside_zone=candidate.inside_zone,
            approaching=candidate.approaching,
            state=state,
            reason=reason,
            changed=changed,
            events=events,
            belt_speed_mps=candidate.belt_speed_mps,
            belt_displacement_m=candidate.belt_displacement_m,
        )
