"""Offline parameter-uncertainty utilities for the repository's canonical ODE.

Only fixed-time simulated states are studied. There is no target, release
calculation, ground-intersection event, or operational guidance.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .ballistic_model import model_rhs
from .parameters import Atmosphere, Body
from .trajectory import integrate


PARAMETER_NAMES = (
    "mass_kg", "reference_area_m2", "drag_coefficient", "density_kg_m3",
    "wind_e_m_s", "wind_n_m_s", "initial_vx_m_s", "initial_vy_m_s",
)
NONNEGATIVE_PARAMETERS = {"reference_area_m2", "drag_coefficient", "density_kg_m3"}
POSITIVE_PARAMETERS = {"mass_kg"}


@dataclass(frozen=True)
class UncertaintyPlan:
    study_id: str
    description: str
    seed: int
    sample_count: int
    integration_step_s: float
    diagnostic_step_s: float
    diagnostic_sample_count: int
    parameters: tuple[tuple[str, float], ...]


def _strict_object(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(f"{label} must contain exactly {sorted(required)}")
    return value


def _positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return float(value)


def _integer(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def load_uncertainty_plan(path: str | Path, scenario=None) -> UncertaintyPlan:
    """Load independent uniform half-widths; all ranges are illustrative.

    If a scenario is supplied, validate that every uncertainty interval stays
    within the parameters' physical domain and diagnostic resolution is finer.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"),
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {x}")))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load uncertainty specification {path}: {exc}") from exc
    _strict_object(raw, {"study_id", "description", "seed", "sample_count",
                         "integration_step_s", "diagnostic_step_s",
                         "diagnostic_sample_count", "parameters"}, "uncertainty study")
    if not isinstance(raw["study_id"], str) or not raw["study_id"].strip():
        raise ValueError("study_id must be a nonempty string")
    if not isinstance(raw["description"], str):
        raise ValueError("description must be a string")
    seed = _integer(raw["seed"], "seed", 0, 2**32 - 1)
    sample_count = _integer(raw["sample_count"], "sample_count", 16, 10000)
    diagnostic_count = _integer(raw["diagnostic_sample_count"], "diagnostic_sample_count", 1, sample_count)
    dt = _positive_number(raw["integration_step_s"], "integration_step_s")
    dt_check = _positive_number(raw["diagnostic_step_s"], "diagnostic_step_s")
    if dt_check >= dt:
        raise ValueError("diagnostic_step_s must be smaller than integration_step_s")
    values = raw["parameters"]
    if not isinstance(values, dict) or not values or set(values) - set(PARAMETER_NAMES):
        raise ValueError(f"parameters must be a nonempty mapping with names from {PARAMETER_NAMES}")
    params = tuple((name, _positive_number(half_width, name)) for name, half_width in values.items())
    if scenario is not None:
        nominal = nominal_parameters(scenario)
        for name, width in params:
            lower = nominal[name] - width
            if name in POSITIVE_PARAMETERS and lower <= 0:
                raise ValueError(f"{name} uncertainty includes nonpositive values")
            if name in NONNEGATIVE_PARAMETERS and lower < 0:
                raise ValueError(f"{name} uncertainty includes negative values")
        if scenario.duration_s / dt_check > 500_000:
            raise ValueError("diagnostic integration would require too many steps")
    return UncertaintyPlan(raw["study_id"], raw["description"], seed, sample_count,
                           dt, dt_check, diagnostic_count, params)


def nominal_parameters(scenario) -> dict[str, float]:
    """Extract the eight supported scalar inputs without changing the scenario."""
    return {
        "mass_kg": float(scenario.body.mass_kg),
        "reference_area_m2": float(scenario.body.reference_area_m2),
        "drag_coefficient": float(scenario.body.drag_coefficient),
        "density_kg_m3": float(scenario.atmosphere.density_kg_m3),
        "wind_e_m_s": float(scenario.atmosphere.wind_m_s[0]),
        "wind_n_m_s": float(scenario.atmosphere.wind_m_s[1]),
        "initial_vx_m_s": float(scenario.initial_state[3]),
        "initial_vy_m_s": float(scenario.initial_state[4]),
    }


