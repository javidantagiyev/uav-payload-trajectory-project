"""build controlled gazebo environment experiments from an existing world."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PARAMETERS = {
    "wind_enu_m_s", "gravity_m_s2", "mass_kg", "size_xyz_m",
    "initial_xyz_rpy", "friction", "restitution", "physics_step_s",
    "wind_force_scale", "odometry_noise_std",
}


def _vector(value, length, name):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f"{name} must have {length} values")
    result = [float(x) for x in value]
    if not all(math.isfinite(x) for x in result):
        raise ValueError(f"{name} must be finite")
    return result


def validate_case(case):
    if set(case) != PARAMETERS:
        raise ValueError("environment case has missing or unknown parameters")
    wind = _vector(case["wind_enu_m_s"], 3, "wind_enu_m_s")
    size = _vector(case["size_xyz_m"], 3, "size_xyz_m")
    pose = _vector(case["initial_xyz_rpy"], 6, "initial_xyz_rpy")
    if any(s <= 0 for s in size) or pose[2] <= max(size):
        raise ValueError("invalid geometry or initial height")
    if any(abs(v) > 100 for v in wind):
        raise ValueError("wind exceeds declared screening bounds")
    for k in PARAMETERS - {"wind_enu_m_s", "size_xyz_m", "initial_xyz_rpy"}:
        if not isinstance(case[k], (int, float)) or not math.isfinite(case[k]):
            raise ValueError(f"{k} must be finite")
    if not 0 < case["gravity_m_s2"] <= 20:
        raise ValueError("invalid gravity")
    if not 0 < case["mass_kg"] <= 30:
        raise ValueError("invalid mass")
    if not 0 < case["physics_step_s"] <= 0.01:
        raise ValueError("invalid physics time step")
    if not 0 <= case["friction"] <= 3 or not 0 <= case["restitution"] <= 1:
        raise ValueError("invalid contact coefficients")
    if not 0 <= case["wind_force_scale"] <= 20:
        raise ValueError("invalid wind-force scale")
    if not 0 <= case["odometry_noise_std"] <= 1:
        raise ValueError("invalid odometry noise")
    return case


def load_cases(spec):
    if isinstance(spec, (str, Path)):
        spec = json.loads(Path(spec).read_text(encoding="utf-8"))
    if spec.get("design") != "one_factor_at_a_time":
        raise ValueError("unsupported design")
    baseline = dict(spec["baseline"])
    validate_case(baseline)
    cases = [("baseline", baseline)]
    ids = {"baseline"}
    for change in spec["variations"]:
        case_id = change["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", case_id) or case_id in ids:
            raise ValueError("invalid or duplicate case id")
        if not change["set"] or set(change["set"]) - PARAMETERS:
            raise ValueError("invalid variation keys")
        case = dict(baseline)
        case.update(change["set"])
        validate_case(case)
        ids.add(case_id)
        cases.append((case_id, case))
    return cases


def world_name(case_id):
    return f"env_{case_id}"


def _numbers(values):
    return " ".join(f"{float(x):.12g}" for x in values)


def render_world(template, case_id, case):
    validate_case(case)
    root = ET.fromstring(template)
    world = root.find("world")
    if world is None:
        raise ValueError("expected sdf world")
    world.set("name", world_name(case_id))
    world.find("gravity").text = _numbers((0, 0, -case["gravity_m_s2"]))
    world.find("physics/max_step_size").text = str(case["physics_step_s"])

    wind = world.find("wind")
    if wind is None:
        wind = ET.Element("wind")
        world.insert(1, wind)
    ET.SubElement(wind, "linear_velocity") if wind.find("linear_velocity") is None else None
    wind.find("linear_velocity").text = _numbers(case["wind_enu_m_s"])
    if not any(p.get("name") == "gz::sim::systems::WindEffects" for p in world.findall("plugin")):
        system = ET.Element("plugin", {
            "filename": "gz-sim-wind-effects-system",
            "name": "gz::sim::systems::WindEffects",
        })
        ET.SubElement(system, "force_approximation_scaling_factor").text = str(case["wind_force_scale"])
        world.insert(2, system)

    model = world.find("model[@name='inert_body']")
    if model is None:
        raise ValueError("missing inert_body model")
    model.find("pose").text = _numbers(case["initial_xyz_rpy"])
    link = model.find("link")
    link.find("inertial/mass").text = str(case["mass_kg"])
    x, y, z = case["size_xyz_m"]
    m = case["mass_kg"]
    inertia = link.find("inertial/inertia")
    for name, val in (("ixx", m * (y*y + z*z)/12),
                      ("iyy", m * (x*x + z*z)/12),
                      ("izz", m * (x*x + y*y)/12)):
        inertia.find(name).text = f"{val:.12g}"
    for shape in ("collision/geometry/box/size", "visual/geometry/box/size"):
        link.find(shape).text = _numbers(case["size_xyz_m"])
    for name in ("mu", "mu2"):
        link.find(f"collision/surface/friction/ode/{name}").text = str(case["friction"])
    link.find("collision/surface/bounce/restitution_coefficient").text = str(case["restitution"])
    link.find("sensor[@name='body_imu']")
    enable_wind = link.find("enable_wind")
    if enable_wind is None:
        enable_wind = ET.SubElement(link, "enable_wind")
    enable_wind.text = "true"
    model.find("plugin[@name='gz::sim::systems::OdometryPublisher']/gaussian_noise").text = str(case["odometry_noise_std"])
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def prepare_worlds(spec_path, template_path, output):
    spec_path = Path(spec_path)
    template_path = Path(template_path)
    output = Path(output)
    cases = load_cases(spec_path)
    template = template_path.read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "study_id": json.loads(spec_path.read_text(encoding="utf-8"))["study_id"],
        "status": "prepared_not_simulated",
        "design": "one_factor_at_a_time",
        "simulator": "gazebo harmonic 8",
        "wind_model": "gazebo windeffects simplified force model",
        "position_source": "gazebo odometry; noisy_odometry case is not ground truth",
        "source_config_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        "source_world_sha256": hashlib.sha256(template_path.read_bytes()).hexdigest(),
        "cases": [],
    }
    for case_id, case in cases:
        content = render_world(template, case_id, case)
        path = output / (world_name(case_id) + ".sdf")
        path.write_text(content, encoding="utf-8")
        manifest["cases"].append({
            "id": case_id,
            "world": str(path),
            "world_name": world_name(case_id),
            "parameters": case,
            "sdf_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    (output / "scenario_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
