import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import xarray as xr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.cabauw_thermodynamic_climatology import read_observations,inversion_events,summarize,run,sha256


def fixture():
    t=pd.date_range('2026-10-01',periods=6,freq='10min').to_numpy()
    z=[200,2,20]; T=np.array([[280,279,279.5],[280,279,279.5],[279,280,279.5],[np.nan,279,279.5],[280,279,279.5],[280,279,279.5]])
    return xr.Dataset({'TA':(('time','z'),T,{'units':'K'}),'TD':(('time','z'),T-2,{'units':'K'}),'Q':(('time','z'),np.full(T.shape,7.),{'units':'g kg-1'}),'ZMA':(('time','z'),np.full(T.shape,20000.),{'units':'m'})},coords={'time':t,'z':('z',z,{'units':'m'})})


def test_height_sort_and_pair_counts():
    _,grid,z,a,_,_=read_observations(fixture()); assert list(z)==[2,20,200]
    inv,events,_,_,vis,_=summarize(grid,z,a)
    row=next(r for r in inv if r['lower_m']==2 and r['upper_m']==200 and r['threshold_K']==0)
    assert row['valid_pairs']==5 and row['above_threshold_count']==4 and row['observed_runs']==2
    assert row['fraction_of_valid']==.8 and row['longest_nominal_minutes']==20
    assert all(v['fraction_equal_20000_m']==1 for v in vis)


def test_event_missing_and_gap():
    grid=pd.DatetimeIndex(['2026-10-01 00:00','2026-10-01 00:10','2026-10-01 00:30','2026-10-01 00:40','2026-10-01 00:50'],tz='UTC')
    rows=inversion_events(grid,[1,1,1,np.nan,1],0)
    assert [r['intervals'] for r in rows]==[2,1,1]
    assert all(r['right_censored'] for r in rows)


def test_units_and_time():
    ds=fixture();ds.TA.attrs['units']='C'
    with pytest.raises(ValueError,match='TA'):read_observations(ds)
    ds=fixture();ds=ds.assign_coords(time=ds.time.values+np.timedelta64(2,'s'))
    with pytest.raises(ValueError,match='Time grid'):read_observations(ds)


def test_missing_and_invalid():
    ds=fixture();ds.Q.values[0,0]=1001;ds.ZMA.values[0,0]=-1
    _,_,_,a,rejected,_=read_observations(ds)
    assert rejected['Q']['finite_outside_basic_range']==1
    assert np.isnan(a['Q'][0,-1])
    assert rejected['ZMA']['finite_outside_basic_range']==1


def test_threshold_is_strict():
    grid=pd.date_range('2026-10-01',periods=3,freq='10min',tz='UTC')
    assert inversion_events(grid,[.1,.1001,.5],.1)[0]['intervals']==2
    assert inversion_events(grid,[.1,.1001,.5],.5)==[]


def test_no_valid_pairs():
    ds=fixture();ds.TA.values[:]=np.nan
    _,grid,z,a,_,_=read_observations(ds)
    inv,*_=summarize(grid,z,a)
    assert all(r['fraction_of_valid'] is None and r['observed_runs']==0 for r in inv)


def test_end_to_end(tmp_path):
    p=tmp_path/'fixture.nc';fixture().to_netcdf(p,engine='scipy');out=tmp_path/'out'
    with pytest.raises(ValueError,match='SHA256'):run(p,out,'wrong')
    assert not out.exists()
    result=run(p,out,sha256(p));assert result['timestamps']==6 and len(result['figures'])==9
    assert (out/'climatology_summary.json').exists()
    with pytest.raises(FileExistsError):run(p,out)
