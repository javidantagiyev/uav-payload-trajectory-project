"""Offline descriptive seasonal climatology of temperature, moisture and visibility.
Requires the Stage 8 reader. No wind analysis, prediction, fitting or simulation.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cabauw_thermodynamic_climatology import read_observations, sha256, describe

PREFIX='cesar_tower_meteo_lb1_t10_v1.3_'
SEASONS={'DJF':(12,1,2),'MAM':(3,4,5),'JJA':(6,7,8),'SON':(9,10,11)}

def month_range(start,end):
    p=pd.period_range(start,end,freq='M')
    if not len(p): raise ValueError('Empty month range')
    return p

def aggregate(grid,z,a,period,expected):
    rows=[]; layers=[]
    for j,h in enumerate(z):
        for name in ['TA','TD','Q','ZMA','dewpoint_excess_K']:
            vals=(a['TD']-a['TA'])[:,j] if name=='dewpoint_excess_K' else a[name][:,j]
            d=describe(vals); n=d['n']; r={'period':period,'height_m':float(h),'variable':name,'expected_intervals':expected,'observed_intervals':len(grid),**d,'coverage':n/expected if expected else None}
            if name=='ZMA':
                r.update({'ceiling_count':int((vals==20000).sum()),'low_visibility_count':int((vals<1000).sum()),'above_ceiling_count':int((vals>20000).sum())})
            if name=='dewpoint_excess_K': r.update({'positive_count':int((vals>0).sum()),'above_0_5K_count':int((vals>.5).sum())})
            rows.append(r)
    pairs=[(i,i+1) for i in range(len(z)-1)]
    if len(z)>2: pairs.append((0,len(z)-1))
    for lo,hi in pairs:
        delta=a['TA'][:,hi]-a['TA'][:,lo]; n=int(np.isfinite(delta).sum())
        for t in [0.,.1,.5]:
            count=int((delta>t).sum()); layers.append({'period':period,'lower_m':float(z[lo]),'upper_m':float(z[hi]),'threshold_K':t,'valid_pairs':n,'expected_intervals':expected,'count':count,'fraction_valid':count/n if n else None,'coverage':n/expected if expected else None})
    return rows,layers

def load_month(path,month):
    with xr.open_dataset(path,decode_times=True,mask_and_scale=True) as ds:
        native,grid,z,a,rejected,offset=read_observations(ds)
    start=pd.Timestamp(month.start_time,tz='UTC'); end=pd.Timestamp((month+1).start_time,tz='UTC')
    if ((grid<start)|(grid>=end)).any(): raise ValueError(f'{path.name}: normalized time outside filename month')
    expected=len(pd.date_range(start,end,freq='10min',inclusive='left'))
    return grid,z,a,{'month':str(month),'filename':path.name,'sha256':sha256(path),'expected_intervals':expected,'observed_intervals':len(grid),'missing_intervals':expected-len(grid),'max_native_offset_s':offset,'basic_range_audit':rejected,'status':'processed'}

def plots(out,monthly,layers,months,z):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True,exist_ok=True); figs=[]
    df=pd.DataFrame(monthly); lf=pd.DataFrame(layers); labels=list(map(str,months)); xp=np.arange(len(labels))
    def save(fig,ax,name):
        ax.set_xticks(xp,labels,rotation=45,ha='right'); ax.set_xlabel('UTC calendar month'); ax.grid(alpha=.2); ax.legend(fontsize=8,ncol=3); fig.tight_layout(); fig.savefig(out/name,dpi=150); plt.close(fig); figs.append('figures/'+name)
    for var,unit,name in [('TA','K','01_monthly_temperature.png'),('Q','g/kg','02_monthly_humidity.png')]:
        fig,ax=plt.subplots(figsize=(11,5))
        for h in z:
            p=df[(df.variable==var)&(df.height_m==h)].set_index('period').reindex(labels)
            ax.plot(xp,p['median'].astype(float),marker='o',label=f'{h:g} m')
        ax.set(title=f'Monthly observed {var} medians (missing months are gaps)',ylabel=unit);save(fig,ax,name)
    fig,ax=plt.subplots(figsize=(11,5))
    for (lo,hi),p in lf[lf.threshold_K==.5].groupby(['lower_m','upper_m']):
        ax.plot(xp,100*p.set_index('period').reindex(labels).fraction_valid,marker='o',label=f'{lo:g}–{hi:g} m')
    ax.set(title='Observed positive layer temperature differences > 0.5 K',ylabel='% of valid paired observations',ylim=(0,100));save(fig,ax,'03_monthly_temperature_differences.png')
    for var,num,title,name in [('ZMA','ceiling_count','Recorded visibility at 20 km instrument ceiling','04_monthly_visibility_ceiling.png'),('dewpoint_excess_K','positive_count','Recorded dew point above air temperature','05_monthly_dewpoint_excess.png')]:
        fig,ax=plt.subplots(figsize=(11,5))
        for h in z:
            p=df[(df.variable==var)&(df.height_m==h)].set_index('period').reindex(labels)
            ax.plot(xp,100*p[num]/p.n.replace(0,np.nan),marker='o',label=f'{h:g} m')
        ax.set(title=title,ylabel='% of valid observations',ylim=(0,100));save(fig,ax,name)
    return figs

def run(input_dir,out,start='2025-11',end='2026-10',make_figures=True):
    input_dir=Path(input_dir);out=Path(out);months=month_range(start,end)
    if out.exists() and any(out.iterdir()): raise FileExistsError('Output directory must be empty')
    if not input_dir.is_dir(): raise ValueError('Input directory does not exist')
    inventory=[]; monthly=[]; layers=[]; loaded={}; z=None
    for m in months:
        path=input_dir/(PREFIX+m.strftime('%Y%m')+'.nc')
        expected=m.days_in_month*144
        if not path.is_file():
            inventory.append({'month':str(m),'filename':path.name,'status':'not_available_locally','expected_intervals':expected,'observed_intervals':0,'missing_intervals':expected});continue
        g,h,a,r=load_month(path,m)
        if z is None: z=h
        elif not np.array_equal(h,z): raise ValueError(f'{path.name}: height coordinates differ across months')
        inventory.append(r);loaded[m]=(g,a)
        rr,ll=aggregate(g,z,a,str(m),expected);monthly.extend(rr);layers.extend(ll)
    if not loaded: raise ValueError('No source files available in requested period')
    # Seasonal groups pool actual observations; a single-year SON group can be disjoint.
    seasonal=[];season_layers=[];groups=[]
    for label,nums in SEASONS.items():
        requested=[m for m in months if m.month in nums]; available=[m for m in requested if m in loaded]
        expected=sum(m.days_in_month*144 for m in requested)
        groups.append({'season':label,'requested_months':list(map(str,requested)),'available_months':list(map(str,available)),'expected_intervals':expected,'complete_month_group':len(requested)==len(available)==3,'contiguous_requested_months':all(b.ordinal-a.ordinal==1 for a,b in zip(requested,requested[1:]))})
        if not available: continue
        grid=pd.DatetimeIndex(np.concatenate([loaded[m][0].to_numpy() for m in available]));a={k:np.concatenate([loaded[m][1][k] for m in available],axis=0) for k in loaded[available[0]][1]}
        rr,ll=aggregate(grid,z,a,label,expected);seasonal.extend(rr);season_layers.extend(ll)
    out.mkdir(parents=True,exist_ok=True)
    for name,data in [('monthly_statistics',monthly),('monthly_temperature_differences',layers),('seasonal_statistics',seasonal),('seasonal_temperature_differences',season_layers)]:
        pd.DataFrame(data).to_csv(out/(name+'.csv'),index=False)
    figures=plots(out/'figures',monthly,layers,months,z) if make_figures else []
    report={'status':'descriptive_thermodynamic_seasonal_study','requested_months':list(map(str,months)),'processed_months':len(loaded),'expected_intervals':sum(m.days_in_month*144 for m in months),'observed_intervals':sum(len(g) for g,_ in loaded.values()),'height_levels_m':z.tolist(),'source_inventory':inventory,'season_groups':groups,'figures':figures,'limitations':['One site and selected period, not a long-term climate normal.','Missing months or intervals are not imputed. Seasonal groups pool valid observations rather than monthly medians; autumn may be split across the window.','No wind analysis or model fitting. Temperature differences are descriptive, not stability classification.','Visibility ceiling is an instrument limitation; dew point and specific humidity are not independent.','Local source hashes record reproducibility, not independent provider authentication.']}
    (out/'seasonal_summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--start-month',default='2025-11');p.add_argument('--end-month',default='2026-10');a=p.parse_args();print(json.dumps(run(a.input_dir,a.out,a.start_month,a.end_month),indent=2))
