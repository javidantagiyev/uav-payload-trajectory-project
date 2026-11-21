import sys,json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cabauw_climate_archive import run,parse_names,era,PREFIX

def make(raw,period,temp=280):
    t=pd.date_range(period+'-01',periods=4,freq='10min')
    a=np.full((4,2),float(temp)); a[0,1]=np.nan
    ds=xr.Dataset({k:(('time','z'),v,{'units':u}) for k,v,u in [('TA',a,'K'),('TD',a-1,'K'),('Q',np.full_like(a,5),'g kg-1'),('ZMA',np.full_like(a,20000),'m')]},coords={'time':t,'z':('z',[2.,10.],{'units':'m'})})
    ds.to_netcdf(raw/(PREFIX+period.replace('-','')+'.nc'),engine='scipy')

def fixture(p):
    raw=p/'raw';raw.mkdir();make(raw,'2025-02');make(raw,'2026-02',282);make(raw,'2025-03');i=p/'inventory.json';i.write_text(json.dumps([x.name for x in raw.glob('*.nc')]+[PREFIX+'200601.nc']));return raw,i

def test_matching(tmp_path):
    raw,i=fixture(tmp_path);o=tmp_path/'out';r=run(raw,o,i,False);assert r['matched_months']==[2];assert r['advertised_not_local']==['2006-01'];d=pd.read_csv(o/'matched_2025_2026.csv');assert len(d)==4;assert d.loc[d.variable=='TA','median_difference'].iloc[0]==pytest.approx(2);assert not d.both_coverage_ge_90pct.any();assert np.isnan(d.loc[d.variable=='ZMA','median_difference'].iloc[0]);assert d.loc[d.variable=='TA','n_base'].iloc[0]==3

def test_eras():
    assert era(pd.Period('2006-01'))=='pre_2010_change';assert era(pd.Period('2010-04'))=='2010_2013_transition';assert era(pd.Period('2014-01'))=='2014_onward_documented_configuration'

def test_inventory_dedup():
    assert len(parse_names([PREFIX+'202501.nc']*2+['other.nc']))==1

def test_plots_and_no_overwrite(tmp_path):
    raw,i=fixture(tmp_path);o=tmp_path/'out';r=run(raw,o,i);assert len(r['figures'])==5;assert all((o/n).stat().st_size>0 for n in r['figures']);
    with pytest.raises(FileExistsError):run(raw,o,i,False)

def test_empty(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();i=tmp_path/'i.json';i.write_text('[]');
    with pytest.raises(ValueError):run(raw,tmp_path/'out',i,False)
