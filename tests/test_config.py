import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

"""Tests for strict experiment configuration loading."""

import json
from pathlib import Path

import pytest

from src.physics.config import load_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_config_loads_with_expected_units():
    cfg = load_scenario(ROOT / "configs" / "baseline.json")
    assert cfg.scenario_id == "baseline_lab_v1"
    assert cfg.initial_state == (0.0, 0.0, 12.0, 1.5, 0.5, 0.0)
    assert cfg.atmosphere.gravity_m_s2 == pytest.approx(9.81)
    assert cfg.reference_step_s < min(cfg.convergence_steps_s)


def test_invalid_json_fails_loudly(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{broken json", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot load scenario"):
        load_scenario(p)


@pytest.mark.parametrize("field, replacement", [
    ("initial_state", [0, 0]),
    ("initial_state", [0, 0, 1, 0, 0, float('nan')]),
    ("duration_s", -1),
    ("scenario_id", ""),
])
def test_invalid_scenario_rejected(tmp_path, field, replacement):
    original = json.loads((ROOT / "configs" / "baseline.json").read_text())
    original[field] = replacement
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenario(p)


def test_missing_configuration_field_rejected(tmp_path):
    original = json.loads((ROOT / "configs" / "baseline.json").read_text())
    del original["numerics"]["reference_step_s"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="numerics"):
        load_scenario(p)


def test_reference_must_be_finer_than_comparison_grid(tmp_path):
    original = json.loads((ROOT / "configs" / "baseline.json").read_text())
    original["numerics"]["reference_step_s"] = 0.1
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="finer"):
        load_scenario(p)


def test_bool_rejected_in_numeric_position(tmp_path):
    original = json.loads((ROOT / "configs" / "baseline.json").read_text())
    original["initial_state"][0] = True
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="finite numeric"):
        load_scenario(p)
