"""Print only NetCDF schema metadata; no variable values or credentials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def peek(path):
    import xarray as xr
    with xr.open_dataset(path) as ds:
        summary = {
            'dimensions': {str(k): int(v) for k, v in ds.sizes.items()},
            'variables': {name: {
                'dimensions': list(var.dims),
                'units': str(var.attrs.get('units', '')),
                'standard_name': str(var.attrs.get('standard_name', '')),
                'long_name': str(var.attrs.get('long_name', ''))[:160],
            } for name, var in ds.variables.items()},
        }
        if 'z' in ds and ds['z'].ndim == 1 and ds['z'].size < 100:
            summary['height_coordinate_z_values'] = ds['z'].values.tolist()
        return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--netcdf', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(peek(a.netcdf), indent=2, default=str))
