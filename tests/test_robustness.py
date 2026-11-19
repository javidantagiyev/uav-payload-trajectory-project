"""tests for scenario variants and bounded uncertainty priors."""

import json
from pathlib import Path

import numpy as np
import pytest

from src.physics import load_scenario
from src.physics.robustness import apply_variant, draw_uncertain_parameters, load_robustness_plan
from src.physics.uncertainty import load_uncertainty_plan, nominal_parameters

ROOT = Path(__file__).resolve().parents[1]


def _objects():
    scenario = load_scenario(ROOT / "configs/baseline.json")
    uncertainty = load_uncertainty_plan(ROOT / "configs/uncertainty_study.json", scenario)
    plan = load_robustness_plan(ROOT / "configs/robustness_study.json")
    return scenario, uncertainty, plan


def test_plan_loads():
    scenario, uncertainty, plan = _objects()
    assert len(plan.variants) == 6
    assert set(plan.distributions) == {"uniform", "triangular", "beta22"}
    assert uncertainty.sample_count >= plan.sample_count


def test_variant_does_not_mutate_baseline():
    scenario, _, _ = _objects()
    changed = apply_variant(scenario, {"density_kg_m3": 0.9, "wind_e_m_s": 0.5})
    assert changed.atmosphere.density_kg_m3 == 0.9
    assert changed.atmosphere.wind_m_s[0] == 0.5
    assert scenario.atmosphere.density_kg_m3 == 1.225
    assert scenario.atmosphere.wind_m_s == (0.0, 0.0, 0.0)


def test_invalid_body_parameter_fails():
    scenario, _, _ = _objects()
    with pytest.raises(ValueError):
        apply_variant(scenario, {"mass_kg": -1})
    with pytest.raises(ValueError):
        apply_variant(scenario, {"unknown": 7})


@pytest.mark.parametrize("distribution", ["uniform", "triangular", "beta22"])
def test_draws_are_bounded_reproducible(distribution):
    scenario, uncertainty, plan = _objects()
    a = draw_uncertain_parameters(plan, uncertainty, scenario, distribution)
    b = draw_uncertain_parameters(plan, uncertainty, scenario, distribution)
    assert a == b
    assert len(a) == plan.sample_count
    nominal = nominal_parameters(scenario)
    for row in a:
        for name, width in uncertainty.parameters:
            assert abs(row[name] - nominal[name]) <= width + 1e-12


def test_priors_change_spread_without_changing_bounds():
    scenario, uncertainty, plan = _objects()
    widths = dict(uncertainty.parameters)
    nominal = nominal_parameters(scenario)
    a = draw_uncertain_parameters(plan, uncertainty, scenario, "uniform")
    b = draw_uncertain_parameters(plan, uncertainty, scenario, "triangular")
    name = "wind_e_m_s"
    wa = np.array([(r[name] - nominal[name]) / widths[name] for r in a])
    wb = np.array([(r[name] - nominal[name]) / widths[name] for r in b])
    assert not np.allclose(wa, wb)


def test_duplicate_variant_rejected(tmp_path):
    obj = json.loads((ROOT / "configs/robustness_study.json").read_text())
    obj["variants"][1]["id"] = "nominal"
    file = tmp_path / "bad.json"
    file.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="unique"):
        load_robustness_plan(file)


def test_invalid_distribution_rejected(tmp_path):
    obj = json.loads((ROOT / "configs/robustness_study.json").read_text())
    obj["distributions"].append("gaussian")
    file = tmp_path / "bad.json"
    file.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="distributions"):
        load_robustness_plan(file)


def test_invalid_resolution_rejected(tmp_path):
    obj = json.loads((ROOT / "configs/robustness_study.json").read_text())
    obj["fine_step_s"] = obj["step_s"]
    file = tmp_path / "bad.json"
    file.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="finer|smaller"):
        load_robustness_plan(file)
