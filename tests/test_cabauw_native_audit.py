import sys
from pathlib import Path
import numpy as np
import pytest
import xarray as xr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from audit_cabauw_native import timestamp_audit, inspect_native, run, sha256_file


def fixture():
    t=np.array(['2026-10-01T00:00:00','2026-10-01T00:09:59','2026-10-01T00:20:00'],dtype='datetime64[s]')
    z=[2.,10.,200.]
    ds=xr.Dataset({'TA':(('time','z'),[[285,286,287],[284,np.nan,286],[283,284,285]],{'units':'K'}),
                   'Q':(('time','z'),np.full((3,3),5.),{'units':'g kg-1'}),
                   'F':(('time','z'),np.full((3,3),2.),{'units':'m s-1'}),
                   'D':(('time','z'),[[90,360,400],[0,30,60],[90,180,270]],{'units':'degree'})},coords={'time':t,'z':('z',z,{'units':'m'})})
    return ds


def test_offset_not_rewritten():
    t,offset,r=timestamp_audit(fixture().time.values)
    assert offset.tolist()==[0,-1,0]
    assert r['nonzero_grid_offset_count']==1
    assert not r['timestamps_modified']


def test_duplicate_time_rejected():
    with pytest.raises(ValueError):timestamp_audit(np.array(['2026-01-01','2026-01-01'],dtype='datetime64[s]'))


def test_inventory_counts_and_missing_values():
    _,z,_,r,v=inspect_native(fixture())
    assert len(z)==3
    assert sum(i.get('basic_range_violation',0) for i in r['inventory'] if i['variable']=='D')==1
    assert np.isnan(v['TA'][1,1])
    assert any(i['variable']=='SF' and i['status']=='absent' for i in r['inventory'])


def test_wrong_units_not_interpreted():
    ds=fixture();ds['Q'].attrs['units']='unknown'
    *_,r,v=inspect_native(ds)
    assert 'Q' not in v
    assert any(i['status']=='unsupported_schema_or_units' for i in r['inventory'])


def test_native_bounds():
    ds=fixture();t=ds.time.values
    ds['time_bnds']=(('time','bnds'), np.column_stack([t,t+np.timedelta64(600,'s')]))
    *_,r,v=inspect_native(ds)
    assert r['time_bounds']['status']=='bounds_inspected'
    assert r['time_bounds']['minimum_width_s']==600


def test_end_to_end(tmp_path):
    f=tmp_path/'fixture.nc'; fixture().to_netcdf(f,engine='scipy')
    out=tmp_path/'results';r=run(f,out,sha256_file(f))
    assert r['expected_hash_matched'] and len(r['figures'])==2
    assert (out/'variable_completeness.csv').exists()
    with pytest.raises(FileExistsError):run(f,out)
    with pytest.raises(ValueError):run(f,tmp_path/'wrong','0'*64)
