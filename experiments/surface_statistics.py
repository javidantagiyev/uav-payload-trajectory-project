"""Standalone descriptive surface climate statistics; no forecasts or flight models."""
import argparse, calendar, hashlib, json
from pathlib import Path
from zipfile import ZipFile
from itertools import combinations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SITES={'01975':'Hamburg-Fuhlsbuettel','03015':'Lindenberg'}
YEAR=2025

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def grid(): return pd.date_range('2025-01-01','2026-01-01',freq='10min',inclusive='left',tz='UTC')

def read_summary(path):
    d=pd.read_csv(path)
    req={'site','month','variable','unit','expected','observed','n','coverage','q25','median','q75'}
    if not req.issubset(d): raise ValueError('Missing summary fields')
    if len(d)!=72 or d.duplicated(['site','month','variable']).any() or set(d.site)!={'Cabauw',*SITES.values()} or set(d.variable)!={'TA','TD'} or set(d.month)!=set(range(1,13)) or set(d.unit)!={'degC'}: raise ValueError('Unexpected summary domain')
    exp=d.month.map(lambda m:calendar.monthrange(YEAR,int(m))[1]*144)
    if not d.expected.eq(exp).all() or not ((d.n>=0)&(d.n<=d.observed)&(d.observed<=d.expected)).all() or not np.allclose(d.coverage,d.n/exp): raise ValueError('Invalid counts')
    live=d.n>0
    if not np.isfinite(d.loc[live,['q25','median','q75']]).all().all() or not ((d.loc[live,'q25']<=d.loc[live,'median'])&(d.loc[live,'median']<=d.loc[live,'q75'])).all(): raise ValueError('Invalid quantiles')
    return d

def read_dwd(path, station):
    with ZipFile(path) as z:
        files=[n for n in z.namelist() if Path(n).name.lower().startswith('produkt_') and n.lower().endswith('.txt')]
        if len(files)!=1: raise ValueError('Expected one product member')
        with z.open(files[0]) as f: d=pd.read_csv(f,sep=';',dtype=str,encoding='latin1')
    d.columns=d.columns.str.strip()
    if not pd.to_numeric(d.STATIONS_ID,errors='raise').eq(int(station)).all(): raise ValueError('Station mismatch')
    t=pd.to_datetime(d.MESS_DATUM.str.strip(),format='%Y%m%d%H%M',utc=True,errors='raise')
    d=d.loc[t.dt.year.eq(YEAR)].copy(); d.index=pd.DatetimeIndex(t[t.dt.year.eq(YEAR)])
    if d.empty or d.index.has_duplicates or not (d.index.minute%10==0).all(): raise ValueError('Empty, duplicate or off-grid times')
    qn=d.QN.str.strip().fillna('missing').value_counts().to_dict()
    x=d[['TT_10','TD_10']].apply(pd.to_numeric,errors='raise').replace(-999,np.nan).rename(columns={'TT_10':'TA','TD_10':'TD'})
    for v in x:
        a=x[v].dropna()
        if not np.isfinite(a).all() or not a.between(-100,70).all(): raise ValueError('Unexpected temperature range')
    meta={'station':station,'sha256':sha(path),'timestamp_records':len(d),'quality_codes':qn,'file':str(path)}
    return x.sort_index().reindex(grid()),meta

def daily(x):
    n=x.resample('D').count(); med=x.resample('D').median().where(n>=130)
    return pd.DataFrame({'n':n,'coverage':n/144,'median':med})

def lag_corr(x,k):
    # preserve calendar gaps; correlation of paired available daily medians.
    a=np.asarray(x,float); left=a[:-k]; right=a[k:]; valid=np.isfinite(left)&np.isfinite(right)
    u,v=left[valid],right[valid]; n=len(u)
    return (float(np.corrcoef(u,v)[0,1]) if n>=3 and np.std(u)>0 and np.std(v)>0 else np.nan),n

