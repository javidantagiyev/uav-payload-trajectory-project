from pathlib import Path
from zipfile import ZipFile
import importlib.util
import pytest
p=Path(__file__).resolve().parents[1]/'experiments'/'surface_climate_comparison.py'
spec=importlib.util.spec_from_file_location('surface_climate_comparison',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture(tmp_path,rows):
    p=tmp_path/'source.zip'
    with ZipFile(p,'w') as z:
        z.writestr('produkt_test.txt','STATIONS_ID;MESS_DATUM;QN;TT_10;TD_10\n'+rows)
    return p

def test_units_missing_and_counts(tmp_path):
    p=fixture(tmp_path,'1975;202501010000;3;4;2\n1975;202501010010;3;-999;1\n')
    d,meta=m.read_dwd(p,'01975');a=d[(d.month==1)&(d.variable=='TA')].iloc[0]
    assert a.n==1 and a.observed==2 and a['median']==4 and a.expected==4464
    assert len(d)==24 and meta['quality_code_counts']=={'3':2}

def test_duplicate(tmp_path):
    p=fixture(tmp_path,'1975;202501010000;3;4;2\n1975;202501010000;3;4;2\n')
    with pytest.raises(ValueError,match='Duplicate'): m.read_dwd(p,'01975')

def test_station(tmp_path):
    p=fixture(tmp_path,'3015;202501010000;3;4;2\n')
    with pytest.raises(ValueError,match='Station'): m.read_dwd(p,'01975')

def test_off_grid(tmp_path):
    p=fixture(tmp_path,'1975;202501010001;3;4;2\n')
    with pytest.raises(ValueError,match='off-grid'): m.read_dwd(p,'01975')

def test_overwrite(tmp_path):
    with pytest.raises(FileExistsError): m.run(tmp_path,tmp_path,tmp_path)
