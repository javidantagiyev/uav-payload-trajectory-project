"""Regression tests against the Cabauw tower F(time,z), D(time,z) schema."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.inspect_knmi_cabauw import inspect_file
from experiments.convert_tower_netcdf import convert_file
from experiments.knmi_tower_schema import resolve_wind_levels

pytest.importorskip('xarray')
import xarray as xr


def fixture_tower(tmp_path, *, heights=(2,10,20,40,80,140,200), dims=('time','z'), speed_units='m s-1', z_units='m', direction_std='wind_from_direction'):
    times = np.arange('2024-06-01T00:00','2024-06-01T01:00', dtype='datetime64[10m]').astype('datetime64[ns]')
    shape = (len(times),len(heights))
    speed = np.broadcast_to(np.arange(len(heights),dtype=float)+3,shape).copy()
    direction = np.broadcast_to(np.arange(len(heights),dtype=float)+150,shape).copy()
    if dims == ('z','time'):
        speed,direction=speed.T,direction.T
    ds=xr.Dataset({'F':(dims,speed,{'units':speed_units,'standard_name':'wind_speed'}),
                   'D':(dims,direction,{'units':'degree','standard_name':direction_std})},
                  coords={'time':times,'z':('z',np.asarray(heights,dtype=float),{'units':z_units})},
                  attrs={'title':'synthetic tower 2d fixture'})
    p=tmp_path/'tower.nc';ds.to_netcdf(p,engine='scipy')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                    'filename':p.name,'dataset':'cesar_tower_meteo_lb1_t10','version':'v1.3'}))
    return p,manifest


def map_path():
    return ROOT/'data/examples/knmi_cabauw_tower_profile_mapping.json'


@pytest.mark.parametrize('order', [('time','z'),('z','time')])
def test_tower_schema_inspection_and_conversion(tmp_path,order):
    p, manifest = fixture_tower(tmp_path,dims=order)
    r=inspect_file(p,map_path(),manifest)
    assert r['time_count']==6 and len(r['levels'])==6
    assert r['levels']['10.0']['speed_var']=='F'
    rows=convert_file(p,map_path(),tmp_path/'out.csv',tmp_path/'out.metadata.json',
            'KNMI','cesar_tower_meteo_lb1_t10','v1.3','https://example.org','CABAUW','CC-BY-4.0','observed')
    assert rows == 36
    csv_lines=(tmp_path/'out.csv').read_text().splitlines()
    assert len(csv_lines)==37
    assert csv_lines[1].split(',')[2]=='10.0'


def test_missing_height_rejected(tmp_path):
    p,_=fixture_tower(tmp_path,heights=(2,10,20,40,80,140,190))
    with pytest.raises(ValueError,match='200.*not uniquely present'):
        inspect_file(p,map_path())


def test_bad_height_units_rejected(tmp_path):
    p,_=fixture_tower(tmp_path,z_units='km')
    with pytest.raises(ValueError,match='metres'):
        inspect_file(p,map_path())


def test_bad_direction_metadata_rejected(tmp_path):
    p,_=fixture_tower(tmp_path,direction_std='wind_to_direction')
    with pytest.raises(ValueError,match='meteorological FROM'):
        inspect_file(p,map_path())


def test_wrong_speed_units_rejected(tmp_path):
    p,_=fixture_tower(tmp_path,speed_units='km/h')
    with pytest.raises(ValueError,match='m/s'):
        inspect_file(p,map_path())


def test_full_pipeline_2d_tower(tmp_path):
    pytest.importorskip('matplotlib')
    p,manifest=fixture_tower(tmp_path)
    from experiments.run_knmi_cabauw_stage5 import execute
    summary=execute(p,manifest,map_path(),tmp_path/'verified', max_times=6)
    assert summary['observations_converted']==36
    assert summary['profiles']==6
    assert summary['eligible_model_rows']>0
    assert len(summary['figures'])==6
