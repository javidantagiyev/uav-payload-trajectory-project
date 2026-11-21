"""Descriptive monthly surface climatology; no predictive model or simulation."""
import argparse
import calendar
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STATIONS = {'01975': 'Hamburg-Fuhlsbuettel', '03015': 'Lindenberg'}
BASE = 'https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/historical/'
YEAR = 2025

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def expected(month):
    return calendar.monthrange(YEAR, month)[1] * 144

def read_dwd(path, station):
    with ZipFile(path) as z:
        names = [n for n in z.namelist() if Path(n).name.lower().startswith('produkt_') and n.lower().endswith('.txt')]
        if len(names) != 1:
            raise ValueError(f'Expected one product member, found {names}')
        with z.open(names[0]) as f:
            d = pd.read_csv(f, sep=';', dtype=str, encoding='latin1')
        members = z.namelist()
    d.columns = d.columns.str.strip()
    required = {'STATIONS_ID','MESS_DATUM','QN','TT_10','TD_10'}
    if not required.issubset(d.columns):
        raise ValueError(f'Missing fields: {required-set(d.columns)}')
    if not pd.to_numeric(d.STATIONS_ID, errors='raise').eq(int(station)).all():
        raise ValueError('Station ID mismatch')
    t = pd.to_datetime(d.MESS_DATUM.str.strip(), format='%Y%m%d%H%M', utc=True, errors='raise')
    d = d.loc[t.dt.year.eq(YEAR)].copy()
    d['time'] = t.loc[d.index]
    if d.time.duplicated().any() or (d.time.dt.minute % 10 != 0).any():
        raise ValueError('Duplicate or off-grid 2025 timestamps')
    if d.empty:
        raise ValueError('No 2025 observations')
    records = []
    for m in range(1,13):
        sub = d[d.time.dt.month.eq(m)]
        for source, var in [('TT_10','TA'),('TD_10','TD')]:
            x = pd.to_numeric(sub[source], errors='raise').replace(-999, np.nan).dropna()
            if not np.isfinite(x).all() or not x.between(-100,70).all():
                raise ValueError(f'Unexpected {source} range at month {m}')
            q = x.quantile([.25,.5,.75]).tolist() if len(x) else [np.nan]*3
            records.append(dict(site=STATIONS[station],month=m,variable=var,unit='degC',nominal_height_m=2,expected=expected(m),observed=len(sub),n=len(x),coverage=len(x)/expected(m),q25=q[0],median=q[1],q75=q[2]))
    meta = dict(station_id=station,file=Path(path).name,sha256=sha(path),url=BASE+Path(path).name,product_member=names[0],archive_members=members,quality_code_counts=d.QN.str.strip().fillna('missing').value_counts().to_dict())
    return pd.DataFrame(records),meta

def read_cabauw(path):
    d = pd.read_csv(path)
    d = d[(d.height_m==2)&d.variable.isin(['TA','TD'])].copy()
    if len(d)!=24 or d.duplicated(['period','variable']).any():
        raise ValueError('Expected 24 nominal 2 m monthly TA/TD rows')
    t=pd.to_datetime(d.period,format='%Y-%m',errors='raise')
    if not t.dt.year.eq(YEAR).all():
        raise ValueError('Expected calendar year 2025')
    d['month']=t.dt.month
    d['expected']=d.month.map(expected)
    if not d.expected.eq(d.expected_intervals).all() or not ((d.n>=0)&(d.n<=d.observed_intervals)&(d.observed_intervals<=d.expected)).all():
        raise ValueError('Invalid count denominators')
    for k in ['q25','median','q75']:
        d[k] = d[k]-273.15
    d['site']='Cabauw'; d['unit']='degC'; d['nominal_height_m']=2
    d['observed']=d.observed_intervals; d['coverage']=d.n/d.expected
    return d[['site','month','variable','unit','nominal_height_m','expected','observed','n','coverage','q25','median','q75']]

def run(stage10,dwd_dir,out):
    stage10,dwd_dir,out=map(Path,(stage10,dwd_dir,out))
    if out.exists(): raise FileExistsError(out)
    p=stage10/'monthly_statistics.csv'; c=read_cabauw(p)
    frames=[c]; sources=[dict(file=str(p),sha256=sha(p),kind='Stage 10 derived monthly statistics')]
    for station in STATIONS:
        f=dwd_dir/f'10minutenwerte_TU_{station}_20200101_20251231_hist.zip'
        data,meta=read_dwd(f,station); frames.append(data);sources.append(meta)
    d=pd.concat(frames,ignore_index=True);d['coverage_screen']=d.coverage>=.90
    # Existing descriptive findings, no new profile inference.
    s=stage10/'monthly_temperature_differences.csv'; strat=pd.read_csv(s)
    strat=strat[strat.threshold_K.eq(.5)].copy()
    strat['coverage_screen']=strat.coverage>=.90
    if len(strat)!=84: raise ValueError('Expected 12 months x seven existing layer summaries')
    out.mkdir(parents=True);figs=out/'figures';figs.mkdir()
    d.to_csv(out/'monthly_surface_comparison.csv',index=False)
    strat.to_csv(out/'existing_stratification_coverage.csv',index=False)
    for v in ['TA','TD']:
        fig,ax=plt.subplots(figsize=(10,4.5))
        for site,g in d[d.variable.eq(v)].groupby('site'):
            g=g.sort_values('month'); x=g.month.to_numpy(); y=g['median'].to_numpy(float)
            ax.plot(x,y,marker='o',label=site);ax.fill_between(x,g.q25.to_numpy(float),g.q75.to_numpy(float),alpha=.12)
            bad=~g.coverage_screen.to_numpy();ax.scatter(x[bad],y[bad],marker='x',color='black',zorder=5)
        ax.set(xlabel='Calendar month (2025)',ylabel='°C',title=f'{v}: monthly median and interquartile range');ax.set_xticks(range(1,13));ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figs/f'{v}_monthly.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5))
    for (site,var),g in d.groupby(['site','variable']):
        ax.plot(g.month,g.coverage*100,marker='.',label=f'{site} {var}')
    ax.axhline(90,ls='--',color='black');ax.set(xlabel='Month',ylabel='Valid records (%)',ylim=(0,105));ax.set_xticks(range(1,13));ax.legend(fontsize=8,ncol=2);fig.tight_layout();fig.savefig(figs/'coverage.png',dpi=160);plt.close(fig)
    summary=dict(status='descriptive_surface_comparison',year=YEAR,sites=list(d.site.unique()),rows=len(d),below_90_percent=int((~d.coverage_screen).sum()),sources=sources,existing_stratification_source=dict(file=str(s),sha256=sha(s)),limitations=['DWD instantaneous 2 m values and Cabauw nominal 2 m intervals differ in measurement and aggregation.','DWD dew point derived from temperature and relative humidity; not equivalent independent moisture measurement.','QN counts retained, not a per-variable error estimate.','Monthly distributions are descriptive; station siting and missingness may confound differences.','No independent vertical profile validation; Stage 16 only consolidates existing Cabauw results.'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage10',type=Path,required=True);p.add_argument('--dwd-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.stage10,a.dwd_dir,a.out),indent=2))
