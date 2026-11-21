"""6f batch generator and dry-run tests without requiring gazebo."""

import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.physics.environmental_matrix import prepare_worlds

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sim/gazebo/scripts/run_simtime_matrix.py"


def load_script():
    spec = importlib.util.spec_from_file_location("run_simtime_matrix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_rate_copies_sdf_without_touching_source(tmp_path):
    mod = load_script()
    source = ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf"
    first = source.read_bytes()
    target = tmp_path / "rate.sdf"
    digest = mod.prepare_rate_world(source, target, 200)
    assert len(digest) == 64
    assert first == source.read_bytes()
    root = ET.parse(target)
    assert root.findtext("world/model[@name='inert_body']/plugin/odom_publish_frequency") == "200"


def test_rate_cannot_exceed_physics_frequency(tmp_path):
    mod = load_script()
    source = ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf"
    with pytest.raises(ValueError, match="physics"):
        mod.prepare_rate_world(source, tmp_path / "bad.sdf", 2000)


def test_dry_run_has_no_runtime_side_effects(tmp_path):
    worlds = tmp_path / "worlds"
    prepare_worlds(ROOT / "configs/environment_matrix.json",
                   ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf", worlds)
    results = tmp_path / "runs"
    cmd = [sys.executable, str(SCRIPT), "--worlds", str(worlds),
           "--output", str(results), "--cases", "baseline", "wind_east_4",
           "--duration-s", "1", "--repeats", "4"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert '"total_runs": 8' in p.stdout
    assert not results.exists()
