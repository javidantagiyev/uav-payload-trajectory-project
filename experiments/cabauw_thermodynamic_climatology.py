"""Descriptive climatology of observed temperature, moisture and visibility.
No wind estimation, stability inference, forecasts or simulation coupling.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

UNITS = {'TA':'K','TD':'K','Q':'g kg-1','ZMA':'m'}
THRESHOLDS = (0.0, 0.1, 0.5)
INTERVAL = pd.Timedelta(minutes=10)


def sha256(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def read_observations(ds):
    if ds.z.dims != ('z',) or ds.z.attrs.get('units') != 'm':
        raise ValueError('Expected height coordinate z in metres')
    z = np.asarray(ds.z.values, dtype=float)
    if not np.isfinite(z).all() or (z < 0).any() or len(set(z)) != len(z) or len(z)<2:
        raise ValueError('Invalid height coordinate')
    order = np.argsort(z); z = z[order]
    if not np.issubdtype(ds.time.dtype,np.datetime64) or ds.time.dims != ('time',):
        raise ValueError('Expected one-dimensional decoded time coordinate')
    native = pd.DatetimeIndex(pd.to_datetime(ds.time.values,utc=True))
    if not len(native) or native.hasnans or not native.is_unique or not native.is_monotonic_increasing:
        raise ValueError('Time must be finite, increasing and unique')
    grid = native.round('10min')
    offsets = (native-grid).total_seconds().to_numpy()
    if np.max(np.abs(offsets)) > .5 or not grid.is_unique:
        raise ValueError('Time grid not supported: offsets > 0.5 s or collisions')
    a = {}; rejected = {}
    for name,unit in UNITS.items():
        var = ds[name]
        if set(var.dims) != {'time','z'} or var.ndim != 2 or str(var.attrs.get('units','')).strip() != unit:
            raise ValueError(f'{name}: unexpected dimensions or units')
        v = np.asarray(var.transpose('time','z').values,dtype=float)[:,order]
        valid = np.isfinite(v) & ((v>0) if name in ('TA','TD') else (v>=0))
        if name=='Q': valid &= v<=1000
        rejected[name] = {'nonfinite':int((~np.isfinite(v)).sum()), 'finite_outside_basic_range':int((np.isfinite(v)&~valid).sum())}
        a[name] = np.where(valid,v,np.nan)
    return native,grid,z,a,rejected,float(np.max(np.abs(offsets)))


def inversion_events(grid, delta, threshold):
    """Runs of observed mean-temperature differences above a stated threshold.
    Missing values and absent intervals interrupt events; no bridging.
    Durations are nominal occupied interval counts, not continuous proof.
    """
    delta=np.asarray(delta,dtype=float)
    if len(grid)!=len(delta): raise ValueError('time/value length mismatch')
    positive=np.isfinite(delta)&(delta>threshold)
    rows=[]; i=0
    while i<len(grid):
        if not positive[i]: i+=1; continue
        start=i; i+=1
        while i<len(grid) and positive[i] and grid[i]-grid[i-1]==INTERVAL: i+=1
        end=i-1
        left = start==0 or grid[start]-grid[start-1]!=INTERVAL or not np.isfinite(delta[start-1])
        right = i==len(grid) or grid[i]-grid[end]!=INTERVAL or not np.isfinite(delta[i])
        rows.append({'first_grid_utc':grid[start].isoformat(),'last_grid_utc':grid[end].isoformat(),'intervals':i-start,'nominal_minutes':10*(i-start),'left_censored':bool(left),'right_censored':bool(right),'max_delta_K':float(delta[start:i].max())})
    return rows


def describe(v):
    v=np.asarray(v); v=v[np.isfinite(v)]
    if not len(v): return {'n':0,'median':None,'q25':None,'q75':None}
    q=np.quantile(v,[.25,.5,.75]); return {'n':len(v),'median':float(q[1]),'q25':float(q[0]),'q75':float(q[2])}


def summarize(grid,z,a):
    pairs=[(i,i+1) for i in range(len(z)-1)]
    if len(z)>2: pairs.append((0,len(z)-1))
    inv=[]; events=[]; daily=[]; diurnal=[]; vis=[]; deltas={}
    for lo,hi in pairs:
        delta=a['TA'][:,hi]-a['TA'][:,lo]; key=(float(z[lo]),float(z[hi])); deltas[key]=delta
        for threshold in THRESHOLDS:
            valid=np.isfinite(delta); n=int(valid.sum()); pos=int((valid&(delta>threshold)).sum())
            segments=inversion_events(grid,delta,threshold)
            inv.append({'lower_m':key[0],'upper_m':key[1],'threshold_K':threshold,'valid_pairs':n,'missing_pairs':len(delta)-n,'above_threshold_count':pos,'fraction_of_valid':pos/n if n else None,'observed_runs':len(segments),'longest_nominal_minutes':max((s['nominal_minutes'] for s in segments),default=0),'censored_runs':sum(s['left_censored'] or s['right_censored'] for s in segments)})
            events.extend(dict(lower_m=key[0],upper_m=key[1],threshold_K=threshold,**s) for s in segments)
        for day in grid.normalize().unique():
            d=delta[grid.normalize()==day]; n=int(np.isfinite(d).sum()); p=int((d>0).sum())
            daily.append({'date_utc':str(day.date()),'lower_m':key[0],'upper_m':key[1],'positive_count':p,'valid_count':n,'fraction_positive':p/n if n else None,**describe(d)})
    series={**a,'dewpoint_depression_K':a['TA']-a['TD']}
    for name,vals in series.items():
        for j,h in enumerate(z):
            for hour in range(24):
                diurnal.append({'variable':name,'height_m':float(h),'hour_utc':hour,**describe(vals[grid.hour==hour,j])})
    for j,h in enumerate(z):
        v=a['ZMA'][:,j]; v=v[np.isfinite(v)]; n=len(v)
        vis.append({'height_m':float(h),'n':n,'maximum_m':float(v.max()) if n else None,'exact_20000_m':int((v==20000).sum()),'above_20000_m':int((v>20000).sum()),'fraction_equal_20000_m':float((v==20000).mean()) if n else None})
    return inv,events,daily,diurnal,vis,deltas


def plots(out,grid,z,a,deltas,diurnal):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    figs=[]
    full_grid=pd.date_range(grid[0],grid[-1],freq='10min')
    def save(fig,name):
        fig.tight_layout(); fig.savefig(out/name,dpi=150); plt.close(fig); figs.append(name)
    for var,unit in [('TA','K'),('Q','g/kg'),('TD','K'),('ZMA','m')]:
        fig,ax=plt.subplots(figsize=(13,5))
        mat=np.ma.masked_invalid(pd.DataFrame(a[var],index=grid).reindex(full_grid).to_numpy().T)
        # Use numeric UTC date coordinates and actual height spacing.
        pm=ax.pcolormesh(mdates.date2num(full_grid.to_pydatetime()),z,mat,shading='nearest')
        ax.xaxis_date(); ax.set(title=f'Observed {var}: full observation period',ylabel='Height above surface (m)',xlabel='UTC'); fig.colorbar(pm,ax=ax,label=unit); save(fig,f'{var}_time_height.png')
    key=(float(z[0]),float(z[-1])); d=pd.Series(deltas[key],index=grid).reindex(full_grid).to_numpy()
    for suffix,mask in [('full',np.ones(len(full_grid),dtype=bool)),('first_72h',full_grid<full_grid[0]+pd.Timedelta(days=3))]:
        fig,ax=plt.subplots(figsize=(13,3.8)); ax.plot(full_grid[mask],d[mask],lw=.9); ax.axhline(0,ls='--',color='0.4'); ax.set(title=f'Observed temperature difference: {key[1]:g} m minus {key[0]:g} m',ylabel='Difference (K)',xlabel='UTC'); ax.grid(alpha=.2); save(fig,f'temperature_difference_{suffix}.png')
    df=pd.DataFrame(diurnal)
    for var,unit in [('TA','K'),('Q','g/kg'),('dewpoint_depression_K','K')]:
        fig,ax=plt.subplots(figsize=(10,4.8))
        for h,sub in df[df.variable==var].groupby('height_m'):
            ax.plot(sub.hour_utc,sub['median'],label=f'{h:g} m');
        ax.set(title=f'{var}: hourly median by UTC hour across observation period',xlabel='UTC hour',ylabel=unit,xticks=range(0,24,3));ax.grid(alpha=.2);ax.legend(ncol=3,fontsize=8);save(fig,f'{var}_diurnal.png')
    return figs


def run(path,out,expected_hash=None):
    path=Path(path);out=Path(out); digest=sha256(path)
    if expected_hash and expected_hash.lower()!=digest: raise ValueError('Source SHA256 mismatch')
    if out.exists() and any(out.iterdir()): raise FileExistsError('Output directory must be empty')
    with xr.open_dataset(path,decode_times=True,mask_and_scale=True) as ds:
        native,grid,z,a,rejected,max_offset=read_observations(ds)
    out.mkdir(parents=True,exist_ok=True)
    inv,events,daily,diurnal,vis,deltas=summarize(grid,z,a)
    for name,data in [('inversion_summary',inv),('inversion_events',events),('daily_temperature_difference',daily),('diurnal_summary',diurnal),('visibility_ceiling_diagnostic',vis)]:
        columns = ['lower_m','upper_m','threshold_K','first_grid_utc','last_grid_utc','intervals','nominal_minutes','left_censored','right_censored','max_delta_K'] if name=='inversion_events' else None
        pd.DataFrame(data,columns=columns).to_csv(out/f'{name}.csv',index=False)
    pd.DataFrame({'native_utc':native.astype(str),'analysis_grid_utc':grid.astype(str)}).to_csv(out/'time_mapping.csv',index=False)
    figures=plots(out,grid,z,a,deltas,diurnal)
    valid=np.isfinite(a['TA'])&np.isfinite(a['TD'])
    report={'status':'descriptive_thermodynamic_climatology_only','source_sha256':digest,'expected_hash_matched':bool(expected_hash),'timestamps':len(grid),'utc_days':len(grid.normalize().unique()),'height_levels_m':z.tolist(),'maximum_grid_offset_s':max_offset,'missing_grid_slots':len(pd.date_range(grid[0],grid[-1],freq='10min').difference(grid)),'basic_range_audit':rejected,'dewpoint_temperature_joint_valid':int(valid.sum()),'dewpoint_above_air_temperature_count':int((valid&(a['TD']>a['TA'])).sum()),'temperature_difference_thresholds_K':list(THRESHOLDS),'figures':figures,'limitations':['Positive layer temperature difference describes observed temperature structure, not a complete stability diagnosis.','Thresholds are descriptive sensitivity checks, not instrument uncertainty estimates.','Run duration counts contiguous qualifying ten-minute records, not resolved continuous inversion duration.','Repeated visibility values at 20000 m are a diagnostic, not proof of censoring.','No imputation, no physical-model fitting, no wind estimation or simulation integration.','One site and observation period; no generalization claim.']}
    (out/'climatology_summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--netcdf',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--sha256');args=p.parse_args();print(json.dumps(run(args.netcdf,args.out,args.sha256),indent=2))
