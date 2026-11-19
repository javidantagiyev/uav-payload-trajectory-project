"""Unit checks for the illustrative parameter-uncertainty utilities."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from src.physics import load_scenario
from src.physics.uncertainty import (
    PARAMETER_NAMES, bootstrap_p95_interval, independent_uniform_draws,
    load_uncertainty_plan, nominal_parameters, one_at_a_time,
    percentile_summary, simulate_terminal_state,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "configs" / "baseline.json"
UNCERTAINTY = ROOT / "configs" / "uncertainty_study.json"


def test_baseline_uncertainty_plan_is_valid():
    scenario = load_scenario(BASELINE)
    plan = load_uncertainty_plan(UNCERTAINTY, scenario)
    assert plan.sample_count == 256
    assert plan.diagnostic_step_s < plan.integration_step_s
    assert len(plan.parameters) == 8
    assert {name for name, _ in plan.parameters} == set(PARAMETER_NAMES)


def test_draws_are_seeded_and_within_configured_intervals():
    scenario = load_scenario(BASELINE)
    plan = load_uncertainty_plan(UNCERTAINTY, scenario)
    nominal = nominal_parameters(scenario)
    a = independent_uniform_draws(plan, nominal)
    b = independent_uniform_draws(plan, nominal)
    assert a == b
    assert len(a) == plan.sample_count
    for row in a:
        for name, width in plan.parameters:
            assert nominal[name] - width <= row[name] <= nominal[name] + width
    assert independent_uniform_draws(replace(plan, seed=plan.seed + 1), nominal) != a


@pytest.mark.parametrize("field,value", [
    ("seed", True), ("sample_count", 0), ("sample_count", 3.0),
    ("integration_step_s", 0), ("diagnostic_step_s", 0.1),
    ("diagnostic_sample_count", 257), ("parameters", {}),
    ("study_id", ""),
])
def test_invalid_plan_values_are_rejected(tmp_path, field, value):
    obj = json.loads(UNCERTAINTY.read_text(encoding="utf-8"))
    obj[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError):
        load_uncertainty_plan(path, load_scenario(BASELINE))


def test_uncertainty_below_physical_parameter_domain_is_rejected(tmp_path):
    obj = json.loads(UNCERTAINTY.read_text(encoding="utf-8"))
    obj["parameters"]["mass_kg"] = 0.5
    path = tmp_path / "bad_mass.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="mass_kg"):
        load_uncertainty_plan(path, load_scenario(BASELINE))


def test_uncertainty_rejects_unknown_parameter_name(tmp_path):
    obj = json.loads(UNCERTAINTY.read_text(encoding="utf-8"))
    obj["parameters"]["arbitrary_field"] = 1.0
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="parameters"):
        load_uncertainty_plan(path, load_scenario(BASELINE))


def test_nan_json_constant_is_rejected(tmp_path):
    path = tmp_path / "nan.json"
    path.write_text(UNCERTAINTY.read_text().replace("0.04", "NaN"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_uncertainty_plan(path, load_scenario(BASELINE))


def test_simulation_does_not_mutate_scenario_or_input_dictionary():
    scenario = load_scenario(BASELINE)
    nominal = nominal_parameters(scenario)
    copy = nominal.copy()
    before = tuple(scenario.initial_state)
    state = simulate_terminal_state(scenario, nominal, 0.025)
    assert state.shape == (6,)
    assert np.all(np.isfinite(state))
    assert nominal == copy
    assert tuple(scenario.initial_state) == before


def test_nominal_endpoint_changes_with_initial_horizontal_velocity():
    scenario = load_scenario(BASELINE)
    nominal = nominal_parameters(scenario)
    end0 = simulate_terminal_state(scenario, nominal, 0.025)
    altered = nominal.copy()
    altered["initial_vx_m_s"] += 0.1
    end1 = simulate_terminal_state(scenario, altered, 0.025)
    assert end1[0] > end0[0]
    assert abs(end1[0] - end0[0]) > .05


def test_invalid_simulation_parameter_vector_is_rejected():
    scenario = load_scenario(BASELINE)
    nominal = nominal_parameters(scenario)
    with pytest.raises(ValueError):
        simulate_terminal_state(scenario, {"mass_kg": 0.4}, .025)
    with pytest.raises(ValueError):
        simulate_terminal_state(scenario, {**nominal, "wind_e_m_s": float("nan")}, .025)
    with pytest.raises(ValueError):
        simulate_terminal_state(scenario, {**nominal, "mass_kg": 0}, .025)


def test_one_at_a_time_screening_has_one_result_per_parameter():
    scenario = load_scenario(BASELINE)
    plan = load_uncertainty_plan(UNCERTAINTY, scenario)
    nominal = nominal_parameters(scenario)
    end = simulate_terminal_state(scenario, nominal, plan.integration_step_s)
    rows = one_at_a_time(scenario, plan, nominal, end)
    assert len(rows) == 8
    assert {row["parameter"] for row in rows} == set(PARAMETER_NAMES)
    assert all(row["position_half_span_m"] >= 0 for row in rows)
    assert all(rows[i]["position_half_span_m"] >= rows[i + 1]["position_half_span_m"]
               for i in range(len(rows) - 1))


def test_descriptive_quantiles_and_bootstrap_reproducible():
    a = np.linspace(0, 1, 32)
    stats = percentile_summary(a)
    assert stats["mean"] == pytest.approx(0.5)
    assert stats["p05"] < stats["median"] < stats["p95"]
    ci1 = bootstrap_p95_interval(a, seed=33, replicates=100)
    ci2 = bootstrap_p95_interval(a, seed=33, replicates=100)
    assert ci1 == ci2
    assert 0 <= ci1[0] <= ci1[1] <= 1


def test_invalid_statistics_are_rejected():
    with pytest.raises(ValueError):
        percentile_summary([1])
    with pytest.raises(ValueError):
        bootstrap_p95_interval([1, 2, 3], seed=1)


def test_drag_loading_cannot_identify_mass_and_area_separately():
    """Scaling mass and area together leaves the point-mass drag acceleration unchanged."""
    scenario = load_scenario(BASELINE)
    nominal = nominal_parameters(scenario)
    altered = nominal.copy()
    altered["mass_kg"] *= 2
    altered["reference_area_m2"] *= 2
    a = simulate_terminal_state(scenario, nominal, 0.025)
    b = simulate_terminal_state(scenario, altered, 0.025)
    assert np.allclose(a, b, atol=1e-12, rtol=0)
