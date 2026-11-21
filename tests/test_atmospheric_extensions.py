"""independent equation and contract tests for 6g stage 3."""

import math
import numpy as np
import pytest

from src.physics.atmospheric_extensions import (
    RD, RV, businger_dyer_psi_m, moist_air_density,
    monin_obukhov_horizontal_wind, TabulatedWindProfile,
    bounded_gauss_markov_wind, meteorological_direction_or_none,
)
from src.physics.wind_model import log_law_wind


def _model(L=None, vertical=0.0, d=0.0, lo=0.5, hi=40):
    return monin_obukhov_horizontal_wind(
        (4, 2), 10, 0.03, (lo, hi), L, d, vertical)


@pytest.mark.parametrize('zeta', [0, 0.1, 0.5, 2])
def test_stable_psi_exact(zeta):
    assert businger_dyer_psi_m(zeta) == pytest.approx(-6*zeta)


def test_unstable_psi_reference_independent_expression():
    for zeta in (-0.01, -0.5, -2):
        x = (1-19.3*zeta)**.25
        expected = 2*math.log((1+x)/2) + math.log((1+x*x)/2) - 2*math.atan(x) + math.pi/2
        assert businger_dyer_psi_m(zeta) == pytest.approx(expected)
        assert expected > 0


@pytest.mark.parametrize('L', [None, 100., -100.])
def test_reference_normalization_and_separate_vertical(L):
    wind = _model(L, vertical=lambda t, p: 1.5 + .1*t)
    assert wind(4, (0, 0, 10)) == pytest.approx((4, 2, 1.9))
    assert wind(4, (0, 0, 20))[2] == pytest.approx(1.9)


def test_neutral_legacy_horizontal_agreement_and_vertical_difference():
    new = _model(None, vertical=1.0)
    old = log_law_wind((4, 2, 1), 10, .03)
    for z in [1, 10, 40]:
        assert new(0, (0, 0, z))[:2] == pytest.approx(old(0, (0, 0, z))[:2])
        assert new(0, (0, 0, z))[2] == 1.0
    assert new(0, (0, 0, 40))[2] != pytest.approx(old(0, (0, 0, 40))[2])


def test_psi_derivative_matches_businger_dyer_phi():
    # d/dz [ln(z/z0) - psi(z/L)] = phi_m(z/L)/z.
    for L in (100., -100.):
        z = 10.
        h = 1.e-4
        f = lambda zz: math.log(zz/.03)-businger_dyer_psi_m(zz/L)
        numeric = (f(z+h)-f(z-h))/(2*h)
        zeta = z/L
        phi = 1+6*zeta if L > 0 else (1-19.3*zeta)**(-.25)
        assert numeric == pytest.approx(phi/z, rel=2.e-7)


def test_stable_and_unstable_change_shear():
    neutral = _model()
    stable = _model(100)
    unstable = _model(-100)
    pos = (0, 0, 30)
    # normalized to the same 10m reference wind
    assert stable(0, pos)[0] > neutral(0, pos)[0] > unstable(0, pos)[0]


@pytest.mark.parametrize('invalid', [
    {'roughness_length': 0}, {'displacement_height': -1},
    {'reference_height': 0.1}, {'valid_height_range': (0.02, 10)},
    {'valid_height_range': (10, 5)}, {'valid_height_range': (20, 30)},
    {'obukhov_length': 0}, {'obukhov_length': float('nan')},
    {'reference_horizontal': (1, 2, 3)},
])
def test_domain_rejects_invalid_parameters(invalid):
    params = dict(reference_horizontal=(4, 2), reference_height=10,
                  roughness_length=.03, valid_height_range=(1, 40),
                  obukhov_length=None, displacement_height=0)
    params.update(invalid)
    with pytest.raises(ValueError):
        monin_obukhov_horizontal_wind(**params)


def test_height_below_above_domain_raises():
    f = _model()
    with pytest.raises(ValueError):
        f(0, (0, 0, .4))
    with pytest.raises(ValueError):
        f(0, (0, 0, 40.1))


def test_displacement_height_moves_effective_coordinates():
    f = _model(d=1, lo=2, hi=40)
    expected = math.log((20-1)/.03)/math.log((10-1)/.03)*4
    assert f(0, (0,0,20))[0] == pytest.approx(expected)


def test_invalid_vertical_callback_and_nan_position():
    f = _model(vertical=lambda t, p: float('nan'))
    with pytest.raises(ValueError):
        f(0, (0,0,10))
    with pytest.raises(ValueError):
        _model()(0, (0,0,float('nan')))


