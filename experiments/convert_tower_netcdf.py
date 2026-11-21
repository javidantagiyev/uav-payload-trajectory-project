"""Convert a user-acquired NetCDF tower file to the strict Stage-4 UTC/AGL/ENU format.

Variable mapping and physical units must be explicitly supplied; no guessed headers.
"""

from pathlib import Path
import argparse
import csv
import json
import sys
from datetime import datetime, timezone

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.physics.atmospheric_observations import meteorological_from_to_enu, sha256_file
from experiments.knmi_tower_schema import resolve_wind_levels


def convert_file(path, mapping_path, output_csv, output_metadata, provider, dataset_id,
                 dataset_version, source_url, station, license_name, data_kind, max_times=None):
    if data_kind not in ("observed", "synthetic", "reanalysis"):
        raise ValueError("data_kind must be explicitly declared")
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("optional NetCDF conversion needs xarray and a suitable backend") from exc
    mapping=json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    if not mapping.get("time") or not (mapping.get("levels") or mapping.get("profile")):
        raise ValueError("mapping needs time variable and level -> speed/direction names")
    ds=xr.open_dataset(path)
    try:
        tname=mapping["time"]
        if tname not in ds:
            raise ValueError(f"time variable {tname} not present")
        times=np.asarray(ds[tname].values)
        if times.ndim != 1 or not np.issubdtype(times.dtype, np.datetime64):
            raise ValueError("time must be 1D UTC-decodable datetime64; no inferred timezones")
        n=len(times) if max_times is None else min(len(times),max_times)
        levels = resolve_wind_levels(ds, mapping, tname)
        # Freeze to arrays once; avoid reading and re-slicing the NetCDF per row.
        series = [(height, np.asarray(s.values[:n], dtype=float), np.asarray(d.values[:n], dtype=float))
                  for height, _sn, _dn, s, d in levels]
        rows=[]
        rejected=0
        for idx in range(n):
            tstamp=np.datetime_as_string(times[idx], unit="s") + "Z"
            dt=datetime.fromisoformat(tstamp.replace("Z","+00:00"))
            if dt.tzinfo!=timezone.utc:
                raise ValueError("invalid UTC timestamp")
            for height, speeds, directions in series:
                speed=float(speeds[idx]); angle=float(directions[idx])
                if (not np.isfinite(speed) or not np.isfinite(angle) or
                        speed < 0 or angle < 0 or angle > 360):
                    rejected+=1
                    continue
                east,north=meteorological_from_to_enu(speed,angle)
                rows.append({"timestamp_utc":tstamp,"station_id":station,
                             "height_agl_m":height,"wind_east_m_s":east,"wind_north_m_s":north})
    finally:
        ds.close()
    if not rows:
        raise ValueError("NetCDF had no valid time/height samples")
    output_csv=Path(output_csv);output_csv.parent.mkdir(parents=True,exist_ok=True)
    with output_csv.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    meta={"data_kind":data_kind, "provider":provider,"dataset_id":dataset_id,
          "dataset_version":dataset_version,"source_url":source_url,
          "station_id":station,"height_datum":"AGL_m","time_basis":"UTC_ISO8601",
          "wind_units":"ENU_m_s","data_license":license_name,
          "raw_netcdf_sha256":sha256_file(path),
          "conversion_mapping_sha256":sha256_file(mapping_path),
          "rejected_missing_or_invalid_level_rows":rejected,
          "data_quality_note":"converter trusts provider-declared variable units and measured wind FROM directions; check NetCDF metadata and flag semantics before publication"}
    Path(output_metadata).write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return len(rows)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netcdf",type=Path,required=True)
    p.add_argument("--mapping",type=Path,required=True)
    p.add_argument("--csv",type=Path,required=True)
    p.add_argument("--metadata",type=Path,required=True)
    p.add_argument("--provider",required=True)
    p.add_argument("--dataset",required=True)
    p.add_argument("--version",required=True)
    p.add_argument("--source-url",required=True)
    p.add_argument("--station",required=True)
    p.add_argument("--license",required=True)
    p.add_argument("--data-kind",required=True,choices=["observed","synthetic","reanalysis"])
    p.add_argument("--max-times",type=int)
    args=p.parse_args()
    print(json.dumps({"rows":convert_file(args.netcdf,args.mapping,args.csv,args.metadata,
                                          args.provider,args.dataset,args.version,args.source_url,
                                          args.station,args.license,args.data_kind,args.max_times)},indent=2))

if __name__=="__main__":main()
