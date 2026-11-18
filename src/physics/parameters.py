"""Validated parameters for the repository physics model (ENU, SI units)."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Body:
    mass_kg: float
    reference_area_m2: float
    drag_coefficient: float

    def __post_init__(self):
        if not np.isfinite(self.mass_kg) or self.mass_kg <= 0:
            raise ValueError("mass_kg must be positive and finite")
        if not np.isfinite(self.reference_area_m2) or self.reference_area_m2 < 0:
            raise ValueError("reference_area_m2 must be nonnegative and finite")
        if not np.isfinite(self.drag_coefficient) or self.drag_coefficient < 0:
            raise ValueError("drag_coefficient must be nonnegative and finite")


@dataclass(frozen=True)
class Atmosphere:
    density_kg_m3: float = 1.225
    wind_m_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gravity_m_s2: float = 9.81

    def __post_init__(self):
        if not np.isfinite(self.density_kg_m3) or self.density_kg_m3 < 0:
            raise ValueError("density_kg_m3 must be nonnegative and finite")
        if not np.isfinite(self.gravity_m_s2) or self.gravity_m_s2 <= 0:
            raise ValueError("gravity_m_s2 must be positive and finite")
        if np.asarray(self.wind_m_s).shape != (3,) or not np.all(np.isfinite(self.wind_m_s)):
            raise ValueError("wind_m_s must contain three finite numbers")