def simulate_terminal_state(scenario, parameters: dict[str, float], step_s: float) -> np.ndarray:
    """Compute simulated state at a fixed elapsed time (not ground impact)."""
    expected = set(PARAMETER_NAMES)
    if set(parameters) != expected:
        raise ValueError("parameters must contain exactly the supported physical inputs")
    if not all(isinstance(v, (float, int, np.floating, np.integer)) and
               not isinstance(v, (bool, np.bool_)) and np.isfinite(v) for v in parameters.values()):
        raise ValueError("parameters must all be finite numbers")
    state0 = np.asarray(scenario.initial_state, dtype=float).copy()
    state0[3] = parameters["initial_vx_m_s"]
    state0[4] = parameters["initial_vy_m_s"]
    body = Body(parameters["mass_kg"], parameters["reference_area_m2"], parameters["drag_coefficient"])
    atmosphere = Atmosphere(
        density_kg_m3=parameters["density_kg_m3"],
        wind_m_s=(parameters["wind_e_m_s"], parameters["wind_n_m_s"], scenario.atmosphere.wind_m_s[2]),
        gravity_m_s2=scenario.atmosphere.gravity_m_s2,
    )
    rhs = lambda t, state: model_rhs(t, state, body, atmosphere)
    result = integrate(rhs, state0, scenario.duration_s, step_s, method="rk4")
    return result.states[-1].copy()


def independent_uniform_draws(plan: UncertaintyPlan, nominal: dict[str, float]) -> list[dict[str, float]]:
    """Seeded, independent uniform draws, one scalar per configured parameter."""
    rng = np.random.default_rng(plan.seed)
    names = [name for name, _ in plan.parameters]
    widths = np.array([delta for _, delta in plan.parameters], dtype=float)
    noise = rng.uniform(-1, 1, size=(plan.sample_count, len(names)))
    draws = []
    for row in noise:
        values = nominal.copy()
        for name, half_width, unit_noise in zip(names, widths, row):
            values[name] = nominal[name] + float(half_width * unit_noise)
        draws.append(values)
    return draws


def one_at_a_time(scenario, plan: UncertaintyPlan, nominal: dict[str, float], nominal_state: np.ndarray):
    """Symmetric perturbation for each parameter; a screening measure, not Sobol indices."""
    rows = []
    for name, half_width in plan.parameters:
        lower = nominal.copy()
        upper = nominal.copy()
        lower[name] -= half_width
        upper[name] += half_width
        low_state = simulate_terminal_state(scenario, lower, plan.integration_step_s)
        high_state = simulate_terminal_state(scenario, upper, plan.integration_step_s)
        half_span = (high_state[:3] - low_state[:3]) / 2.0
        rows.append({
            "parameter": name,
            "nominal": nominal[name],
            "half_width": half_width,
            "lower_value": lower[name],
            "upper_value": upper[name],
            "position_half_span_m": float(np.linalg.norm(half_span)),
            "delta_x_from_lower_to_upper_m": float(high_state[0] - low_state[0]),
            "delta_y_from_lower_to_upper_m": float(high_state[1] - low_state[1]),
            "delta_z_from_lower_to_upper_m": float(high_state[2] - low_state[2]),
            "lower_deviation_from_nominal_m": float(np.linalg.norm(low_state[:3] - nominal_state[:3])),
            "upper_deviation_from_nominal_m": float(np.linalg.norm(high_state[:3] - nominal_state[:3])),
        })
    return sorted(rows, key=lambda row: row["position_half_span_m"], reverse=True)


def percentile_summary(values) -> dict[str, float]:
    """Descriptive Monte Carlo statistics; no claim of physical confidence bounds."""
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1 or len(arr) < 2 or not np.all(np.isfinite(arr)):
        raise ValueError("statistics require at least two finite observations")
    return {
        "mean": float(arr.mean()),
        "standard_deviation": float(arr.std(ddof=1)),
        "p05": float(np.quantile(arr, 0.05)),
        "median": float(np.median(arr)),
        "p95": float(np.quantile(arr, 0.95)),
    }


def bootstrap_p95_interval(values, seed: int, replicates=400) -> tuple[float, float]:
    """Bootstrap interval for the finite-sample estimated p95, conditional on inputs."""
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1 or len(arr) < 16 or not np.all(np.isfinite(arr)):
        raise ValueError("bootstrap requires at least sixteen finite observations")
    replicates = _integer(replicates, "replicates", 50, 10000)
    rng = np.random.default_rng(seed + 1)
    bootstrap = np.empty(replicates, dtype=float)
    for i in range(replicates):
        sample = rng.choice(arr, len(arr), replace=True)
        bootstrap[i] = np.quantile(sample, 0.95)
    return tuple(float(x) for x in np.quantile(bootstrap, [0.025, 0.975]))
