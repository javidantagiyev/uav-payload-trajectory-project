"""Inspect a downloaded Cabauw file, convert to ENU, and run Stage-4 evaluation.

Run only after the raw NetCDF has been acquired via KNMI API and its source noted.
"""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.inspect_knmi_cabauw import inspect_file
from experiments.convert_tower_netcdf import convert_file
from experiments.validate_observed_wind_profiles import run as evaluate


def execute(netcdf, manifest, mapping, out, max_times=None):
    netcdf = Path(netcdf)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    schema = inspect_file(netcdf, mapping, manifest)
    (out / "netcdf_schema_inspection.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    csv_path = out / "cabauw_observations_enu.csv"
    metadata_path = out / "cabauw_observations.metadata.json"
    row_count = convert_file(netcdf, mapping, csv_path, metadata_path,
             provider="KNMI", dataset_id="cesar_tower_meteo_lb1_t10",
             dataset_version="v1.3",
             source_url="https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3",
             station="CABAUW", license_name="CC-BY-4.0", data_kind="observed", max_times=max_times)
    if row_count < 1:
        raise ValueError("conversion produced no rows")
    model_report = evaluate(csv_path, metadata_path, out / "comparison")
    summary = {
        "status": "real_observation_comparison_conditional_on_provider_quality_and_metadata",
        "source": "KNMI Cabauw tower meteo lb1 v1.3",
        "raw_sha256": schema["sha256"],
        "manifest_checksum_verified": schema["provenance"] == "checksum_matches_locally_recorded_knmi_download_manifest",
        "observations_converted": row_count,
        "profiles": model_report["profile_count"],
        "eligible_model_rows": model_report["eligible_rows"],
        "wind_height_validity_used_m": model_report["declared_surface_layer_valid_height_agl_m"],
        "figures": model_report["figures"],
        "model_metrics": model_report["model_metrics"],
        "limitations": [
            "observed wind profiles do not validate UAV or payload physics",
            "10-40m surface-layer gate is illustrative and must be physically justified",
            "monin-obukhov length candidates are not inferred from flux measurements",
            "tower data need careful native quality-flag and boom-change interpretation",
            "single-site observational agreement cannot establish performance at 500m",
            "source identity is supported by official download workflow and local checksum, not cryptographically authenticated provider contents",
        ],
    }
    (out / "stage5_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netcdf",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--mapping",type=Path,default=ROOT/"data/examples/knmi_cabauw_tower_profile_mapping.json")
    p.add_argument("--out",type=Path,default=ROOT/"results/atmospheric_testbed/6g_stage5/verified")
    p.add_argument("--max-times",type=int,help="optional restricted sample count for fast smoke test")
    a=p.parse_args()
    result=execute(a.netcdf,a.manifest,a.mapping,a.out,a.max_times)
    print(json.dumps({k:result[k] for k in ("status", "manifest_checksum_verified",
           "observations_converted", "profiles", "eligible_model_rows", "figures")}, indent=2))

if __name__=="__main__":main()
