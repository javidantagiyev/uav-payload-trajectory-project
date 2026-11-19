"""controlled scenario and uncertainty-distribution comparisons."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .parameters import Atmosphere, Body
from .uncertainty import nominal_parameters

ALLOWED_OVERRIDES = {
    "mass_kg", "reference_area_m2", "drag_coefficient",
    "density_kg_m3", "wind_e_m_s", "wind_n_m_s", "wind_u_m_s",
}
DISTRIBUTIONS = {"uniform", "triangular", "beta22"}


@dataclass(frozen=True)
class RobustnessPlan:
    study_id: str
    seed: int
    sample_count: int
    step_s: float
    fine_step_s: float
    distributions: tuple[str, ...]
    variants: tuple[tuple[str, str, dict[str, float]], ...]


def _number(value, label, minimum=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not np.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if minimum is not None and (value <= minimum if strict else value < minimum):
        raise ValueError(f"{label} violates its physical bounds")
    return float(value)


def load_robustness_plan(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"),
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite json value")))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid robustness configuration: {exc}") from exc
    expected = {"study_id", "seed", "sample_count", "step_s", "fine_step_s", "distributions", "variants"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("invalid robustness configuration keys")
    if not isinstance(raw["study_id"], str) or not raw["study_id"].strip():
        raise ValueError("study_id must be nonempty")
    seed, count = raw["seed"], raw["sample_count"]
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("seed must be a nonnegative integer")
    if isinstance(count, bool) or not isinstance(count, int) or not 16 <= count <= 5000:
        raise ValueError("sample_count must be between 16 and 5000")
    step = _number(raw["step_s"], "step_s", 0, True)
    fine = _number(raw["fine_step_s"], "fine_step_s", 0, True)
    if fine >= step:
        raise ValueError("fine_step_s must be smaller than step_s")
    distributions = raw["distributions"]
    if (not isinstance(distributions, list) or not distributions or
            any(not isinstance(x, str) for x in distributions) or
            len(set(distributions)) != len(distributions) or set(distributions) - DISTRIBUTIONS):
        raise ValueError("invalid uncertainty distributions")
    variants = raw["variants"]
    if not isinstance(variants, list) or not 1 <= len(variants) <= 20:
        raise ValueError("variants must be a nonempty list of at most 20")
    cleaned = []
    ids = set()
    for variant in variants:
        if not isinstance(variant, dict) or set(variant) != {"id", "description", "overrides"}:
            raise ValueError("invalid variant")
        name, description, overrides = variant["id"], variant["description"], variant["overrides"]
        if not isinstance(name, str) or not name.strip() or name in ids:
            raise ValueError("variant ids must be unique nonempty strings")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("variant description must be nonempty")
        if not isinstance(overrides, dict) or set(overrides) - ALLOWED_OVERRIDES:
            raise ValueError("unsupported scenario override")
        validated = {}
        for key, value in overrides.items():
            lower = 0 if key in {"mass_kg", "reference_area_m2", "drag_coefficient", "density_kg_m3"} else None
            validated[key] = _number(value, key, lower, key == "mass_kg")
        ids.add(name)
        cleaned.append((name, description, validated))
    if not any(len(v[2]) == 0 for v in cleaned):
        raise ValueError("include a nominal variant with empty overrides")
    return RobustnessPlan(raw["study_id"], seed, count, step, fine, tuple(distributions), tuple(cleaned))


def apply_variant(scenario, changes):
    """return new immutable scenario objects for overridden model parameters."""
    if set(changes) - ALLOWED_OVERRIDES:
        raise ValueError("unsupported scenario override")
    body = scenario.body
    atmosphere = scenario.atmosphere
    b = {key: getattr(body, key) for key in ("mass_kg", "reference_area_m2", "drag_coefficient")}
    a = {"density_kg_m3": atmosphere.density_kg_m3,
         "gravity_m_s2": atmosphere.gravity_m_s2,
         "wind_m_s": list(atmosphere.wind_m_s)}
    for key, value in changes.items():
        _number(value, key)
        if key in b:
            b[key] = value
        elif key == "density_kg_m3":
            a[key] = value
        else:
            a["wind_m_s"][("wind_e_m_s", "wind_n_m_s", "wind_u_m_s").index(key)] = value
    return replace(scenario, body=Body(**b), atmosphere=Atmosphere(**a))


def draw_uncertain_parameters(plan, uncertain_plan, baseline, distribution):
    """draw fixed-in-time uncertain parameters from bounded inputs."""
    if distribution not in DISTRIBUTIONS:
        raise ValueError("unsupported uncertainty distribution")
    names = [name for name, _ in uncertain_plan.parameters]
    widths = np.array([width for _, width in uncertain_plan.parameters])
    nominal = nominal_parameters(baseline)
    rng = np.random.default_rng(plan.seed)
    shape = (plan.sample_count, len(names))
    if distribution == "uniform":
        deviations = rng.uniform(-1, 1, shape)
    elif distribution == "triangular":
        deviations = rng.triangular(-1, 0, 1, shape)
    else:
        deviations = 2 * rng.beta(2, 2, shape) - 1
    return [dict(nominal, **{
        name: nominal[name] + float(width * draw)
        for name, width, draw in zip(names, widths, row)
    }) for row in deviations]
