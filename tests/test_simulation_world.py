"""validate static gazebo world geometry and configuration."""

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "sim/gazebo/worlds/rigid_body_lab.sdf"


def test_world_is_valid_xml_and_dynamic():
    root = ET.parse(WORLD).getroot()
    assert root.tag == "sdf"
    assert root.find("world").attrib["name"] == "rigid_body_lab"
    dynamic = root.find("world/model[@name='inert_body']")
    assert dynamic is not None
    assert dynamic.findtext("static") == "false"
    assert float(root.findtext("world/physics/max_step_size")) == pytest.approx(0.001)
    assert list(map(float, root.findtext("world/gravity").split())) == pytest.approx([0, 0, -9.81])


def test_box_inertia_matches_homogeneous_rectangular_rigid_body():
    root = ET.parse(WORLD).getroot()
    link = root.find("world/model[@name='inert_body']/link")
    size = [float(s) for s in link.findtext("collision/geometry/box/size").split()]
    m = float(link.findtext("inertial/mass"))
    inertial = link.find("inertial/inertia")
    expected = (
        m*(size[1]**2 + size[2]**2)/12,
        m*(size[0]**2 + size[2]**2)/12,
        m*(size[0]**2 + size[1]**2)/12,
    )
    actual = [float(inertial.findtext(k)) for k in ("ixx","iyy","izz")]
    assert actual == pytest.approx(expected, rel=1e-8)
    assert all(value > 0 for value in actual)
    assert float(link.findtext("inertial/mass")) > 0


def test_sensor_and_3d_odometry_declared():
    root = ET.parse(WORLD).getroot()
    model = root.find("world/model[@name='inert_body']")
    assert model.find("link/sensor[@type='imu']") is not None
    p = model.find("plugin[@name='gz::sim::systems::OdometryPublisher']")
    assert p is not None
    assert p.findtext("dimensions") == "3"
    assert p.findtext("odom_topic") == "/sdp/inert_body/odometry"
    assert float(p.findtext("gaussian_noise")) == 0
    plugins = [p.attrib["name"] for p in root.findall("world/plugin")]
    assert "gz::sim::systems::Physics" in plugins
    assert "gz::sim::systems::Sensors" in plugins


def test_scenario_config_matches_world():
    config = json.loads((ROOT / "configs/simulation_testbed.json").read_text(encoding="utf-8"))
    root = ET.parse(WORLD).getroot()
    link = root.find("world/model[@name='inert_body']/link")
    assert config["body"]["mass_kg"] == float(link.findtext("inertial/mass"))
    assert config["body"]["box_size_m"] == [float(x) for x in link.findtext("collision/geometry/box/size").split()]
    assert config["body"]["initial_pose_xyz_rpy"] == pytest.approx([float(x) for x in root.findtext("world/model[@name='inert_body']/pose").split()])
