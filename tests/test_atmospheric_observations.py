"""stage 4 data contract and leakage-aware observational comparison."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import math

import numpy as np
import pytest

from src.physics.atmospheric_observations import (
    meteorological_from_to_enu, enu_to_met_from, signed_circular_difference_deg,
    load_profiles, compare_observation_profiles, leave_one_level_out_enu,
    summarize_errors, WindObservation,
)
from experiments.validate_observed_wind_profiles import run

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/"data/examples/synthetic_wind_tower_6g4.csv"
META = ROOT/"data/examples/synthetic_wind_tower_6g4.metadata.json"


def test_conversion_north_from():
    assert meteorological_from_to_enu(3, 0) == pytest.approx((0,-3))


def test_conversion_east_from():
    assert meteorological_from_to_enu(3, 90) == pytest.approx((-3,0))


def test_conversion_roundtrip():
    for angle in (0,45,90,179,270,359):
        u,v=meteorological_from_to_enu(4,angle)
        assert signed_circular_difference_deg(enu_to_met_from(u,v),angle) == pytest.approx(0,abs=1e-10)


def test_meteorological_calm_none():
    assert enu_to_met_from(0,0) is None


def test_circular_wrap():
    assert signed_circular_difference_deg(359,1)==-2
    assert signed_circular_difference_deg(1,359)==2


@pytest.mark.parametrize("v,angle", [(-1,0), (float('nan'),0), (2,float('inf'))])
def test_conversion_reject_bad(v,angle):
    with pytest.raises(ValueError):meteorological_from_to_enu(v,angle)


def test_load_fixture_count():
    meta, profiles = load_profiles(DATA, META)
    assert meta["data_kind"] == "synthetic"
    assert len(profiles)==24
    assert all(len(p)==7 for p in profiles)


def test_timestamp_is_utc():
    _, profiles=load_profiles(DATA,META)
    assert all(p[0].timestamp_utc.tzinfo==timezone.utc for p in profiles)


def test_profile_sorted():
    _, profiles=load_profiles(DATA,META)
    assert [x.height_agl_m for x in profiles[0]] == [10,20,30,40,80,140,200]


def test_no_out_of_surface_domain_evaluated():
    _,profiles=load_profiles(DATA,META)
    rows,reasons=compare_observation_profiles(profiles)
    assert rows and all(10<=r['height_agl_m']<=40 for r in rows)
    assert reasons['out_of_surface_domain']==24*3


def test_ref_never_evaluated():
    _,profiles=load_profiles(DATA,META)
    rows,reasons=compare_observation_profiles(profiles)
    assert all(r['height_agl_m']!=10 for r in rows)
    assert reasons['at_reference']==24


def test_loo_has_no_self_leakage():
    t=datetime(2026,11,1,tzinfo=timezone.utc)
    profile=[WindObservation(t,'x',z,e,0) for z,e in [(10,1),(20,200),(30,3)]]
    assert leave_one_level_out_enu(profile,20) == pytest.approx((2,0))
    assert leave_one_level_out_enu(profile,10) is None
    assert leave_one_level_out_enu(profile,30) is None


def test_loo_models_separately_reported():
    _,profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles)
    assert set(r['model'] for r in rows)=={
        'neutral','L_+100m_exploratory','L_-100m_exploratory','loo_tabulated',
        'power_law_1_7_legacy','legacy_log_neutral'}


def test_reproducible_bootstrap():
    _,profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles)
    assert summarize_errors(rows,100,2026) == summarize_errors(rows,100,2026)


def test_block_count_8():
    _,profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles)
    summary=summarize_errors(rows,10)
    assert all(s['utc_day_blocks']==8 for s in summary.values())
    assert all(len(s['utc_day_block_bootstrap_vector_rmse_95pct_ci_m_s'])==2 for s in summary.values())


def test_ci_absent_with_one_day():
    _,profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles[:1])
    assert all(s['utc_day_block_bootstrap_vector_rmse_95pct_ci_m_s'] is None
               for s in summarize_errors(rows).values())


def test_reject_invalid_reference():
    _,profiles=load_profiles(DATA,META)
    with pytest.raises(ValueError):compare_observation_profiles(profiles,reference_height_m=50,
                                                                valid_height_range=(10,40))


def test_missing_reference_excluded():
    _,profiles=load_profiles(DATA,META)
    rows,reasons=compare_observation_profiles([tuple(x for x in profiles[0]
                                                if x.height_agl_m!=10)])
    assert not rows
    assert reasons['missing_reference']==1


def test_file_metadata_requires_datum(tmp_path):
    data=json.loads(META.read_text());data['height_datum']='AMSL_m'
    bad=tmp_path/'bad.json';bad.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='UTC/AGL/ENU'):
        load_profiles(DATA,bad)


def test_file_metadata_requires_source(tmp_path):
    data=json.loads(META.read_text());data['source_url']=''
    bad=tmp_path/'bad.json';bad.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='metadata'):load_profiles(DATA,bad)


def test_file_rejects_duplicate_level(tmp_path):
    lines=DATA.read_text().splitlines()
    bad=tmp_path/'bad.csv'
    bad.write_text('\n'.join(lines+[lines[1]])+'\n')
    with pytest.raises(ValueError,match='duplicate'):load_profiles(bad,META)


def test_file_rejects_missing_timezone(tmp_path):
    bad=tmp_path/'bad.csv'
    lines=DATA.read_text().splitlines()
    lines[1]=lines[1].replace('Z,',',')
    bad.write_text('\n'.join(lines)+'\n')
    with pytest.raises(ValueError,match='UTC'):load_profiles(bad,META)


def test_file_rejects_bad_station(tmp_path):
    bad=tmp_path/'bad.csv'
    lines=DATA.read_text().splitlines()
    lines[1]=lines[1].replace('synthetic_cabauw_like','wrong_station')
    bad.write_text('\n'.join(lines)+'\n')
    with pytest.raises(ValueError,match='station'):load_profiles(bad,META)


def test_full_runner_outputs_declared_synthetic(tmp_path):
    report=run(DATA,META,tmp_path,seed=2026)
    assert report['status']=='synthetic_or_reanalysis_profile_comparison_not_field_validation'
    assert report['profile_count']==24
    assert report['source_identity_not_independently_authenticated']
    assert len(report['figures'])==6
    assert (tmp_path/'stage4_report.json').exists()
    assert (tmp_path/'holdout_residuals.csv').exists()


def test_no_silent_calm_direction():
    _, profiles=load_profiles(DATA,META)
    assert enu_to_met_from(1e-7,0,calm_threshold=1e-6) is None


def test_no_model_uses_500m():
    _, profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles,valid_height_range=(10,40))
    assert max(r['height_agl_m'] for r in rows)==40


def test_vector_error_consistency():
    _,profiles=load_profiles(DATA,META)
    rows,_=compare_observation_profiles(profiles)
    for r in rows[:30]:
        assert r['vector_error_m_s']==pytest.approx(math.hypot(
            r['residual_east_m_s'],r['residual_north_m_s']))


def test_synthetic_fixture_has_only_synthetic_label():
    meta=json.loads(META.read_text())
    assert meta['data_kind']=='synthetic'
    assert 'NOT KNMI DATA' in meta['notes']
