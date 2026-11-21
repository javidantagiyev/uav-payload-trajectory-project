"""small synthetic netcdf fixture ensures converter does not silently guess units."""

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.convert_tower_netcdf import convert_file
from src.physics.atmospheric_observations import load_profiles


def make_input(tmp_path, speed_units="m/s", direction_units="degree"):
    xr=pytest.importorskip("xarray")
    pytest.importorskip("scipy")
    t=np.array(['2026-01-01T00:00:00','2026-01-01T00:10:00'],dtype='datetime64[s]')
    ds=xr.Dataset({
      'F010':('time',[3.,4.],{'units':speed_units}),
      'D010':('time',[90.,180.],{'units':direction_units}),
      'F020':('time',[4.,5.],{'units':speed_units}),
      'D020':('time',[45.,90.],{'units':direction_units}),
      'F040':('time',[5.,6.],{'units':speed_units}),
      'D040':('time',[0.,270.],{'units':direction_units})}, coords={'time':t})
    f=tmp_path/'fixture.nc';ds.to_netcdf(f,engine='scipy')
    mapping={'time':'time','levels':{str(z):{'speed':f'F{z:03d}','direction_from':f'D{z:03d}'}
                                     for z in (10,20,40)}}
    m=tmp_path/'map.json';m.write_text(json.dumps(mapping))
    return f,m


def convert(tmp_path, f,m):
    return convert_file(f,m,tmp_path/'canon.csv',tmp_path/'canon.json',
                        'synthetic_converter_test','test','1','generated-test',
                        'synthetic_site','test-only','synthetic')


def test_converter_correct_vector_conversion(tmp_path):
    f,m=make_input(tmp_path)
    assert convert(tmp_path,f,m)==6
    metadata,profiles=load_profiles(tmp_path/'canon.csv',tmp_path/'canon.json')
    assert len(profiles)==2
    assert profiles[0][0].east_m_s==pytest.approx(-3)
    assert profiles[0][0].north_m_s==pytest.approx(0,abs=1e-8)
    assert metadata['raw_netcdf_sha256']


def test_converter_rejects_wrong_speed_units(tmp_path):
    f,m=make_input(tmp_path,speed_units='knots')
    with pytest.raises(ValueError,match='units'):
        convert(tmp_path,f,m)


def test_converter_rejects_wrong_direction_units(tmp_path):
    f,m=make_input(tmp_path,direction_units='radians')
    with pytest.raises(ValueError,match='direction units'):
        convert(tmp_path,f,m)


def test_converter_rejects_unknown_variable(tmp_path):
    f,m=make_input(tmp_path)
    mapping=json.loads(m.read_text());mapping['levels']['40']['speed']='F_UNKNOWN'
    m.write_text(json.dumps(mapping))
    with pytest.raises(ValueError,match='missing'):
        convert(tmp_path,f,m)
