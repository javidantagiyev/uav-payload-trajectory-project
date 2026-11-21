import sys
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.cabauw_measurement_consistency import summarize,run,sha256

def fixture():
    z=[2.,20.]; t=pd.date_range('2026-10-01',periods=4,freq='10min'); ta=np.full((4,2),280.);td=ta+np.array([[0,.25],[.5,-1],[np.nan,1],[0,-.2]])
    a={'TA':ta,'TD':td,'Q':np.full((4,2),6.),'ZMA':np.array([[50,20000],[1000,10000],[20000,20001],[np.nan,20000]])}
    return t,z,a

def test_thresholds_and_missing():
    t,z,a=fixture();d,_,_,f,_,_=summarize(t,z,a);r=d[(d.height_m==2)&(d.date_utc=='all')];assert r.valid_pairs.tolist()==[3]*5;assert r['count'].tolist()==[1,1,1,0,0];assert len(f)==3

def test_visibility_partition():
    t,z,a=fixture();_,r,v,*_=summarize(t,z,a);assert r.groupby('height_m').valid_pairs.sum().tolist()==[3,4];assert v.above_ceiling_count.tolist()==[0,1];assert v.ceiling_count.tolist()==[1,2]

def test_derived_coverage():
    t,z,a=fixture();_,_,_,_,c,_=summarize(t,z,a);assert c.q_only.tolist()==[1,0];assert c.both_valid.tolist()==[3,4]

def test_empty_pairs():
    t,z,a=fixture();a['TD'][:]=np.nan;r,_,_,f,*_=summarize(t,z,a);assert r.fraction.isna().all() and len(f)==0

def test_end_to_end(tmp_path):
    t,z,a=fixture();units={'TA':'K','TD':'K','Q':'g kg-1','ZMA':'m'}
    ds=xr.Dataset({k:(('time','z'),v,{'units':units[k]}) for k,v in a.items()},coords={'z':('z',z,{'units':'m'}),'time':t});p=tmp_path/'test.nc';ds.to_netcdf(p,engine='scipy');out=tmp_path/'out'
    with pytest.raises(ValueError,match='SHA256'):run(p,out,'bad')
    r=run(p,out,sha256(p));assert r['positive_excess_count']==3 and r['valid_temperature_dewpoint_pairs']==7;assert len(list((out/'figures').glob('*.png')))==5
    with pytest.raises(FileExistsError):run(p,out,sha256(p))
