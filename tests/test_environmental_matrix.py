"""environment scenario schema and sdf transformation tests."""

import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from src.physics.environmental_matrix import (load_cases, prepare_worlds,
                                              render_world, validate_case)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/environment_matrix.json"
TEMPLATE = ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf"


def test_coverage_matrix_is_unique_and_controlled():
    cases = load_cases(CONFIG)
    assert len(cases) == 20
    assert len(set(k for k, _ in cases)) == len(cases)
    baseline = cases[0][1]
    for case_id, case in cases[1:]:
        assert case != baseline, case_id
        assert all(k in baseline for k in case)


def test_wind_vector_and_plugin_are_both_present():
    case = dict(load_cases(CONFIG)[0][1])
    case["wind_enu_m_s"] = [4, -2, 1]
    root = ET.fromstring(render_world(TEMPLATE.read_text(), "custom", case))
    world = root.find("world")
    assert world.get("name") == "env_custom"
    assert world.findtext("wind/linear_velocity") == "4 -2 1"
    plugin = world.find("plugin[@name='gz::sim::systems::WindEffects']")
    assert plugin is not None
    assert plugin.get("filename") == "gz-sim-wind-effects-system"
    assert world.findtext("model[@name='inert_body']/link/enable_wind") == "true"


def test_mass_changes_inertia_consistently():
    case = dict(load_cases(CONFIG)[0][1])
    case["mass_kg"] = 2.4
    root = ET.fromstring(render_world(TEMPLATE.read_text(), "heavy", case))
    link = root.find("world/model[@name='inert_body']/link")
    assert float(link.findtext("inertial/mass")) == 2.4
    for k, expected in (("ixx", 2.4*(0.3**2 + 0.2**2)/12),
                        ("iyy", 2.4*(0.48**2 + 0.2**2)/12),
                        ("izz", 2.4*(0.48**2 + 0.3**2)/12)):
        assert float(link.findtext("inertial/inertia/" + k)) == pytest.approx(expected)


def test_noisy_odometry_flag_is_explicit():
    case = next(v for k, v in load_cases(CONFIG) if k == "noisy_odometry")
    root = ET.fromstring(render_world(TEMPLATE.read_text(), "noisy_odometry", case))
    assert float(root.findtext("world/model[@name='inert_body']/plugin/gaussian_noise")) > 0


@pytest.mark.parametrize("parameter,value", [
    ("mass_kg", 0), ("gravity_m_s2", -1), ("physics_step_s", 0),
    ("restitution", 1.1), ("friction", -0.1),
    ("wind_enu_m_s", [float("nan"), 0, 0]),
    ("size_xyz_m", [0, 1, 1]), ("wind_force_scale", -1),
])
def test_invalid_case_is_rejected(parameter, value):
    case = copy.deepcopy(load_cases(CONFIG)[0][1])
    case[parameter] = value
    with pytest.raises(ValueError):
        validate_case(case)


def test_duplicate_id_is_rejected():
    spec = json.loads(CONFIG.read_text())
    spec["variations"].append(copy.deepcopy(spec["variations"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(spec)


def test_generator_provides_hashes_and_no_legacy_mutation(tmp_path):
    original = TEMPLATE.read_bytes()
    manifest = prepare_worlds(CONFIG, TEMPLATE, tmp_path)
    assert len(manifest["cases"]) == 20
    assert TEMPLATE.read_bytes() == original
    assert (tmp_path / "scenario_manifest.json").exists()
    for item in manifest["cases"]:
        assert Path(item["world"]).exists()
        assert len(item["sdf_sha256"]) == 64
        ET.parse(item["world"])


def test_wind_model_reference_and_reproducibility():
    import numpy as np
    from src.physics.wind_model import (power_law_wind, log_law_wind,
                                        discrete_gust, turbulence_series)
    w = (5.0, 0, 0)
    assert power_law_wind(w, 10, 1/7)(0, (0, 0, 10)) == pytest.approx(w)
    assert log_law_wind(w, 10, .03)(0, (0, 0, 10)) == pytest.approx(w)
    gust = discrete_gust(w, (2, 0, 0), 3, 4)
    assert gust(3, (0, 0, 10))[0] == pytest.approx(5)
    assert gust(5, (0, 0, 10))[0] == pytest.approx(7)
    a = turbulence_series((1,.5,.2), 30, 8, 3, .01, seed=2026)[1]
    b = turbulence_series((1,.5,.2), 30, 8, 3, .01, seed=2026)[1]
    assert np.array_equal(a, b)


def test_isa_density_decreases_over_500m():
    from src.physics.atmosphere import isa_density
    assert isa_density(500) < isa_density(0)
