"""independent diagnostics for existing atmospheric and wind model contracts.

this module does not alter wind forcing, predict impacts, or validate real weather.
"""

from __future__ import annotations

import math

import numpy as np

from src.physics import atmosphere, wind_model


# rounded reference data from the 1976 standard atmosphere table at nmsu.
# pressures in pa, densities in kg/m3; not generated from our atmosphere module.
ISA_REFERENCE = (
    {"altitude_m": 0, "temperature_k": 288.15, "pressure_pa": 101325.0, "density_kg_m3": 1.2250},
    {"altitude_m": 1000, "temperature_k": 281.65, "pressure_pa": 89874.5705, "density_kg_m3": 1.1116},
    {"altitude_m": 2000, "temperature_k": 275.15, "pressure_pa": 79495.2155, "density_kg_m3": 1.0065},
)

ISA_REFERENCE_SOURCE = "https://atmos.nmsu.edu/planetary_datasets/earth_temppres.html"


def isa_reference_comparison():
    """compare against independently tabulated standard-atmosphere anchors."""
    rows = []
    for item in ISA_REFERENCE:
        h = item["altitude_m"]
        actual = {
            "temperature_k": atmosphere.temperature(h),
            "pressure_pa": atmosphere.pressure(h),
            "density_kg_m3": atmosphere.isa_density(h),
        }
        row = dict(item)
        for name, value in actual.items():
            row[f"code_{name}"] = value
            row[f"error_{name}"] = value - item[name]
        rows.append(row)
    return rows


def hydrostatic_balance(h, offset_m=0.5):
    """central-difference hydrostatic residual, dP/dh + rho*g, in pa/m."""
    if not offset_m > 0:
        raise ValueError("offset must be positive")
    derivative = (atmosphere.pressure(h + offset_m) -
                  atmosphere.pressure(h - offset_m)) / (2.0 * offset_m)
    expected = -atmosphere.isa_density(h) * atmosphere.G0
    return {"altitude_m": h, "dpressure_dheight_pa_m": derivative,
            "hydrostatic_expected_pa_m": expected,
            "residual_pa_m": derivative - expected}


def independent_power_factor(height_m, reference_m, exponent):
    if reference_m <= 0 or exponent < 0:
        raise ValueError("invalid power profile")
    return (max(height_m, wind_model.MINIMUM_PROFILE_HEIGHT) / reference_m) ** exponent


def independent_log_factor(height_m, reference_m, roughness_m):
    if roughness_m <= 0 or reference_m <= roughness_m:
        raise ValueError("invalid log profile")
    if height_m <= roughness_m:
        return 0.0
    return math.log(height_m / roughness_m) / math.log(reference_m / roughness_m)


def profile_comparison(heights_m, reference_wind=(4.0, 2.0, 1.0),
                       reference_height_m=10.0, exponent=1.0 / 7,
                       roughness_m=0.03):
    """compare source-code output with independent formulas and audit vertical scaling."""
    pw = wind_model.power_law_wind(reference_wind, reference_height_m, exponent)
    lw = wind_model.log_law_wind(reference_wind, reference_height_m, roughness_m)
    rows = []
    for height in heights_m:
        point = (0.0, 0.0, float(height))
        power = tuple(float(x) for x in pw(0.0, point))
        log = tuple(float(x) for x in lw(0.0, point))
        p_fac = independent_power_factor(height, reference_height_m, exponent)
        l_fac = independent_log_factor(height, reference_height_m, roughness_m)
        rows.append({"height_agl_m": float(height), "power_east_m_s": power[0],
                     "power_north_m_s": power[1], "power_up_m_s": power[2],
                     "log_east_m_s": log[0], "log_north_m_s": log[1],
                     "log_up_m_s": log[2],
                     "power_formula_max_abs_error_m_s": max(abs(power[i] - reference_wind[i]*p_fac) for i in range(3)),
                     "log_formula_max_abs_error_m_s": max(abs(log[i] - reference_wind[i]*l_fac) for i in range(3))})
    return rows


def ar1_coefficient(length_scale_m, airspeed_m_s, dt_s):
    if min(length_scale_m, airspeed_m_s, dt_s) <= 0:
        raise ValueError("length scale, airspeed, and step must be positive")
    return math.exp(-airspeed_m_s * dt_s / length_scale_m)


def ar1_theoretical_acf(a, lags):
    if not 0 <= a < 1:
        raise ValueError("ar1 coefficient must lie in [0,1)")
    return np.power(a, np.asarray(lags, dtype=float))


def ar1_sample_acf(series, lags):
    values = np.asarray(series, dtype=float)
    if values.ndim != 1 or not len(values):
        raise ValueError("expected a nonempty 1d series")
    lags = np.asarray(lags, dtype=int)
    if np.any(lags < 0) or np.any(lags >= len(values)):
        raise ValueError("lags must be within the series")
    centered = values - np.mean(values)
    denominator = float(np.dot(centered, centered))
    if denominator <= 0:
        raise ValueError("cannot estimate autocorrelation of constant data")
    return np.array([np.dot(centered[:len(values)-lag], centered[lag:]) /
                     denominator for lag in lags], dtype=float)


