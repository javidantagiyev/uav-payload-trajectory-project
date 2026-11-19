"""Validated, file-based configurations for reproducible offline experiments."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .parameters import Atmosphere, Body


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    initial_state: tuple[float, float, float, float, float, float]
    duration_s: float
    body: Body
    atmosphere: Atmosphere
    maximum_step_s: float
    reference_step_s: float
    convergence_steps_s: tuple[float, ...]
    timing_repetitions: int


def _mapping(value, expected_keys, name):
    if not isinstance(value, dict) or set(value) != set(expected_keys):
        raise ValueError(f"{name} must be an object with exactly {sorted(expected_keys)}")
    return value


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


def _vector(value, length, name):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{name} must contain {length} finite numeric entries")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not np.isfinite(v) for v in value):
        raise ValueError(f"{name} must contain {length} finite numeric entries")
    return tuple(float(v) for v in value)


def load_scenario(path: str | Path) -> Scenario:
    """Read a strict JSON schema. No implicit defaults or hidden unit conversions."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load scenario {path}: {exc}") from exc

    _mapping(raw, {"scenario_id", "description", "initial_state", "duration_s", "body", "atmosphere", "numerics"}, "scenario")
    if not isinstance(raw["scenario_id"], str) or not raw["scenario_id"].strip():
        raise ValueError("scenario_id must be a nonempty string")
    if not isinstance(raw["description"], str):
        raise ValueError("description must be a string")

    body = _mapping(raw["body"], {"mass_kg", "reference_area_m2", "drag_coefficient"}, "body")
    atmosphere = _mapping(raw["atmosphere"], {"density_kg_m3", "wind_m_s", "gravity_m_s2"}, "atmosphere")
    numerics = _mapping(raw["numerics"], {"maximum_step_s", "reference_step_s", "convergence_steps_s", "timing_repetitions"}, "numerics")

    steps = numerics["convergence_steps_s"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("convergence_steps_s must be a nonempty list")
    convergence_steps = tuple(_positive(x, "convergence step") for x in steps)
    repetitions = numerics["timing_repetitions"]
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1 or repetitions > 100:
        raise ValueError("timing_repetitions must be an integer between 1 and 100")

    maximum_step = _positive(numerics["maximum_step_s"], "maximum_step_s")
    reference_step = _positive(numerics["reference_step_s"], "reference_step_s")
    duration = _positive(raw["duration_s"], "duration_s")
    if duration > 60:
        raise ValueError("offline demonstrator supports at most 60 seconds")
    if reference_step >= min(convergence_steps):
        raise ValueError("reference step must be finer than all convergence steps")
    if duration / min((maximum_step, reference_step, *convergence_steps)) > 500_000:
        raise ValueError("configuration requests too many numerical steps")

    return Scenario(
        scenario_id=raw["scenario_id"],
        description=raw["description"],
        initial_state=_vector(raw["initial_state"], 6, "initial_state"),
        duration_s=duration,
        body=Body(**body),
        atmosphere=Atmosphere(
            density_kg_m3=atmosphere["density_kg_m3"],
            wind_m_s=_vector(atmosphere["wind_m_s"], 3, "wind_m_s"),
            gravity_m_s2=atmosphere["gravity_m_s2"],
        ),
        maximum_step_s=maximum_step,
        reference_step_s=reference_step,
        convergence_steps_s=convergence_steps,
        timing_repetitions=repetitions,
    )
