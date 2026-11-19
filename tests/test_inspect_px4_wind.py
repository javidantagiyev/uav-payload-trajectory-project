"""verify that px4 configuration audits do not imply physical validation."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sim/gazebo/scripts/inspect_px4_wind.py"


def get_inspector():
    spec = importlib.util.spec_from_file_location("px4_wind_inspector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect


def test_missing_px4_files_do_not_pass(tmp_path):
    result = get_inspector()(tmp_path)
    assert not result["configuration_ready_for_wind_response_test"]
    assert not result["physics_wind_response_verified"]
    assert not result["world_exists"]


def test_wind_plugin_without_link_enable_is_not_ready(tmp_path):
    world = tmp_path / "Tools/simulation/gz/worlds/windy.sdf"
    model = tmp_path / "Tools/simulation/gz/models/x500_base/model.sdf"
    world.parent.mkdir(parents=True)
    model.parent.mkdir(parents=True)
    world.write_text('''<sdf><world name="windy"><wind><linear_velocity>4 0 0</linear_velocity></wind>
      <plugin name="gz::sim::systems::WindEffects" filename="gz-sim-wind-effects-system"/></world></sdf>''')
    model.write_text('''<sdf><model name="x500_base"><link name="base_link"><enable_wind>false</enable_wind></link></model></sdf>''')
    result = get_inspector()(tmp_path)
    assert result["world_has_wind_system"]
    assert result["wind_velocity_declared_enu_m_s"] == [4, 0, 0]
    assert not result["configuration_ready_for_wind_response_test"]
    model.write_text(model.read_text().replace("false", "true"))
    result = get_inspector()(tmp_path)
    assert result["configuration_ready_for_wind_response_test"]
    assert not result["physics_wind_response_verified"]