def ar1_theoretical_one_sided_psd(frequencies_hz, variance_m2_s2, a, dt_s):
    """one-sided discrete-time ar1 spectral density in (m/s)^2/hz.

    scipy.signal.welch(..., scaling='density', return_onesided=True) uses
    these units. frequencies must fall within [0, nyquist].
    """
    f = np.asarray(frequencies_hz, dtype=float)
    if dt_s <= 0 or variance_m2_s2 < 0 or not 0 <= a < 1:
        raise ValueError("invalid psd parameters")
    nyquist = 0.5 / dt_s
    if np.any(f < 0) or np.any(f > nyquist + 1e-10):
        raise ValueError("frequency is outside the nyquist band")
    denominator = 1 + a*a - 2*a*np.cos(2*math.pi*f*dt_s)
    two_sided = variance_m2_s2 * (1-a*a) * dt_s / denominator
    one_sided = 2*two_sided
    one_sided[np.isclose(f, 0.0, atol=1e-12) |
              np.isclose(f, nyquist, atol=1e-12)] *= 0.5
    return one_sided


def stochastic_diagnostics(intensity=(1.0, 0.6, 0.2), length_scale_m=40.0,
                           airspeed_m_s=12.0, duration_s=900.0, step_s=0.05,
                           seed=2026, max_lag_s=20.0):
    """diagnose the exact ar1 law used by turbulence_series, not dryden."""
    times, series = wind_model.turbulence_series(
        intensity, length_scale_m, airspeed_m_s, duration_s, step_s, seed)
    a = ar1_coefficient(length_scale_m, airspeed_m_s, step_s)
    lag_limit = min(len(times)-2, int(max_lag_s / step_s))
    lags = np.unique(np.linspace(0, lag_limit, 160, dtype=int))
    sample_acf = ar1_sample_acf(series[:, 0], lags)
    from scipy.signal import welch
    frequencies, empirical_psd = welch(series[:, 0], fs=1/step_s,
                                       nperseg=min(4096, len(times)),
                                       detrend="constant", scaling="density")
    theoretical_psd = ar1_theoretical_one_sided_psd(
        frequencies, float(intensity[0])**2, a, step_s)
    n = len(times)
    # approximate standard error of the sample mean for correlated ar1 noise.
    effective_n = n * (1-a)/(1+a)
    return {
        "times": times, "series": series, "lags_s": lags*step_s,
        "theoretical_acf": ar1_theoretical_acf(a, lags),
        "empirical_acf": sample_acf,
        "psd_frequency_hz": frequencies,
        "psd_sample": empirical_psd,
        "psd_ar1_theory": theoretical_psd,
        "summary": {
            "status": "mathematical_ar1_diagnostics_not_atmospheric_validation",
            "sample_count": n, "requested_duration_s": duration_s,
            "actual_last_sample_time_s": float(times[-1]),
            "step_s": step_s, "seed": int(seed),
            "ar1_coefficient": a,
            "correlation_timescale_s": length_scale_m / airspeed_m_s,
            "effective_sample_size_approx_mean": effective_n,
            "lag1_theoretical": a,
            "lag1_sample": float(ar1_sample_acf(series[:, 0], [1])[0]),
            "sample_mean_m_s": np.mean(series, axis=0).tolist(),
            "sample_std_m_s": np.std(series, axis=0, ddof=1).tolist(),
            "specified_std_m_s": [float(x) for x in intensity],
            "lag_acf_rmse": float(np.sqrt(np.mean((sample_acf -
                                                 ar1_theoretical_acf(a, lags))**2))),
            "dryden_spectrum_validated": False,
            "spatial_correlation_validated": False,
            "interpretation": "time-only stationary independent-axis gauss-markov model",
        },
    }


def model_contract_findings():
    """non-silent source-code limitations, not automatically failures."""
    zero = wind_model.wind_direction((0.0, 0.0, 0.0))
    power = wind_model.power_law_wind((4.0, 0.0, 1.0))(0.0, (0.0, 0.0, 100.0))
    logarithmic = wind_model.log_law_wind((4.0, 0.0, 1.0))(0.0, (0.0, 0.0, 100.0))
    field = wind_model.turbulent_wind((0.0, 0.0, 0.0), 1.0, 30.0,
                                      10.0, 1.0, step=0.1, seed=4)
    same_at_different_positions = (field(0.5, (0, 0, 5)) ==
                                   field(0.5, (100, 200, 300)))
    constant_after_end = field(2.0, (0, 0, 0)) == field(3.0, (0, 0, 0))
    return {
        "vertical_wind_scaled_by_horizontal_power_profile": power[2] != 1.0,
        "vertical_wind_scaled_by_horizontal_log_profile": logarithmic[2] != 1.0,
        "turbulence_identical_across_spatial_positions": same_at_different_positions,
        "turbulence_endpoint_clamped_beyond_generated_time": constant_after_end,
        "calm_wind_direction_returned_deg": zero,
        "calm_wind_direction_physically_defined": False,
        "notes": "observed source-code contract; no physical corrections applied",
    }
