"""stage 6 scientific contracts: matched information, held-out time, provenance and QA."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from src.physics.atmospheric_observations import WindObservation
from src.physics.atmospheric_stage6 import (
    make_observation_table, build_targets, fixed_scale, _fit_parameter,
    fit_daily_cv, all_model_predictions, direction_errors, metrics, grouped_metrics,
    paired_day_bootstrap, temporal_holdout, quality_report,
)


def synthetic_profiles(days=7, alpha=.25, base=3., missing=False):
    rows=[]
    for d in range(days):
        t=datetime(2026,10,1,tzinfo=timezone.utc)+timedelta(days=d)
        speed=base+.1*d
        levels=[]
        for z in (10.,20.,40.,80.):
            if missing and d==1 and z==20.:continue
            vec=speed*(z/10.)**alpha
            levels.append(WindObservation(t,"TEST",z,vec,0.))
        rows.append(tuple(levels))
    return rows


def test_fixed_scaling_reference_and_neutral():
    for m in ('no_shear_10m','power_1_7_fixed','neutral_log_z0_003_fixed'):
        assert fixed_scale(m,10)==pytest.approx(1)
    assert fixed_scale('power_1_7_fixed',40)>1
    with pytest.raises(ValueError):fixed_scale('not-a-model',20)


def test_cv_fit_uses_only_other_days_and_reproduces_power_exponent():
    x=build_targets(make_observation_table(synthetic_profiles()))
    cv,fold=fit_daily_cv(x)
    assert set(cv.model)=={'power_alpha_heldout_day','log_z0_heldout_day'}
    assert all(fold.train_days==6)
    assert np.allclose(fold.power_alpha, .25,atol=1e-12)
    powerv=cv[cv.model=='power_alpha_heldout_day']
    assert np.allclose(powerv.predicted_east,powerv.east,atol=1e-12)


def test_same_day_outlier_does_not_leak_into_heldout_fitting():
    normal=build_targets(make_observation_table(synthetic_profiles()))
    _,fold1=fit_daily_cv(normal)
    perturbed=normal.copy()
    perturbed.loc[(perturbed.date_utc=='2026-10-01')&(perturbed.height_agl_m==40.),'east']+=1000.
    _,fold2=fit_daily_cv(perturbed)
    p1=fold1.loc[fold1.date_utc=='2026-10-01','power_alpha'].iloc[0]
    p2=fold2.loc[fold2.date_utc=='2026-10-01','power_alpha'].iloc[0]
    assert p1==p2


def test_extra_sensor_models_marked_differently_and_holdout_excluded():
    obs=make_observation_table(synthetic_profiles())
    pred,fit=all_model_predictions(obs,build_targets(obs))
    primary=pred[pred.information_class=='10m_only']
    extra=pred[pred.information_class=='extra_simultaneous_height_sensors']
    assert len(primary)==7*2*5
    assert len(extra)==7*2*2
    assert all(primary.model!='interpolation_extra_sensors')
    assert 'interpolation_extra_sensors' in set(extra.model)


def test_zero_wind_direction_is_masked():
    obs=make_observation_table(synthetic_profiles(base=0.))
    # simulate explicitly zero reference on one day
    obs.loc[(obs.date_utc=='2026-10-01')&(obs.height_agl_m==10.),['east','north','speed']]=0.
    pred,_=all_model_predictions(obs,build_targets(obs))
    pred=direction_errors(pred,2.)
    sub=pred[pred.date_utc=='2026-10-01']
    assert not sub.direction_evaluable.any()
    assert sub.direction_error_deg.isna().all()


def test_quality_cadence_rounding_is_not_missing():
    p=synthetic_profiles(days=5)
    p2=[]
    for i,profile in enumerate(p):
        stamp=profile[0].timestamp_utc+timedelta(seconds=(-1 if i%2 else 0))
        p2.append(tuple(WindObservation(stamp,x.station_id,x.height_agl_m,x.east_m_s,x.north_m_s) for x in profile))
    obs=make_observation_table(p2)
    q=quality_report(obs)
    assert len(q['height_quality'])==4
    assert q['timestamp_count']==5


def test_paired_days_and_chronological_holdout():
    obs=make_observation_table(synthetic_profiles())
    targets=build_targets(obs)
    pred,_=all_model_predictions(obs,targets)
    pred=direction_errors(pred)
    boot=paired_day_bootstrap(pred,seed=4,replicates=10)
    assert boot['day_blocks']==7
    assert set(boot['comparisons'])=={'power_alpha_heldout_day','log_z0_heldout_day'}
    forward=temporal_holdout(targets)
    assert forward['train_days'][-1] < forward['test_days'][0]
    assert forward['metrics']['power_alpha_train_past']['rmse_m_s']<1e-10


def test_missing_level_retains_same_comparison_support():
    obs=make_observation_table(synthetic_profiles(missing=True))
    pred,_=all_model_predictions(obs,build_targets(obs))
    prim=pred[pred.information_class=='10m_only']
    assert prim.groupby('model').size().nunique()==1
    quality=quality_report(obs)
    assert next(q for q in quality['height_quality'] if q['height_agl_m']==20.)['timestamps_without_level']==1


def test_direction_threshold_validation():
    obs=make_observation_table(synthetic_profiles())
    pred,_=all_model_predictions(obs,build_targets(obs))
    with pytest.raises(ValueError):direction_errors(pred,-1)


def test_full_month_runner_requires_unlimited_timestamp_conversion(tmp_path, monkeypatch):
    import experiments.run_cabauw_full_month_stage6 as wrapper
    seen={}
    def fake_stage5(netcdf, manifest, mapping, out, max_times):
        seen['max_times']=max_times
        out.mkdir(parents=True,exist_ok=True)
        return {'profiles':4464,'raw_sha256':'fixture_hash'}
    def fake_inventory(netcdf, out):
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text('{}')
    def fake_stage6(csv, meta, out, stage4_report, seed):
        return {'qa':{'timestamp_count':4464,'days':31},'figures':['one.png']}
    monkeypatch.setattr(wrapper,'stage5',fake_stage5)
    monkeypatch.setattr(wrapper,'inventory',fake_inventory)
    monkeypatch.setattr(wrapper,'stage6',fake_stage6)
    report=wrapper.execute(tmp_path/'input.nc',tmp_path/'manifest',tmp_path/'map',tmp_path/'result')
    assert seen['max_times'] is None
    assert report['stage6_profiles']==4464
    assert (tmp_path/'result/full_month_processing_summary.json').exists()


def test_native_metadata_inventory_never_guesses_flag_meanings(tmp_path):
    xr=pytest.importorskip('xarray')
    pytest.importorskip('scipy')
    import experiments.inspect_cabauw_quality_metadata as inspect
    ds=xr.Dataset({'F':(('time','z'),np.ones((2,2)),{'units':'m/s','long_name':'test speed'}),
                   'PF':(('time','z'),np.full((2,2),9),{'long_name':'unknown auxiliary'})},
                  coords={'time':np.arange(2),'z':np.array([10,20])})
    nc=tmp_path/'fixture.nc';ds.to_netcdf(nc,engine='scipy')
    data=inspect.run(nc,tmp_path/'inventory.json')
    assert data['status']=='raw_netcdf_metadata_inventory_not_quality_screening'
    assert data['variables']['PF']['attrs']['long_name']=='unknown auxiliary'
    assert 'warning' in data
