"""Descriptive near-surface climatology and archive inventory (no wind or operational prediction)."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
import numpy as np
import pandas as pd
from cabauw_seasonal_climatology import PREFIX, load_month

PATTERN = re.compile(re.escape(PREFIX)+r'(\d{4})(\d{2})\.nc$')
VARIABLES = ('TA','TD','Q','ZMA')

def parse_names(names):
    periods=set()
    for name in names:
        m=PATTERN.fullmatch(Path(name).name)
        if m:
            try: periods.add(pd.Period(f'{m[1]}-{m[2]}',freq='M'))
            except ValueError: raise ValueError(f'Invalid month: {name}')
    return periods

def era(p):
    if p < pd.Period('2010-04'): return 'pre_2010_change'
    if p.year < 2014: return '2010_2013_transition'
    return '2014_onward_documented_configuration'

def inventory(local, advertised):
    all_months=local|advertised
    if not all_months: raise ValueError('Empty inventory')
    return pd.DataFrame([dict(month=str(p),year=p.year,calendar_month=p.month,local=p in local,advertised=p in advertised,era=era(p),expected_intervals=p.days_in_month*144) for p in pd.period_range(min(all_months),max(all_months),freq='M')])

def monthly(path,p):
    grid,z,a,meta=load_month(path,p)
    idx=np.flatnonzero(z==10.)
    if len(idx)!=1: raise ValueError(f'{path.name}: nominal 10 m measurement missing')
    rows=[]
    for v in VARIABLES:
        x=a[v][:,idx[0]]; x=x[np.isfinite(x)]
        if v in ('TA','TD'): x=x-273.15
        n=len(x); q=np.quantile(x,[.25,.5,.75]) if n else (np.nan,)*3
        rows.append(dict(month=str(p),year=p.year,calendar_month=p.month,era=era(p),variable=v,unit={'TA':'degC','TD':'degC','Q':'g/kg','ZMA':'m'}[v],n=n,expected_intervals=meta['expected_intervals'],coverage=n/meta['expected_intervals'],q25=q[0],median=q[1],q75=q[2],ceiling_fraction=float(np.mean(x==20000)) if n and v=='ZMA' else np.nan))
    return rows,meta

def matched(df,base=2025,other=2026):
    keys=['calendar_month','variable','unit']
    cols=keys+['month','median','n','coverage','ceiling_fraction']
    a=df.loc[df.year==base,cols]; b=df.loc[df.year==other,cols]
    r=a.merge(b,on=keys,suffixes=('_base','_other'),validate='one_to_one')
    r['median_difference']=r.median_other-r.median_base
    r['both_coverage_ge_90pct']=(r.coverage_base>=.9)&(r.coverage_other>=.9)
    # Visibility is right-censored: a numeric median difference is not an uncensored visibility estimate.
    r.loc[r.variable=='ZMA','median_difference']=np.nan
    return r.sort_values(keys)

def figures(out,inv,df,comp):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True,exist_ok=True)
    names=[]
    def save(fig,name):
        fig.tight_layout();fig.savefig(out/name,dpi=150);plt.close(fig);names.append('figures/'+name)
    years=sorted(inv.year.unique()); grid=np.zeros((len(years),12))
    for r in inv.itertuples(): grid[years.index(r.year),r.calendar_month-1]=2 if r.local else int(r.advertised)
    from matplotlib.colors import ListedColormap, BoundaryNorm
    fig,ax=plt.subplots(figsize=(10,max(3,len(years)*.3))); im=ax.imshow(grid,aspect='auto',cmap=ListedColormap(['#eeeeee','#e7ab52','#3274a1']),norm=BoundaryNorm([-.5,.5,1.5,2.5],3));ax.set(xticks=list(range(12)),xticklabels=list(range(1,13)),yticks=list(range(len(years))),yticklabels=years,xlabel='Calendar month',title='Archive coverage: local files and supplied inventory');c=fig.colorbar(im,ax=ax,ticks=[0,1,2]);c.ax.set_yticklabels(['Not listed','Advertised only','Local']);save(fig,'01_archive_coverage.png')
    for v,unit in [('TA','°C'),('Q','g/kg')]:
        fig,ax=plt.subplots(figsize=(9,4))
        for y in sorted(df.year.unique()):
            d=df[(df.variable==v)&(df.year==y)].set_index('calendar_month').reindex(range(1,13));ax.plot(range(1,13),d['median'],marker='o',label=str(y))
        ax.set(xticks=range(1,13),xlabel='Calendar month',ylabel=unit,title=f'Observed 10 m monthly {v} medians (gaps retained)');ax.legend(ncol=3);ax.grid(alpha=.2);save(fig,f'02_{v}_monthly.png')
    fig,ax=plt.subplots(figsize=(9,4));d=comp[comp.variable=='TA'].set_index('calendar_month').reindex(range(1,13));ax.bar(range(1,13),d.median_difference);ax.axhline(0,color='black',lw=.7);ax.set(xticks=range(1,13),xlabel='Matched calendar month',ylabel='°C',title='Descriptive monthly temperature median differences');save(fig,'03_matched_temperature_difference.png')
    fig,ax=plt.subplots(figsize=(10,4));p=df[df.variable=='TA'].copy();ax.bar(p.month,p.coverage*100);ax.tick_params(axis='x',rotation=90,labelsize=7);ax.set(ylabel='Valid observations (%)',ylim=(0,100),title='Monthly 10 m temperature coverage');save(fig,'04_temperature_coverage.png')
    return names

def run(raw,out,inventory_json,make_figures=True):
    raw=Path(raw);out=Path(out);inventory_json=Path(inventory_json)
    if not raw.is_dir(): raise ValueError('Raw directory missing')
    if out.exists() and any(out.iterdir()): raise FileExistsError('Output must be empty')
    names=json.loads(inventory_json.read_text());
    if not isinstance(names,list) or not all(isinstance(n,str) for n in names): raise ValueError('Expected list of provider filenames')
    local=parse_names(p.name for p in raw.iterdir() if p.is_file()); advertised=parse_names(names)
    inv=inventory(local,advertised); rows=[];metadata=[]
    for p in sorted(local):
        r,m=monthly(raw/(PREFIX+p.strftime('%Y%m')+'.nc'),p);rows.extend(r);metadata.append(m)
    if not rows: raise ValueError('No local monthly observations')
    df=pd.DataFrame(rows);comp=matched(df)
    out.mkdir(parents=True,exist_ok=True)
    inv.to_csv(out/'historical_inventory.csv',index=False);df.to_csv(out/'monthly_surface_statistics.csv',index=False);comp.to_csv(out/'matched_2025_2026.csv',index=False)
    f=figures(out/'figures',inv,df,comp) if make_figures else []
    summary=dict(status='descriptive_near_surface_climatology',local_months=len(local),advertised_months=len(advertised),advertised_not_local=sorted(map(str,advertised-local)),local_not_advertised=sorted(map(str,local-advertised)),matched_months=sorted(set(map(int,comp.calendar_month))),source_inventory=metadata,inventory_sha256=hashlib.sha256(inventory_json.read_bytes()).hexdigest(),figures=f,limitations=['Nominal 10 m observations only. No wind, predictive modelling or simulation.','Median differences are descriptive, not trend estimates or paired individual observations.','90% coverage flag is a screening convention, not a guarantee of representativeness.','Archive inventory is a user-supplied snapshot; unlisted months may exist elsewhere or be released later.','Instrument eras are documented historical categories, not verified per-file calibration history.','Visibility is censored at 20 km; specific humidity is derived, not independent.'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');return summary

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--input-dir',required=True,type=Path);a.add_argument('--inventory',required=True,type=Path);a.add_argument('--out',required=True,type=Path);v=a.parse_args();print(json.dumps(run(v.input_dir,v.out,v.inventory),indent=2))
