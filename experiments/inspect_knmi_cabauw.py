"""Fail-closed inventory for a real monthly Cabauw NetCDF before conversion."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = ROOT / "data/examples/knmi_cabauw_tower_profile_mapping.json"
sys.path.insert(0, str(ROOT))
from experiments.knmi_tower_schema import resolve_wind_levels


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalized_units(value):
    return str(value).lower().strip().replace(" ", "")


def inspect_file(netcdf, mapping, manifest_path=None, max_times=1000):
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("install xarray and scipy or netcdf4 to inspect NetCDF") from exc
    netcdf = Path(netcdf)
    mapping = json.loads(Path(mapping).read_text(encoding="utf-8"))
    if not netcdf.is_file():
        raise FileNotFoundError(netcdf)
    checksum = file_sha256(netcdf)
    provenance = "file_supplied_without_download_manifest"
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if (manifest.get("sha256") != checksum or manifest.get("filename") != netcdf.name or
                manifest.get("dataset") != "cesar_tower_meteo_lb1_t10" or manifest.get("version") != "v1.3"):
            raise ValueError("file checksum/name/dataset/version do not match the download manifest")
        provenance = "checksum_matches_locally_recorded_knmi_download_manifest"
    result = {"status": "raw_schema_inspected_not_field_validation", "netcdf_file": str(netcdf),
              "sha256": checksum, "provenance": provenance, "variables": [],
              "quality_flag_candidates": [], "levels": {}, "warnings": []}
    with xr.open_dataset(netcdf) as ds:
        result["dimensions"] = {str(k): int(v) for k, v in ds.sizes.items()}
        result["file_attributes"] = {str(k): str(v)[:500] for k, v in ds.attrs.items()
                                     if k.lower() in ("title", "institution", "history", "source", "references", "version", "date_created")}
        result["variables"] = list(ds.variables)
        result["quality_flag_candidates"] = [name for name in ds.variables
                       if any(s in name.lower() for s in ("qc", "quality", "flag", "status"))]
        tname = mapping.get("time")
        if not tname or tname not in ds:
            raise ValueError("mapped time coordinate missing")
        times = np.asarray(ds[tname].values)
        if times.ndim != 1 or not np.issubdtype(times.dtype, np.datetime64):
            raise ValueError("time coordinate does not decode to 1D datetime64")
        if not len(times):
            raise ValueError("time coordinate empty")
        if np.isnat(times).any() or np.any(np.diff(times.astype("datetime64[ns]").astype(np.int64)) <= 0):
            raise ValueError("missing or non-increasing time coordinates")
        result["time_start_utc_assumed_from_cf"] = np.datetime_as_string(times[0], unit="s") + "Z"
        result["time_end_utc_assumed_from_cf"] = np.datetime_as_string(times[-1], unit="s") + "Z"
        result["time_count"] = len(times)
        result["time_calendar"] = str(ds[tname].encoding.get("calendar", "standard"))
        if len(times) < 2:
            result["warnings"].append("only one time sample; temporal analysis cannot proceed")
        for z, speed_key, direction_key, s, d in resolve_wind_levels(ds, mapping, tname):
            speed = np.asarray(s.values[:max_times], dtype=float)
            direction = np.asarray(d.values[:max_times], dtype=float)
            valid = np.isfinite(speed) & np.isfinite(direction) & (speed >= 0) & (direction >= 0) & (direction <= 360)
            item = {"speed_var": speed_key, "direction_from_var": direction_key,
                    "speed_units": s.attrs.get("units"), "direction_units": d.attrs.get("units"),
                    "speed_long_name": str(s.attrs.get("long_name", "")),
                    "direction_long_name": str(d.attrs.get("long_name", "")),
                    "valid_fraction_first_samples": float(valid.mean()) if len(valid) else 0.0,
                    "inspected_samples": len(valid),
                    "sample_max_speed_m_s": float(np.max(speed[np.isfinite(speed)])) if np.any(np.isfinite(speed)) else None}
            result["levels"][str(z)] = item
            if item["valid_fraction_first_samples"] < .5:
                result["warnings"].append(f"over half early {z:g} m observations invalid; inspect missing-value conventions")
        result["warnings"].append("wind direction is assumed meteorological FROM; confirm native variable definitions")
        result["warnings"].append("quality flags and instrument boom corrections are provider-dependent; inspect attributes before analysis")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--netcdf", required=True, type=Path)
    p.add_argument("--mapping", default=DEFAULT_MAPPING, type=Path)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = inspect_file(args.netcdf, args.mapping, args.manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "time_count": result["time_count"],
                      "start": result["time_start_utc_assumed_from_cf"],
                      "end": result["time_end_utc_assumed_from_cf"],
                      "levels_verified": sorted(result["levels"], key=float),
                      "warnings": result["warnings"]}, indent=2))


if __name__ == "__main__":
    main()
