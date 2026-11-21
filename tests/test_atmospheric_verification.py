"""equation-level verification of existing atmospheric contracts."""

import json
import math

import numpy as np
import pytest
from scipy.integrate import trapezoid

from src.physics import atmosphere, atmospheric_verification as v, wind_model
from experiments.verify_atmospheric_models import run


def test_isa_published_reference_table():
    rows = v.isa_reference_comparison()
    assert len(rows) == 3
    assert max(abs(r["error_temperature_k"]) for r in rows) < 1e-10
    assert max(abs(r["error_pressure_pa"]) for r in rows) < 0.3
    assert max(abs(r["error_density_kg_m3"]) for r in rows) < 8e-5


@pytest.mark.parametrize("height", [0, 500, 1000, 2000, 5000])
def test_isa_hydrostatic_balance(height):
    row = v.hydrostatic_balance(height)
    assert abs(row["residual_pa_m"]) < 1e-3
    assert row["dpressure_dheight_pa_m"] < 0


def test_hydrostatic_bad_offset():
    with pytest.raises(ValueError):
        v.hydrostatic_balance(100, 0)


def test_density_altitude_datum():
    fn = atmosphere.density_function(ground_altitude=150)
    assert fn(350) == pytest.approx(atmosphere.isa_density(500))


@pytest.mark.parametrize("height", [0, 0.1, 1.0, 10., 37., 100.])
def test_power_independent_equation(height):
    wind = wind_model.power_law_wind((4., 2., 1.), 10., 1/7)
    factor = v.independent_power_factor(height, 10., 1/7)
    assert wind(2., (0., 0., height)) == pytest.approx((4*factor, 2*factor, factor))


@pytest.mark.parametrize("height", [0, 0.03, 0.1, 1.0, 10., 100.])
def test_log_independent_equation(height):
    wind = wind_model.log_law_wind((4., 2., 1.), 10., .03)
    factor = v.independent_log_factor(height, 10., .03)
    assert wind(0, (0, 0, height)) == pytest.approx((4*factor, 2*factor, factor))


def test_power_invalid_reference():
    with pytest.raises(ValueError):
        v.independent_power_factor(10, 0, 1/7)


def test_log_invalid_roughness():
    with pytest.raises(ValueError):
        v.independent_log_factor(10, 10, 0)


def test_both_profiles_match_reference():
    for model in (wind_model.power_law_wind((4, 2, 1)),
                  wind_model.log_law_wind((4, 2, 1))):
        assert model(0, (0, 0, 10)) == pytest.approx((4, 2, 1))


def test_layered_wind_is_linear_and_clamped():
    field = wind_model.layered_wind([0, 20, 50], [(0, 0, 0), (4, 2, 1), (8, 0, 1)])
    assert field(0, (0, 0, 10)) == pytest.approx((2, 1, .5))
    assert field(0, (0, 0, -20)) == (0, 0, 0)
    assert field(0, (0, 0, 100)) == (8, 0, 1)


def test_gust_on_and_off_and_smooth_boundaries():
    g = wind_model.discrete_gust((0, 0, 0), (3, 0, 0), 1., 4.)
    w = lambda t: g(t, (0, 0, 10))[0]
    assert w(0) == 0
    assert w(1) == pytest.approx(0)
    assert w(3) == pytest.approx(3)
    assert w(5) == pytest.approx(0)
    assert w(6) == 0
    dt = 1e-4
    assert abs((w(1+dt) - w(1))/dt) < 1e-3
    assert abs((w(5) - w(5-dt))/dt) < 1e-3


def test_ar1_coefficient():
    a = v.ar1_coefficient(40, 12, 0.05)
    assert a == pytest.approx(math.exp(-0.015))


@pytest.mark.parametrize("invalid", [(0, 10, .1), (10, 0, .1), (10, 10, 0)])
def test_ar1_invalid_parameters(invalid):
    with pytest.raises(ValueError):
        v.ar1_coefficient(*invalid)


def test_ar1_theoretical_autocorrelation():
    assert v.ar1_theoretical_acf(.5, [0, 1, 2, 3]).tolist() == pytest.approx([1, .5, .25, .125])


def test_ar1_invalid_acf_coefficient():
    with pytest.raises(ValueError):
        v.ar1_theoretical_acf(1.0, [1])


def test_sample_acf_lag_zero():
    sample = np.array([1, 2, 3, 4, 5], dtype=float)
    assert v.ar1_sample_acf(sample, [0])[0] == pytest.approx(1)


def test_sample_acf_invalid_lag():
    with pytest.raises(ValueError):
        v.ar1_sample_acf(np.arange(20), [20])


def test_sample_acf_constant_rejected():
    with pytest.raises(ValueError):
        v.ar1_sample_acf(np.ones(50), [1])


def test_ar1_psd_integrates_to_variance():
    dt = .05
    fs = 1/dt
    a = .96
    variance = 1.44
    frequencies = np.linspace(0, fs/2, 100001)
    psd = v.ar1_theoretical_one_sided_psd(frequencies, variance, a, dt)
    assert trapezoid(psd, frequencies) == pytest.approx(variance, rel=0.001)
    assert np.all(psd >= 0)


def test_ar1_psd_is_not_white_for_correlated_process():
    psd = v.ar1_theoretical_one_sided_psd(np.array([.1, 4.9]), 1, .95, .1)
    assert psd[0] > 20 * psd[1]


def test_ar1_psd_invalid_frequency():
    with pytest.raises(ValueError):
        v.ar1_theoretical_one_sided_psd(np.array([11.]), 1., .9, .05)


def test_stochastic_model_reproducibility_and_summary():
    first = v.stochastic_diagnostics(duration_s=45, step_s=.05, seed=9)
    second = v.stochastic_diagnostics(duration_s=45, step_s=.05, seed=9)
    other = v.stochastic_diagnostics(duration_s=45, step_s=.05, seed=10)
    assert np.array_equal(first["series"], second["series"])
    assert not np.array_equal(first["series"], other["series"])
    assert first["summary"]["dryden_spectrum_validated"] is False
    assert first["summary"]["effective_sample_size_approx_mean"] < first["summary"]["sample_count"]


def test_contract_findings_are_exposed_not_fixed():
    flags = v.model_contract_findings()
    assert flags["vertical_wind_scaled_by_horizontal_power_profile"]
    assert flags["vertical_wind_scaled_by_horizontal_log_profile"]
    assert flags["turbulence_identical_across_spatial_positions"]
    assert flags["turbulence_endpoint_clamped_beyond_generated_time"]
    assert flags["calm_wind_direction_physically_defined"] is False


def test_pipeline_creates_9_figures_and_csv(tmp_path):
    summary = run(tmp_path / "report", duration_s=12, step_s=.05, seed=2026)
    assert summary["figures_created"] == 9
    assert summary["maximum_isa_pressure_abs_error_pa"] < .3
    assert summary["maximum_hydrostatic_residual_pa_m"] < .001
    assert summary["maximum_power_formula_error_m_s"] < 1e-12
    assert summary["maximum_log_formula_error_m_s"] < 1e-12
    assert (tmp_path / "report" / "ar1_autocorrelation.csv").is_file()
    assert (tmp_path / "report" / "ar1_spectrum.csv").is_file()
    assert json.loads((tmp_path / "report" / "atmospheric_verification.json").read_text())["figures_created"] == 9
