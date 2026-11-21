"""Explicitly bounded atmospheric models for independent verification studies.

These models do not modify the legacy wind API or the Gazebo wind plugin.
"""

from dataclasses import dataclass
import math

import numpy as np

from src.physics.wind_model import turbulence_series

RD = 287.05  # j/(kg k), same dry-air constant as atmosphere.py
RV = 461.5  # j/(kg k), water-vapor gas constant


def _finite_number(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vector(value, length, name):
    try:
        vector = tuple(_finite_number(x, name) for x in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain {length} finite values") from exc
    if len(vector) != length:
        raise ValueError(f"{name} must contain {length} finite values")
    return vector


def businger_dyer_psi_m(zeta):
    """Integrated momentum correction from ESSD 2023 Appendix A, Eq. A1.

    Stable: psi=-6*zeta. Unstable: x=(1-19.3*zeta)**0.25 and
    psi=2ln((1+x)/2)+ln((1+x*x)/2)-2atan(x)+pi/2.
    The empirical coefficients are formulation-specific, not universal.
    """
    zeta = _finite_number(zeta, "zeta")
    if zeta >= 0:
        return -6.0 * zeta
    x = (1.0 - 19.3 * zeta) ** 0.25
    return (2 * math.log((1 + x) / 2)
            + math.log((1 + x*x) / 2)
            - 2 * math.atan(x) + math.pi / 2)


def meteorological_direction_or_none(horizontal, calm_threshold=1e-9):
    """Meteorological from-direction in degrees, or None for calm horizontal wind."""
    east, north = _vector(horizontal, 2, "horizontal")
    threshold = _finite_number(calm_threshold, "calm_threshold")
    if threshold < 0:
        raise ValueError("calm_threshold must not be negative")
    if math.hypot(east, north) <= threshold:
        return None
    return math.degrees(math.atan2(-east, -north)) % 360.0


def moist_air_density(pressure_pa, temperature_k, specific_humidity):
    """Ideal binary gas-mixture density at measured p, T, q (kg/kg moist air).

    Tv=T/[1-(1-Rd/Rv)*q], rho=p/(Rd*Tv). Does not derive a
    pressure/temperature/humidity profile or model condensation.
    """
    p = _finite_number(pressure_pa, "pressure_pa")
    t = _finite_number(temperature_k, "temperature_k")
    q = _finite_number(specific_humidity, "specific_humidity")
    if p <= 0 or t <= 0 or not 0 <= q <= 1:
        raise ValueError("require pressure>0, temperature>0 and 0<=q<=1")
    return p * ((1.0 - q)/RD + q/RV) / t


def _wind_vertical(vertical, t, position):
    result = vertical(t, position) if callable(vertical) else vertical
    return _finite_number(result, "vertical_wind")


def monin_obukhov_horizontal_wind(reference_horizontal, reference_height,
                                  roughness_length, valid_height_range,
                                  obukhov_length=None, displacement_height=0.0,
                                  vertical_wind=0.0):
    """Near-surface ENU wind with Businger-Dyer momentum correction.

    Horizontal wind assumes a fixed horizontal direction and stationary,
    horizontally homogeneous mean flow. Vertical wind is an independent
    input, NEVER scaled by the horizontal similarity equation.

    Heights are AGL (m). valid_height_range=(lo, hi) is explicitly provided
    by the researcher; this function cannot infer a physically valid depth.
    obukhov_length=None is neutral; positive is stable, negative unstable.
    The computation raises outside the declared height range.
    """
    east, north = _vector(reference_horizontal, 2, "reference_horizontal")
    zr = _finite_number(reference_height, "reference_height")
    z0 = _finite_number(roughness_length, "roughness_length")
    d = _finite_number(displacement_height, "displacement_height")
    lo, hi = _vector(valid_height_range, 2, "valid_height_range")
    if z0 <= 0 or d < 0 or lo <= d + z0 or lo >= hi or not lo <= zr <= hi:
        raise ValueError("invalid roughness, displacement or declared height domain")
    if obukhov_length is not None:
        L = _finite_number(obukhov_length, "obukhov_length")
        if L == 0:
            raise ValueError("obukhov_length cannot be zero")
    else:
        L = None
    if not callable(vertical_wind):
        _finite_number(vertical_wind, "vertical_wind")

    def shape(z):
        effective = z - d
        if effective <= z0:
            raise ValueError("height must exceed displacement plus roughness")
        log_term = math.log(effective/z0)
        if L is None:
            return log_term
        return (log_term - businger_dyer_psi_m(effective/L)
                + businger_dyer_psi_m(z0/L))

    denominator = shape(zr)
    if denominator <= 0:
        raise ValueError("reference wind normalization is nonpositive")

    # A model can be invalid even if the reference point normalizes well.
    if shape(lo) <= 0 or shape(hi) <= 0:
        raise ValueError("profile has nonpositive normalization inside declared domain")

    def wind(t, position):
        pos = _vector(position, 3, "position")
        z = pos[2]
        if not lo <= z <= hi:
            raise ValueError("height outside explicitly declared validity range")
        factor = shape(z) / denominator
        return (east*factor, north*factor, _wind_vertical(vertical_wind, t, pos))

    wind.model_info = {
        "model": "businger_dyer_surface_layer", "reference_height_agl_m": zr,
        "roughness_length_m": z0, "displacement_height_m": d,
        "obukhov_length_m": L, "valid_height_range_agl_m": [lo, hi],
        "vertical_wind_separate": True,
        "spatially_homogeneous_horizontal_mean": True,
        "physical_validation": False,
    }
    return wind


@dataclass(frozen=True)
class TabulatedWindProfile:
    """Altitude-indexed ENU table, with explicit data provenance and no extrapolation."""
    heights_agl_m: tuple
    winds_enu_m_s: tuple
    provenance: str
    source_id: str

    def __post_init__(self):
        heights = tuple(_finite_number(x, "height") for x in self.heights_agl_m)
        winds = tuple(_vector(x, 3, "wind") for x in self.winds_enu_m_s)
        if len(heights) < 2 or len(heights) != len(winds):
            raise ValueError("need at least two height/wind rows of equal length")
        if any(a >= b for a, b in zip(heights, heights[1:])):
            raise ValueError("heights must be strictly increasing")
        if self.provenance not in ("synthetic", "observed", "reanalysis"):
            raise ValueError("provenance must be synthetic, observed, or reanalysis")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must identify the data source")
        object.__setattr__(self, "heights_agl_m", heights)
        object.__setattr__(self, "winds_enu_m_s", winds)

    def __call__(self, t, position):
        z = _vector(position, 3, "position")[2]
        if z < self.heights_agl_m[0] or z > self.heights_agl_m[-1]:
            raise ValueError("tabulated profile cannot be extrapolated")
        return tuple(float(np.interp(z, self.heights_agl_m,
                                     [w[j] for w in self.winds_enu_m_s]))
                     for j in range(3))

    def info(self):
        return {"model": "tabulated_enu_linear_interpolation",
                "provenance": self.provenance, "source_id": self.source_id,
                "height_range_agl_m": [self.heights_agl_m[0], self.heights_agl_m[-1]],
                "extrapolation": "raise", "temporal_variation": "none",
                "physical_validation": False}


def bounded_gauss_markov_wind(base_wind, intensity, length_scale, airspeed,
                               duration, step=0.05, seed=2026):
    """Time-only AR(1) fluctuation; raises outside generated time extent.

    This is not a spatial turbulence field and not a Dryden spectrum.
    """
    from src.physics.wind_model import base_wind_value

    duration = _finite_number(duration, "duration")
    times, series = turbulence_series(intensity, length_scale, airspeed,
                                      duration, step, seed)
    # Validate static base now, even if no sample is requested.
    if not callable(base_wind):
        base_wind = _vector(base_wind, 3, "base_wind")

    def wind(t, position):
        tm = _finite_number(t, "t")
        pos = _vector(position, 3, "position")
        if not times[0] <= tm <= duration:
            raise ValueError("requested time is outside stochastic series")
        base = _vector(base_wind_value(base_wind, tm, pos), 3, "base_wind")
        return tuple(float(base[j] + np.interp(tm, times, series[:, j]))
                     for j in range(3))

    wind.model_info = {
        "model": "time_only_ar1_gauss_markov", "duration_s": duration,
        "step_s": step, "seed": seed, "spatial_turbulence": False,
        "dryden_validated": False, "out_of_range": "raise",
    }
    return wind
