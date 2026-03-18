"""Zone-based proximity control for conveyor speed decisions."""

from dataclasses import dataclass
import math
from typing import Iterable, List, Optional


def _get_value(track: object, key: str, default: float = 0.0) -> float:
    if isinstance(track, dict):
        value = track.get(key, default)
    else:
        value = getattr(track, key, default)
    try:
        value_f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return value_f if math.isfinite(value_f) else float(default)


def _get_track_id(track: object) -> Optional[int]:
    if isinstance(track, dict):
        value = track.get("track_id")
    else:
        value = getattr(track, "track_id", None)
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


class ProximitySpeedController:
    """Convert tracked object motion into conveyor speed commands."""

    def __init__(
        self,
        control_zone: ControlZone,
        slow_distance: float = 1.5,
        stop_distance: float = 0.4,
        resume_distance: float = 2.0,
        slow_speed_ratio: float = 0.4,
        approach_speed_threshold: float = 0.1,
        stationary_speed_threshold: float = 0.05,
        clear_frames_required: int = 3,
        target_lock_frames: int = 6,
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
        if target_lock_frames < 0:
            raise ValueError("target_lock_frames must be >= 0")

        self.control_zone = control_zone
        self.slow_distance = slow_distance
        self.stop_distance = stop_distance
        self.resume_distance = resume_distance
        self.slow_speed_ratio = slow_speed_ratio
        self.approach_speed_threshold = approach_speed_threshold
        self.stationary_speed_threshold = stationary_speed_threshold
        self.clear_frames_required = clear_frames_required
        self.target_lock_frames = int(target_lock_frames)

        self._last_command = "RESUME"
        self._last_primary_event = "CLEAR"
        self._clear_frames = clear_frames_required
        self._locked_track_id: Optional[int] = None
        self._lock_frames_remaining = 0

    def _assess_track(self, track: object) -> TrackAssessment:
        x_val = _get_value(track, "x")
        y_val = _get_value(track, "y")
        z_val = _get_value(track, "z")
        vx_val = _get_value(track, "vx")
        vy_val = _get_value(track, "vy")

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

        approaching = closing_speed_mps >= self.approach_speed_threshold
        stopped = speed_mps <= self.stationary_speed_threshold

        return TrackAssessment(
            track_id=_get_track_id(track),
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
        )

    @staticmethod
    def _sort_key(assessment: TrackAssessment) -> tuple:
        return (
            0 if assessment.inside_zone else 1,
            assessment.zone_distance_m,
            -assessment.closing_speed_mps,
            assessment.speed_mps,
        )

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
        assessments.sort(key=self._sort_key)
        candidate = self._select_candidate(assessments)

        if candidate is None:
            self._clear_frames += 1
            if self._clear_frames < self.clear_frames_required:
                command = self._last_command
                primary_event = self._last_primary_event
                reason = "holding previous command until clear condition persists"
                speed_ratio = 0.0 if command == "STOP" else self.slow_speed_ratio if command == "SLOW" else 1.0
            else:
                command = "RESUME"
                primary_event = "CLEAR"
                reason = "no tracks near control zone"
                speed_ratio = 1.0

            changed = command != self._last_command or primary_event != self._last_primary_event
            self._last_command = command
            self._last_primary_event = primary_event
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
                state=command,
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

        if candidate.inside_zone or candidate.zone_distance_m <= self.stop_distance:
            command = "STOP"
            speed_ratio = 0.0
            primary_event = "EMERGENCY_STOP" if candidate.approaching else "OBJECT_IN_ZONE"
            reason = "track is inside zone or within stop distance"
        elif candidate.zone_distance_m <= self.slow_distance and (
            candidate.approaching or self._last_command in {"SLOW", "STOP"}
        ):
            command = "SLOW"
            speed_ratio = self.slow_speed_ratio
            if candidate.approaching:
                primary_event = "OBJECT_APPROACHING"
                reason = "track is approaching the control zone"
            elif candidate.stopped:
                primary_event = "OBJECT_STOPPED"
                reason = "track is loitering near the control zone"
            else:
                primary_event = "OBJECT_IN_ZONE"
                reason = "track remains near the control zone"
        elif self._last_command in {"SLOW", "STOP"} and candidate.zone_distance_m <= self.resume_distance:
            command = "SLOW"
            speed_ratio = self.slow_speed_ratio
            primary_event = "OBJECT_IN_ZONE"
            reason = "holding slow state until track clears resume distance"
        else:
            command = "RESUME"
            speed_ratio = 1.0
            primary_event = "CLEAR"
            reason = "nearest track is outside the control envelope"

        if primary_event not in events:
            events.insert(0, primary_event)

        changed = command != self._last_command or primary_event != self._last_primary_event
        self._last_command = command
        self._last_primary_event = primary_event

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
            state=command,
            reason=reason,
            changed=changed,
            events=events,
        )
