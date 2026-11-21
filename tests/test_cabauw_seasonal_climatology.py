import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import xarray as xr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cabauw_seasonal_climatology import run,PREFIX

def make(p,month,values=(280.,281.),time=None,heights=(2.,10.)):
    if time is None: time=pd.date_range(month+'-01',periods=2,freq='10min')
    a=np.tile(values,(len(time),1));d=xr.Dataset({k:(('time','z'),v,{'units':unit}) for k,v,unit in [('TA',a,'K'),('TD',a-1,'K'),('Q',np.full_like(a,7),'g kg-1'),('ZMA',np.full_like(a,20000),'m')]},coords={'time':time,'z':('z',np.asarray(heights),{'units':'m'})});d.to_netcdf(p/(PREFIX+month.replace('-','')+'.nc'),engine='scipy')

def test_missing_month_and_pool(tmp_path):
    make(tmp_path,'2025-12');make(tmp_path,'2026-02',(290.,291.));o=tmp_path/'out';r=run(tmp_path,o,'2025-12','2026-02',False)
    assert r['processed_months']==2 and r['observed_intervals']==4 and r['expected_intervals']==90*144
    assert r['source_inventory'][1]['status']=='not_available_locally'
    d=pd.read_csv(o/'seasonal_statistics.csv');s=d[(d.variable=='TA')&(d.height_m==2)].iloc[0];assert s['median']==285 and s.n==4

def test_month_mismatch(tmp_path):
    make(tmp_path,'2025-12',time=pd.date_range('2026-01-01',periods=2,freq='10min'))
    with pytest.raises(ValueError,match='outside filename month'):run(tmp_path,tmp_path/'o','2025-12','2025-12',False)

def test_mismatched_heights(tmp_path):
    make(tmp_path,'2025-12');make(tmp_path,'2026-01',heights=(2.,20.))
    with pytest.raises(ValueError,match='height coordinates differ'):run(tmp_path,tmp_path/'o','2025-12','2026-01',False)

def test_no_data(tmp_path):
    with pytest.raises(ValueError,match='No source'):run(tmp_path,tmp_path/'o','2025-12','2025-12',False)

def test_figures_and_output_refusal(tmp_path):
    make(tmp_path,'2025-12');o=tmp_path/'o';r=run(tmp_path,o,'2025-12','2026-02');assert len(r['figures'])==5;assert all((o/p).stat().st_size>0 for p in r['figures'])
    with pytest.raises(FileExistsError):run(tmp_path,o,'2025-12','2026-02',False)
