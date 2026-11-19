"""test headless batch control commands without launching gazebo."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sim/gazebo/scripts/run_environment_batch.py"


def test_control_command_is_correct():
    import importlib.util
    spec = importlib.util.spec_from_file_location("environment_batch_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cmd = module.control_command("env_baseline")
    assert cmd[:4] == ["gz", "service", "-s", "/world/env_baseline/control"]
    assert "pause: false" in cmd


def test_dry_run_requires_worlds_and_does_not_start_gazebo(tmp_path):
    from src.physics.environmental_matrix import prepare_worlds
    worlds = tmp_path / "worlds"
    prepare_worlds(ROOT / "configs/environment_matrix.json",
                   ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf", worlds)
    run = subprocess.run([sys.executable, str(SCRIPT), "--worlds", str(worlds),
                          "--cases", "baseline", "wind_east_4"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "dry_run_no_simulator_started" in run.stdout