def median_bounds(x, expected):
    # Exact order-statistic bounds for conventional even-sample median, no assumed missing values.
    a=np.sort(np.asarray(x,float)); a=a[np.isfinite(a)]; n=len(a); m=expected-n
    if m<0 or expected<=0: raise ValueError('Invalid expected count')
    ranks=[(expected-1)//2,expected//2]
    lower=[a[r-m] if r>=m else -np.inf for r in ranks]
    upper=[a[r] if r<n else np.inf for r in ranks]
    return float(np.mean(lower)),float(np.mean(upper))

def sensitivity(d):
    rows=[]; leave=[]
    for var,g in d.groupby('variable'):
        for a,b in combinations(sorted(g.site.unique()),2):
            p=g[g.site.eq(a)].merge(g[g.site.eq(b)],on='month',suffixes=('_a','_b'))
            for cut in [.75,.90,.95,.99]:
                h=p[(p.coverage_a>=cut)&(p.coverage_b>=cut)].copy()
                diff=h.median_a-h.median_b
                rows.append(dict(variable=var,site_a=a,site_b=b,threshold=cut,months=len(h),included_months=';'.join(map(str,h.month)),mean_monthly_median_difference=diff.mean()))
                if cut==.90:
                    for m in h.month:
                        leave.append(dict(variable=var,site_a=a,site_b=b,omitted_month=m,remaining_months=len(h)-1,mean_monthly_median_difference=diff[h.month.ne(m)].mean()))
    return pd.DataFrame(rows),pd.DataFrame(leave)

def run(summary,out,dwd_dir=None):
    summary,out=Path(summary),Path(out)
    if out.exists(): raise FileExistsError(out)
    d=read_summary(summary); out.mkdir(parents=True); figs=out/'figures'; figs.mkdir()
    # For N expected, n observed, median central ranks lie inside observed IQR when exact rank conditions hold.
    # Use a conservative linear-quantile rank check, not general imputation.
    s=d.copy(); lo_rank=(s.expected-1)//2-(s.expected-s.n); hi_rank=s.expected//2
    s['iqr_contains_complete_median']= (s.n>0)&(lo_rank>=np.ceil((s.n-1)*.25))&(hi_rank<=np.floor((s.n-1)*.75))
    s['missing_records']=s.expected-s.n
    s.to_csv(out/'monthly_missingness.csv',index=False)
    sens,leave=sensitivity(d); sens.to_csv(out/'coverage_sensitivity.csv',index=False);leave.to_csv(out/'leave_one_month_out.csv',index=False)
    for v,g in s.groupby('variable'):
        fig,ax=plt.subplots(figsize=(9,4));
        for site,h in g.groupby('site'): ax.plot(h.month,h.coverage*100,'o-',label=site)
        for y in [90,95,99]: ax.axhline(y,ls=':',color='gray',lw=.8)
        ax.set(xlabel='Month (2025)',ylabel='Valid observations (%)',title=f'{v}: monthly coverage sensitivity',xticks=range(1,13));ax.legend();fig.tight_layout();fig.savefig(figs/f'coverage_{v}.png',dpi=150);plt.close(fig)
    for v,g in sens.groupby('variable'):
        fig,ax=plt.subplots(figsize=(9,4))
        for (a,b),h in g.groupby(['site_a','site_b']): ax.plot(h.threshold*100,h.mean_monthly_median_difference,'o-',label=f'{a} − {b}')
        ax.axhline(0,color='gray',lw=.8);ax.set(xlabel='Minimum monthly coverage (%)',ylabel='Mean monthly median difference (°C)',title=f'{v}: sensitivity to coverage screening');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figs/f'sensitivity_{v}.png',dpi=150);plt.close(fig)
    meta=[]; dailyrows=[]; lags=[]; bounds=[]
    if dwd_dir is not None:
        for station,site in SITES.items():
            file=Path(dwd_dir)/f'10minutenwerte_TU_{station}_20200101_20251231_hist.zip'
            x,m=read_dwd(file,station);meta.append(m)
            for v in x:
                dd=daily(x[v]); dailyrows.append(dd.assign(site=site,variable=v).rename_axis('date').reset_index())
                # Remove calendar-month mean of valid daily medians for a descriptive within-month diagnostic.
                an=dd['median']-dd['median'].groupby(dd.index.month).transform('mean')
                for k in [1,2,3,7,14]:
                    for label,y in [('raw',dd['median']),('month_centered',an)]:
                        r,n=lag_corr(y,k);lags.append(dict(site=site,variable=v,series=label,lag_days=k,correlation=r,pairs=n))
                for month,h in x[v].groupby(x.index.month):
                    lo,hi=median_bounds(h,len(h)); bounds.append(dict(site=site,variable=v,month=month,n=h.count(),expected=len(h),observed_median=h.median(),lower=lo,upper=hi))
        da=pd.concat(dailyrows,ignore_index=True);da.to_csv(out/'daily_medians.csv',index=False);pd.DataFrame(lags).to_csv(out/'daily_lag_correlations.csv',index=False);pd.DataFrame(bounds).to_csv(out/'median_missingness_bounds.csv',index=False)
        for v,g in da.groupby('variable'):
            fig,ax=plt.subplots(figsize=(12,4));
            for site,h in g.groupby('site'): ax.plot(h.date,h['median'],lw=1,label=site)
            ax.set(ylabel='°C',title=f'{v}: daily median, minimum 130/144 readings');ax.legend();fig.tight_layout();fig.savefig(figs/f'daily_{v}.png',dpi=150);plt.close(fig)
        for v,g in pd.DataFrame(lags).groupby('variable'):
            fig,ax=plt.subplots(figsize=(9,4))
            for (site,series),h in g.groupby(['site','series']): ax.plot(h.lag_days,h.correlation,'o-',label=f'{site} {series}')
            ax.axhline(0,color='gray',lw=.8);ax.set(xlabel='Lag (days)',ylabel='Paired Pearson correlation',ylim=(-1,1),title=f'{v}: descriptive daily dependence');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figs/f'lags_{v}.png',dpi=150);plt.close(fig)
    result={'status':'surface_climate_statistics','summary_sha256':sha(summary),'monthly_rows':len(d),'below_90_percent':int((d.coverage<.90).sum()),'iqr_containment_rows':int(s.iqr_contains_complete_median.sum()),'sensitivity_rows':len(sens),'leave_one_month_out_rows':len(leave),'dwd_sources':meta,'figures':sorted(p.name for p in figs.glob('*.png')),'limitations':['Equal-weight averages of monthly medians are not annual medians.','Omitted-month and cutoff results are sensitivity checks, not confidence intervals.','Daily correlations are pairwise descriptive statistics, not conventional full-series ACF or forecasts.','Month centering does not establish stationarity.','No instrument calibration uncertainty inferred from quality codes.','Median bounds address missing data only; no measurement-error allowance.','Cabauw raw daily records not processed; comparisons use existing nominal surface summaries.','No wind, vertical profile model, flight model, or trajectory analysis.']}
    (out/'summary.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--summary',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--dwd-dir',type=Path);a=p.parse_args();print(json.dumps(run(a.summary,a.out,a.dwd_dir),indent=2))
