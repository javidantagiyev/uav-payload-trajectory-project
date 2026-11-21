"""Offline meteorological measurement consistency audit; no imputation or prediction."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
try:
    from .cabauw_thermodynamic_climatology import read_observations, sha256
except ImportError:
    from cabauw_thermodynamic_climatology import read_observations, sha256

THRESHOLDS = (0., .1, .2, .5, 1.)
CAP = 20000.


def summarize(grid, z, a):
    excess = a['TD'] - a['TA']
    rows = []
    for j, h in enumerate(z):
        for day in [None, *grid.normalize().unique()]:
            take = np.ones(len(grid), dtype=bool) if day is None else grid.normalize() == day
            d = excess[take, j]
            d = d[np.isfinite(d)]
            for th in THRESHOLDS:
                count = int((d > th).sum())
                rows.append({'height_m':float(h), 'date_utc':'all' if day is None else str(day.date()), 'threshold_K':th, 'valid_pairs':len(d), 'count':count, 'fraction':count/len(d) if len(d) else np.nan, 'max_excess_K':float(d.max()) if len(d) else np.nan})
    regimes = []
    vis = a['ZMA']
    masks = {'visibility_missing':~np.isfinite(vis), 'below_1000':np.isfinite(vis)&(vis<1000), '1000_to_10000':(vis>=1000)&(vis<10000), '10000_to_ceiling':(vis>=10000)&(vis<CAP), 'at_ceiling':vis==CAP, 'above_documented_ceiling':vis>CAP}
    for j,h in enumerate(z):
        for name, m in masks.items():
            sel = m[:,j] & np.isfinite(excess[:,j]); v=excess[sel,j]
            regimes.append({'height_m':float(h),'visibility_group':name,'valid_pairs':len(v),'positive_count':int((v>0).sum()),'positive_fraction':float((v>0).mean()) if len(v) else np.nan})
    visibility = []
    for j,h in enumerate(z):
        v=vis[:,j]; valid=np.isfinite(v); n=int(valid.sum()); cap=int((v==CAP).sum())
        visibility.append({'height_m':float(h),'valid':n,'missing':len(v)-n,'ceiling_count':cap,'ceiling_fraction':cap/n if n else None,'above_ceiling_count':int((v>CAP).sum()),'below_1000_count':int((valid&(v<1000)).sum()),'below_1000_fraction':int((valid&(v<1000)).sum())/n if n else None})
    flags = []
    for i,j in np.argwhere(np.isfinite(excess)&(excess>0)):
        flags.append({'time_grid_utc':grid[i].isoformat(),'height_m':float(z[j]),'TA_K':float(a['TA'][i,j]),'TD_K':float(a['TD'][i,j]),'excess_K':float(excess[i,j]),'Q_g_kg':float(a['Q'][i,j]),'visibility_m':float(vis[i,j])})
    # This is a coverage check, not independent validation: Q is derived from TD.
    coverage=[]
    for j,h in enumerate(z):
        td=np.isfinite(a['TD'][:,j]); q=np.isfinite(a['Q'][:,j]);
        coverage.append({'height_m':float(h),'both_valid':int((td&q).sum()),'td_only':int((td&~q).sum()),'q_only':int((~td&q).sum()),'both_missing':int((~td&~q).sum())})
    return pd.DataFrame(rows),pd.DataFrame(regimes),pd.DataFrame(visibility),pd.DataFrame(flags,columns=['time_grid_utc','height_m','TA_K','TD_K','excess_K','Q_g_kg','visibility_m']),pd.DataFrame(coverage),excess


def figures(folder, grid, z, excess, thresholds, visibility):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    names=[]
    def save(fig,name):
        fig.tight_layout();fig.savefig(folder/name,dpi=145);plt.close(fig);names.append('figures/'+name)
    fig,ax=plt.subplots(figsize=(10,5)); s=thresholds[thresholds.date_utc=='all']
    for th in THRESHOLDS:
        t=s[s.threshold_K==th];ax.plot(t.height_m,100*t.fraction,marker='o',label=f'excess > {th:g} K')
    ax.set(xlabel='Nominal height (m)',ylabel='Fraction of valid pairs (%)',title='Dew-point excess: threshold sensitivity');ax.grid(alpha=.3);ax.legend();save(fig,'01_dewpoint_thresholds.png')
    fig,ax=plt.subplots(figsize=(12,5)); d=thresholds[(thresholds.date_utc!='all')&(thresholds.threshold_K==0)]
    for h,g in d.groupby('height_m'):
        ax.plot(pd.to_datetime(g.date_utc),100*g.fraction,label=f'{h:g} m')
    ax.set(ylabel='Positive excess (%)',xlabel='UTC date',title='Daily fraction of paired measurements with TD > TA');ax.grid(alpha=.3);ax.legend(ncol=4);fig.autofmt_xdate();save(fig,'02_daily_dewpoint_excess.png')
    for n,label in [(len(grid),'full'),(min(len(grid),432),'first_72h')]:
        fig,ax=plt.subplots(figsize=(13,5)); im=ax.pcolormesh(grid[:n],np.arange(len(z)),np.ma.masked_invalid(excess[:n,:].T),shading='nearest',cmap='coolwarm',vmin=-3,vmax=3);ax.set_yticks(np.arange(len(z)),[f'{h:g}' for h in z]);ax.set(ylabel='Nominal height (m)',xlabel='UTC time',title='Dew-point minus air temperature (color range ±3 K)');fig.colorbar(im,ax=ax,label='K');ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'));fig.autofmt_xdate();save(fig,f'03_excess_{label}.png')
    fig,ax=plt.subplots(figsize=(10,5));ax.bar(visibility.height_m.astype(str),100*visibility.ceiling_fraction);ax.set(xlabel='Nominal height (m)',ylabel='Fraction at ceiling (%)',title='Reported visibility at documented 20 km instrument ceiling',ylim=(0,100));ax.grid(axis='y',alpha=.3);save(fig,'04_visibility_ceiling.png')
    return names


def run(path,out,expected_sha256):
    path,out=Path(path),Path(out)
    digest=sha256(path)
    if digest.lower()!=expected_sha256.lower():raise ValueError('SHA256 mismatch')
    if out.exists():raise FileExistsError(out)
    with xr.open_dataset(path) as ds:
        native,grid,z,a,rejected,offset=read_observations(ds)
    thresholds,regimes,visibility,flags,coverage,excess=summarize(grid,z,a)
    out.mkdir(parents=True);(out/'figures').mkdir()
    for name,df in [('dewpoint_thresholds',thresholds),('dewpoint_by_visibility',regimes),('visibility_ceiling',visibility),('positive_excess_records',flags),('derived_humidity_coverage',coverage)]:
        df.to_csv(out/(name+'.csv'),index=False)
    ns=figures(out/'figures',grid,z,excess,thresholds,visibility)
    valid=int(np.isfinite(excess).sum())
    result={'status':'offline_descriptive_measurement_consistency_audit','source_sha256':digest,'timestamps':len(grid),'valid_temperature_dewpoint_pairs':valid,'positive_excess_count':len(flags),'positive_fraction':len(flags)/valid if valid else None,'visibility_ceiling_m':CAP,'basic_range_audit':rejected,'figures':ns,'limitations':['Documented sensor wetting can cause positive dew-point excess; individual causes are not diagnosed.','Visibility classes describe recorded visibility only; no extrapolation above instrument range.','Specific humidity is derived and not independent confirmation of dew point.','Sensitivity thresholds are descriptive and not calibrated uncertainty bounds.','Nominal heights follow file coordinate; document sensor placement separately.','No observations modified, no model fitting or operational integration.']}
    (out/'measurement_consistency_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--netcdf',required=True,type=Path);p.add_argument('--sha256',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args();print(json.dumps(run(a.netcdf,a.out,a.sha256),indent=2))
