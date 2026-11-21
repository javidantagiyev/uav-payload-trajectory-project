import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from experiments.surface_statistics import median_bounds, lag_corr, daily, grid, read_dwd, sensitivity
from zipfile import ZipFile

def test_bounds_exact():
    assert median_bounds([1,2,3,4],5)==(2,3)
    assert median_bounds([1,2,3],4)==(1.5,2.5)
    assert median_bounds([1,2,3,4],4)==(2.5,2.5)
    assert median_bounds([],4)==(-np.inf,np.inf)

def test_gaps_not_compressed():
    r,n=lag_corr([1,2,np.nan,3,4,5],1)
    assert n==3 and r==pytest.approx(1)

def test_constant():
    r,n=lag_corr([1,1,1,1],1);assert np.isnan(r) and n==3

def test_daily():
    x=pd.Series(1.,index=grid()[:288]);x.iloc[:15]=np.nan
    d=daily(x);assert np.isnan(d['median'].iloc[0]) and d['median'].iloc[1]==1

def test_dwd(tmp_path):
    p=tmp_path/'x.zip'
    with ZipFile(p,'w') as z:z.writestr('produkt_x.txt','STATIONS_ID;MESS_DATUM;QN;TT_10;TD_10\n01975;202501010000;3;5;-999\n01975;202501010020;3;6;4\n')
    d,m=read_dwd(p,'01975');assert len(d)==52560 and d.TA.count()==2 and d.TD.count()==1 and m['quality_codes']=={'3':2}
    with pytest.raises(ValueError):read_dwd(p,'03015')

def test_sensitivity():
    d=pd.DataFrame({'site':['A','A','B','B'],'month':[1,2,1,2],'variable':['TA']*4,'coverage':[1,.8,1,1],'median':[2,10,1,3]})
    s,l=sensitivity(d);assert s.loc[s.threshold.eq(.75),'mean_monthly_median_difference'].item()==4
    assert s.loc[s.threshold.eq(.90),'mean_monthly_median_difference'].item()==1