def test_ideal_moist_gas_law_and_isa_dry_limit():
    p = 101325
    t = 288.15
    dry = moist_air_density(p, t, 0)
    assert dry == pytest.approx(p / (RD*t))
    for q in [.001, .01, .02]:
        observed = moist_air_density(p,t,q)
        expected = p*((1-q)/RD + q/RV)/t
        assert observed == pytest.approx(expected)
        assert observed < dry
    assert moist_air_density(p,t,1) == pytest.approx(p/(RV*t))


@pytest.mark.parametrize('p,t,q', [(0,300,0), (100000,0,0), (100000,290,-.1),
                                 (100000,290,1.01), (float('inf'),290,0)])
def test_moist_atmosphere_rejects_invalid(p,t,q):
    with pytest.raises(ValueError):
        moist_air_density(p,t,q)


def test_tabulated_wind_interpolation_and_provenance():
    profile = TabulatedWindProfile((5, 10, 20), ((1,0,.2), (3,2,.3), (7,6,.5)),
                                   "synthetic", "illustrative-test-fixture")
    assert profile(0, (0,0,15)) == pytest.approx((5,4,.4))
    assert profile(100, (200,300,10)) == (3,2,.3)
    assert profile.info()['provenance'] == 'synthetic'
    with pytest.raises(ValueError):
        profile(0, (0,0,30))


@pytest.mark.parametrize('heights,winds,prov,source', [
    ((10,), ((1,2,3),), 'synthetic', 'x'),
    ((10,5), ((1,2,3),(3,2,1)), 'synthetic', 'x'),
    ((5,10), ((1,2,3),), 'synthetic', 'x'),
    ((5,10), ((1,2,3),(3,2,1)), 'measured', 'x'),
    ((5,10), ((1,2,3),(3,2,1)), 'observed', ''),
])
def test_tabulated_rejects_invalid(heights,winds,prov,source):
    with pytest.raises(ValueError):
        TabulatedWindProfile(heights, winds, prov, source)


def test_bounded_ar1_rejects_time_outside_and_is_seeded():
    f = bounded_gauss_markov_wind((1,0,0), (.1,.2,.05), 30., 10.,
                                  duration=2., step=.1, seed=51)
    g = bounded_gauss_markov_wind((1,0,0), (.1,.2,.05), 30., 10.,
                                  duration=2., step=.1, seed=51)
    h = bounded_gauss_markov_wind((1,0,0), (.1,.2,.05), 30., 10.,
                                  duration=2., step=.1, seed=52)
    for t in (0, .25, 1, 2):
        assert f(t, (0,0,10)) == g(t, (100,200,10))
    assert f(1,(0,0,10)) != h(1,(0,0,10))
    for t in (-.1, 2.01):
        with pytest.raises(ValueError):
            f(t, (0,0,10))
    assert f.model_info['spatial_turbulence'] is False


def test_calm_direction_defined_only_if_moving():
    assert meteorological_direction_or_none((0, 0)) is None
    assert meteorological_direction_or_none((1, 0)) == pytest.approx(270)
    assert meteorological_direction_or_none((0, 1)) == pytest.approx(180)
    assert meteorological_direction_or_none((-1, 0)) == pytest.approx(90)
    with pytest.raises(ValueError):
        meteorological_direction_or_none((1, 0), calm_threshold=-1)


def test_ar1_window_excludes_implicit_ceil_extension():
    f = bounded_gauss_markov_wind((0,0,0), .3, 30, 10, duration=1.01,
                                  step=.1, seed=3)
    f(1.01, (0,0,10))
    with pytest.raises(ValueError):
        f(1.02, (0,0,10))


def test_stage3_pipeline_creates_expected_outputs(tmp_path):
    from experiments.compare_atmospheric_extensions import run
    summary = run(tmp_path / "stage3", seed=10)
    assert summary["figure_count"] == 8
    assert summary["ar1_generated_samples"] == 3601
    assert summary["status"] == "offline_equation_comparisons_not_gazebo_or_field_validation"
    assert len(summary["csv_sha256"]) == 5
    assert summary["wind_30m_horizontal_m_s"]["stable_L_100m"] > summary["wind_30m_horizontal_m_s"]["neutral"]
    assert summary["wind_30m_horizontal_m_s"]["neutral"] > summary["wind_30m_horizontal_m_s"]["unstable_L_minus100m"]
    for name in summary["figure_names"]:
        assert (tmp_path / "stage3" / "figures" / name).exists()
