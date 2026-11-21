"""strict simulation-timestamp recording protocol independent of gazebo imports."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class SimTimeWindow:
    duration_s: float
    nominal_rate_hz: float
    max_samples: int = 20000
    start_limit_s: float = 0.1
    gap_factor: float = 3.0
    samples: list = field(default_factory=list)
    rejected: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    reached: bool = False
    failure: str | None = None

    def __post_init__(self):
        if not (0 < self.duration_s <= 180 and 1 <= self.nominal_rate_hz <= 500):
            raise ValueError("duration must be (0,180], rate [1,500]")
        if not (2 <= self.max_samples <= 20000):
            raise ValueError("max_samples must be [2,20000] (legacy export limit)")
        if not (0 < self.start_limit_s <= 1 and self.gap_factor > 1):
            raise ValueError("invalid timing limits")
        # intentionally fail on a config that would necessarily reach export limits.
        if math.ceil(self.duration_s * self.nominal_rate_hz) + 3 > self.max_samples:
            raise ValueError("duration/rate requires more than max_samples; reduce rate or duration")

    @property
    def start(self):
        return self.samples[0].timestamp_s if self.samples else None

    @property
    def elapsed(self):
        return self.samples[-1].timestamp_s - self.start if self.samples else 0.0

    def ingest(self, sample):
        """consume ordered samples, rejecting duplicates and abnormal gaps."""
        if self.reached or self.failure:
            return
        try:
            sample.validate()
        except (ValueError, AttributeError) as exc:
            self._reject(f"invalid_sample: {exc}")
            return
        t = float(sample.timestamp_s)
        if not self.samples:
            if t > self.start_limit_s:
                self.failure = f"first_sample_late: {t:.6f}s > {self.start_limit_s:.6f}s"
                return
        else:
            previous = self.samples[-1].timestamp_s
            if t <= previous:
                self._reject("nonincreasing_timestamp")
                return
            if t - previous > self.gap_factor / self.nominal_rate_hz + 1e-9:
                self.failure = f"sample_gap_exceeded: {t - previous:.6f}s"
                return
        if len(self.samples) >= self.max_samples:
            self.failure = "sample_limit_exhausted"
            return
        self.samples.append(sample)
        if self.elapsed >= self.duration_s - 1e-9:
            # no wall-clock substitution and no silent early-success.
            self.reached = True

    def _reject(self, message):
        self.rejected += 1
        if len(self.rejection_reasons) < 8:
            self.rejection_reasons.append(message)

    def report(self, wall_timeout=False):
        if self.failure:
            status = "failed_recording"
        elif not self.reached or len(self.samples) < 2:
            status = "wall_timeout_before_sim_duration" if wall_timeout else "incomplete"
        else:
            status = "sim_time_window_captured"
        dt = [b.timestamp_s - a.timestamp_s for a, b in zip(self.samples, self.samples[1:])]
        return {
            "status": status,
            "requested_sim_duration_s": self.duration_s,
            "recorded_sim_duration_s": self.elapsed,
            "absolute_first_sim_stamp_s": self.start,
            "absolute_last_sim_stamp_s": self.samples[-1].timestamp_s if self.samples else None,
            "samples": len(self.samples),
            "nominal_rate_hz": self.nominal_rate_hz,
            "max_sample_gap_s": max(dt) if dt else None,
            "rejected_samples": self.rejected,
            "rejection_reasons": self.rejection_reasons,
            "failure": self.failure,
            "time_origin": "first_valid_odometry_timestamp_not_world_zero",
            "termination": "odometry_simulation_timestamp_not_wall_clock",
        }
