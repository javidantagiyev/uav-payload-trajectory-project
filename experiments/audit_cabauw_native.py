"""Standalone observational data-quality and climatological audit of Cabauw NetCDF.

Does not modify the source, fit a wind model, impute observations, or simulate motion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

VARIABLES = {
    'F': ('m s-1', 'mean wind speed'),
    'D': ('degree', 'mean wind FROM direction'),
    'PF': ('m s-1', 'maximum wind speed'),
    'MF': ('m s-1', 'minimum wind speed, not corrected'),
    'SF': ('m s-1', 'standard deviation of wind speed'),
    'SD': ('degree', 'standard deviation of wind direction'),
    'TA': ('K', 'air temperature'),
    'TD': ('K', 'dew point temperature'),
    'Q': ('g kg-1', 'specific humidity'),
    'ZMA': ('m', 'visibility'),
}


def sha256_file(path):
    with Path(path).open('rb') as f:
        h = hashlib.sha256()
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
        return h.hexdigest()


def timestamp_audit(values):
    values = np.asarray(values)
    if values.ndim != 1 or not np.issubdtype(values.dtype, np.datetime64):
        raise ValueError('expected decoded one-dimensional datetime64 time coordinate')
    t = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    if not len(t) or t.hasnans or not t.is_monotonic_increasing or not t.is_unique:
        raise ValueError('time coordinate must be nonempty, increasing, unique and finite')
    rounded = t.round('10min')
    offset = (t - rounded).total_seconds().to_numpy()
    grid = pd.date_range(rounded[0], rounded[-1], freq='10min')
    report = {'sample_count': len(t), 'first_decoded_utc': str(t[0]),
              'last_decoded_utc': str(t[-1]),
              'nonzero_grid_offset_count': int(np.count_nonzero(offset)),
              'max_absolute_grid_offset_s': float(np.max(np.abs(offset))),
              'nearest_grid_collision_count': int(len(t) - len(rounded.unique())),
              'missing_nearest_grid_slots_within_span': int(len(grid.difference(rounded))),
              'offset_quantiles_s': np.quantile(offset, [0,.25,.5,.75,1]).tolist(),
              'timestamps_modified': False}
    return t, offset, report


def audit_bounds(ds, t):
    name = ds['time'].attrs.get('bounds', ds['time'].encoding.get('bounds', 'time_bnds'))
    if name not in ds:
        return {'status': 'missing_time_bounds'}
    b = ds[name]
    others = [d for d in b.dims if d != 'time']
    if len(others) != 1 or 'time' not in b.dims or b.sizes[others[0]] != 2:
        return {'status': 'unsupported_time_bounds_shape', 'dims': list(b.dims)}
    a = b.transpose('time', others[0]).values
    if not np.issubdtype(a.dtype, np.datetime64):
        return {'status': 'bounds_not_decoded_as_datetime', 'dtype': str(a.dtype)}
    if np.isnat(a).any():
        return {'status': 'missing_bound_values'}
    lo, hi = a[:,0].astype('datetime64[ns]'), a[:,1].astype('datetime64[ns]')
    widths = (hi-lo)/np.timedelta64(1,'s')
    tv = t.tz_localize(None).to_numpy(dtype='datetime64[ns]')
    return {'status': 'bounds_inspected', 'minimum_width_s': float(widths.min()),
            'maximum_width_s': float(widths.max()),
            'nonpositive_width_count': int((widths<=0).sum()),
            'outside_bound_count': int(((tv<lo)|(tv>hi)).sum()),
            'adjacent_overlap_count': int((lo[1:]<hi[:-1]).sum()),
            'adjacent_gap_count': int((lo[1:]>hi[:-1]).sum())}


def normalized_units(s):
    return str(s).strip().lower().replace(' ', '')


def inspect_native(ds):
    if 'time' not in ds or 'z' not in ds:
        raise ValueError('time and z coordinates required')
    z = np.asarray(ds['z'].values, dtype=float)
    if ds['z'].dims != ('z',) or normalized_units(ds['z'].attrs.get('units','')) != 'm' or not np.isfinite(z).all() or len(set(z)) != len(z):
        raise ValueError('expected unique finite height coordinate in metres')
    t, offsets, time = timestamp_audit(ds['time'].values)
    bounds = audit_bounds(ds,t)
    inventory, thermo = [], {}
    for name, (unit, description) in VARIABLES.items():
        if name not in ds:
            inventory.append({'variable':name, 'height_m':None, 'status':'absent'}); continue
        var = ds[name]
        if set(var.dims) != {'time','z'} or normalized_units(var.attrs.get('units','')) != normalized_units(unit):
            inventory.append({'variable':name,'height_m':None,'status':'unsupported_schema_or_units', 'source_units':str(var.attrs.get('units',''))}); continue
        a = np.asarray(var.transpose('time','z').values,dtype=float)
        for idx, height in enumerate(z):
            v = a[:,idx]; finite=np.isfinite(v)
            # Only basic structural/range checks; not provider instrument QC.
            if name in {'F','PF','MF','SF','SD','ZMA','Q'}: invalid=finite & (v<0)
            elif name=='D': invalid=finite & ((v<0)|(v>360))
            elif name in {'TA','TD'}: invalid=finite & (v<=0)
            else: invalid=np.zeros(v.shape,dtype=bool)
            inventory.append({'variable':name,'description':description,'height_m':float(height),'status':'inspected',
                              'source_units':unit,'total':len(v),'missing_or_nonfinite':int((~finite).sum()),'basic_range_violation':int(invalid.sum()),'finite_in_basic_range':int((finite & ~invalid).sum())})
        if name in {'TA','TD','Q','ZMA'}:
            # Preserve all finite, basic-range-valid data, with no imputation.
            valid = np.isfinite(a) & ((a>0) if name in {'TA','TD'} else (a>=0))
            thermo[name] = np.where(valid,a,np.nan)
    return t,z,offsets,{'time':time,'time_bounds':bounds,'height_levels_m':z.tolist(),'inventory':inventory},thermo


def run(path, out, expected_sha256=None):
    path,out=Path(path),Path(out)
    digest=sha256_file(path)
    if expected_sha256 and digest.lower()!=expected_sha256.lower():
        raise ValueError('raw NetCDF SHA256 mismatch')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('choose an empty output directory to preserve earlier results')
    out.mkdir(parents=True,exist_ok=True)
    with xr.open_dataset(path, decode_times=False) as raw:
        raw_time = {'dtype':str(raw['time'].dtype),'attributes':{k:str(v) for k,v in raw['time'].attrs.items()},
                    'raw_first':str(raw['time'].values[0]),'raw_last':str(raw['time'].values[-1])}
    with xr.open_dataset(path, decode_times=True, mask_and_scale=True) as ds:
        t,z,offsets,report,thermo=inspect_native(ds)
    report.update({'status':'descriptive_observational_audit_not_instrument_validation','sha256':digest,'expected_hash_matched':bool(expected_sha256),
                  'raw_time_encoding':raw_time,'limitations':['range checks and missingness do not certify provider QC','native timestamps preserved; nearest-grid offsets are diagnostics only','wind auxiliary variables are interval statistics, not high-frequency samples or QC flags','temperature differences are not a complete atmospheric stability diagnosis; no flux or pressure-derived stability classification','single site and month; no forecast or simulation validation']})
    pd.DataFrame(report.pop('inventory')).to_csv(out/'variable_completeness.csv',index=False)
    pd.DataFrame({'decoded_utc':t.astype(str),'nearest_10min_offset_s':offsets}).to_csv(out/'timestamp_audit.csv',index=False)
    # Site-wide daily summaries of thermodynamic observations only, no predictions.
    rows=[]
    for name,a in thermo.items():
        for j,height in enumerate(z):
            series=pd.Series(a[:,j],index=t)
            for day,group in series.groupby(series.index.floor('D')):
                rows.append({'date_utc':str(day.date()),'variable':name,'height_m':height,'valid_count':int(group.count()),'median':float(group.median()) if group.count() else None,'q25':float(group.quantile(.25)) if group.count() else None,'q75':float(group.quantile(.75)) if group.count() else None})
    daily=pd.DataFrame(rows, columns=['date_utc','variable','height_m','valid_count','median','q25','q75'])
    daily.to_csv(out/'daily_thermodynamic_summary.csv',index=False)
    figures=[]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for name in ('TA','TD','Q','ZMA'):
        if name not in thermo: continue
        sub=daily[daily.variable==name]
        fig,ax=plt.subplots(figsize=(10,4.8))
        for height,group in sub.groupby('height_m'):
            ax.plot(pd.to_datetime(group.date_utc),group['median'],label=f'{height:g} m',lw=1.1)
        ax.set(title=f'Cabauw: daily median {VARIABLES[name][1]} by measurement height',xlabel='UTC date',ylabel=VARIABLES[name][0]);ax.grid(alpha=.25);ax.legend(ncol=4,fontsize=8);fig.autofmt_xdate();fig.tight_layout()
        fn=f'daily_{name}.png';fig.savefig(out/fn,dpi=150);plt.close(fig);figures.append(fn)
    report['figures']=figures
    (out/'native_audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--netcdf',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--sha256')
    a=p.parse_args();print(json.dumps(run(a.netcdf,a.out,a.sha256),indent=2))
