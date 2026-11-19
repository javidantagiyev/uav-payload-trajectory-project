"""read-only check of installed px4 gazebo wind coupling declarations."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def inspect(px4_root):
    px4_root = Path(px4_root)
    world = px4_root / "Tools/simulation/gz/worlds/windy.sdf"
    model = px4_root / "Tools/simulation/gz/models/x500_base/model.sdf"
    report = {
        "source_world": str(world),
        "source_model": str(model),
        "world_exists": world.is_file(),
        "model_exists": model.is_file(),
        "world_has_wind_system": False,
        "wind_velocity_declared_enu_m_s": None,
        "base_link_wind_enabled": False,
        "physics_wind_response_verified": False,
        "notes": ["sdf configuration checks cannot prove actual wind forces on the vehicle"],
    }
    if world.is_file():
        r = ET.parse(world).getroot()
        report["world_has_wind_system"] = any(
            "WindEffects" in (p.get("name", "") + p.get("filename", ""))
            for p in r.findall(".//plugin")
        )
        declaration = r.find(".//world/wind/linear_velocity")
        if declaration is not None and declaration.text:
            try:
                report["wind_velocity_declared_enu_m_s"] = [float(x) for x in declaration.text.split()]
            except ValueError:
                report["notes"].append("world wind declaration is not numeric")
    if model.is_file():
        r = ET.parse(model).getroot()
        links = r.findall(".//link")
        report["links"] = [{"name": link.get("name"),
                             "wind_enabled": link.findtext("enable_wind", "false").strip().lower() == "true"}
                            for link in links]
        report["base_link_wind_enabled"] = any(
            link["name"] == "base_link" and link["wind_enabled"] for link in report["links"]
        )
    report["configuration_ready_for_wind_response_test"] = bool(
        report["world_has_wind_system"] and report["base_link_wind_enabled"]
    )
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--px4-root", type=Path, default=Path.home() / "projects/PX4-Autopilot")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    result = inspect(args.px4_root)
    serialized = json.dumps(result, indent=2) + "\n"
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
