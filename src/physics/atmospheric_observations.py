"""Observed-profile data contract and leakage-aware wind-model verification.

No data retrieval, model fitting or physical validation is implied by this module.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math

import numpy as np

from src.physics.atmospheric_extensions import monin_obukhov_horizontal_wind
from src.physics.wind_model import power_law_wind, log_law_wind


REQUIRED_METADATA = (
    "data_kind", "provider", "dataset_id", "dataset_version", "source_url",
    "station_id", "height_datum", "time_basis", "wind_units", "data_license",
)
REQUIRED_COLUMNS = (
    "timestamp_utc", "station_id", "height_agl_m", "wind_east_m_s", "wind_north_m_s",
)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def meteorological_from_to_enu(speed_m_s, direction_from_deg):
    """Convert wind FROM bearing clockwise from north to east/north wind TO components."""
    speed = float(speed_m_s)
    angle = float(direction_from_deg)
    if not math.isfinite(speed) or speed < 0 or not math.isfinite(angle):
        raise ValueError("wind speed must be finite and nonnegative, bearing finite")
    a = math.radians(angle % 360)
    return (-speed*math.sin(a), -speed*math.cos(a))


def enu_to_met_from(east, north, calm_threshold=1e-6):
    if not all(math.isfinite(float(x)) for x in (east, north, calm_threshold)) or calm_threshold < 0:
        raise ValueError("nonfinite value or invalid calm threshold")
    if math.hypot(east, north) <= calm_threshold:
        return None
    return math.degrees(math.atan2(-east, -north)) % 360


def signed_circular_difference_deg(a, b):
    return (a-b+180) % 360 - 180


@dataclass(frozen=True)
class WindObservation:
    timestamp_utc: datetime
    station_id: str
    height_agl_m: float
    east_m_s: float
    north_m_s: float


def load_profiles(csv_path, metadata_path):
    """Read canonical UTC/AGL/ENU CSV, strictly rejecting missing or duplicate levels."""
    csv_path, metadata_path = Path(csv_path), Path(metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or any(not metadata.get(k) for k in REQUIRED_METADATA):
        raise ValueError("provenance metadata missing required nonempty fields")
    if metadata["data_kind"] not in ("observed", "synthetic", "reanalysis"):
        raise ValueError("data_kind must be observed, synthetic, or reanalysis")
    if metadata["height_datum"] != "AGL_m" or metadata["time_basis"] != "UTC_ISO8601" or metadata["wind_units"] != "ENU_m_s":
        raise ValueError("this parser accepts only explicit UTC/AGL/ENU SI data")
    result = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or any(name not in reader.fieldnames for name in REQUIRED_COLUMNS):
            raise ValueError("csv missing required columns")
        for i, row in enumerate(reader, 2):
            try:
                timestamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
                if timestamp.utcoffset() != timezone.utc.utcoffset(None):
                    raise ValueError("timestamps must have explicit UTC offset")
                timestamp = timestamp.astimezone(timezone.utc)
                station = row["station_id"].strip()
                if station != metadata["station_id"]:
                    raise ValueError("station does not match metadata")
                height = float(row["height_agl_m"])
                east = float(row["wind_east_m_s"])
                north = float(row["wind_north_m_s"])
                if not all(math.isfinite(v) for v in (height, east, north)) or height <= 0:
                    raise ValueError("height must be positive; data must be finite")
                item = WindObservation(timestamp, station, height, east, north)
                key = (station, timestamp)
                levels = result.setdefault(key, {})
                if height in levels:
                    raise ValueError("duplicate height at same station and timestamp")
                levels[height] = item
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid observation row {i}: {exc}") from exc
    if not result:
        raise ValueError("observation file is empty")
    profiles = []
    for key, levels in sorted(result.items()):
        profiles.append(tuple(levels[k] for k in sorted(levels)))
    return metadata, profiles


def _reference_profile(profile, reference_height_m):
    matches = [row for row in profile if abs(row.height_agl_m-reference_height_m) <= 1e-6]
    return matches[0] if len(matches) == 1 else None


def leave_one_level_out_enu(profile, height):
    """Predict a held-out interior level by interpolating adjacent OTHER measured levels."""
    others = [r for r in profile if abs(r.height_agl_m-height) > 1e-6]
    below = [r for r in others if r.height_agl_m < height]
    above = [r for r in others if r.height_agl_m > height]
    if not below or not above:
        return None
    a, b = max(below, key=lambda r:r.height_agl_m), min(above, key=lambda r:r.height_agl_m)
    f = (height-a.height_agl_m)/(b.height_agl_m-a.height_agl_m)
    return (a.east_m_s + f*(b.east_m_s-a.east_m_s),
            a.north_m_s + f*(b.north_m_s-a.north_m_s))


def compare_observation_profiles(profiles, reference_height_m=10, roughness_length_m=0.03,
                                 valid_height_range=(10, 40), model_lengths=(None, 100.0, -100.0)):
    """Evaluate declared surface-layer candidates and leave-one-level-out interpolation.

    This does NOT estimate L or roughness from held-out data. No extrapolation.
    """
    lo, hi = (float(x) for x in valid_height_range)
    if not (0 < lo <= reference_height_m <= hi):
        raise ValueError("invalid declared surface layer or reference height")
    if roughness_length_m <= 0 or roughness_length_m >= lo:
        raise ValueError("roughness must be positive and smaller than valid domain")
    if len(set(model_lengths)) != len(model_lengths):
        raise ValueError("duplicate L candidate")
    data = []
    reasons = {"missing_reference":0, "out_of_surface_domain":0,
               "at_reference":0, "missing_interpolation_bracket":0, "profiles":len(profiles)}
    for profile in profiles:
        ref = _reference_profile(profile, reference_height_m)
        if ref is None:
            reasons["missing_reference"] += 1
            continue
        models = {}
        for L in model_lengths:
            name = "neutral" if L is None else f"L_{L:+g}m_exploratory"
            models[name] = monin_obukhov_horizontal_wind(
                (ref.east_m_s, ref.north_m_s), reference_height_m,
                roughness_length_m, (lo, hi), obukhov_length=L)
        # Legacy candidate baselines are bounded by the same surface-layer gate.
        models["power_law_1_7_legacy"] = power_law_wind(
            (ref.east_m_s, ref.north_m_s, 0), reference_height_m, 1/7)
        models["legacy_log_neutral"] = log_law_wind(
            (ref.east_m_s, ref.north_m_s, 0), reference_height_m, roughness_length_m)
        for obs in profile:
            z = obs.height_agl_m
            if abs(z-reference_height_m) <= 1e-6:
                reasons["at_reference"] += 1
                continue
            if z < lo or z > hi:
                reasons["out_of_surface_domain"] += 1
                continue
            options = {name: f(0, (0, 0, z))[:2] for name, f in models.items()}
            loo = leave_one_level_out_enu(profile, z)
            if loo is not None:
                options["loo_tabulated"] = loo
            else:
                reasons["missing_interpolation_bracket"] += 1
            for model, predicted in options.items():
                e, n = float(predicted[0]), float(predicted[1])
                observed_speed = math.hypot(obs.east_m_s, obs.north_m_s)
                estimated_speed = math.hypot(e, n)
                observed_direction = enu_to_met_from(obs.east_m_s, obs.north_m_s)
                predicted_direction = enu_to_met_from(e, n)
                direction_error = (None if observed_direction is None or predicted_direction is None
                                   else signed_circular_difference_deg(predicted_direction, observed_direction))
                de, dn = e-obs.east_m_s, n-obs.north_m_s
                data.append({
                    "timestamp_utc":obs.timestamp_utc.isoformat(), "station_id":obs.station_id,
                    "date_utc":obs.timestamp_utc.date().isoformat(), "height_agl_m":z,
                    "model":model, "observed_east_m_s":obs.east_m_s,
                    "observed_north_m_s":obs.north_m_s, "predicted_east_m_s":e,
                    "predicted_north_m_s":n, "residual_east_m_s":de,
                    "residual_north_m_s":dn, "vector_error_m_s":math.hypot(de,dn),
                    "observed_speed_m_s":observed_speed, "predicted_speed_m_s":estimated_speed,
                    "speed_error_m_s":estimated_speed-observed_speed,
                    "direction_error_deg":direction_error,
                })
    return data, reasons


def summarize_errors(rows, bootstrap_replicates=500, seed=2026):
    """Block bootstrap by UTC DATE. Report no interval when fewer than 5 days exist."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["model"], []).append(row)
    rng = np.random.default_rng(seed)
    results = {}
    for model, sample in sorted(grouped.items()):
        err = np.asarray([r["vector_error_m_s"] for r in sample], dtype=float)
        dates = sorted(set(r["date_utc"] for r in sample))
        by_date = [np.array([r["vector_error_m_s"] for r in sample
                             if r["date_utc"] == date], dtype=float) for date in dates]
        ci = None
        if len(dates) >= 5 and bootstrap_replicates >= 1:
            boot = []
            for _ in range(bootstrap_replicates):
                chosen = rng.integers(len(dates), size=len(dates))
                combined = np.concatenate([by_date[i] for i in chosen])
                boot.append(np.sqrt(np.mean(combined**2)))
            ci = [float(x) for x in np.percentile(boot, [2.5, 97.5])]
        directional = [abs(r["direction_error_deg"]) for r in sample
                       if r["direction_error_deg"] is not None]
        results[model] = {
            "samples":len(sample), "utc_day_blocks":len(dates),
            "vector_rmse_m_s":float(np.sqrt(np.mean(err**2))),
            "vector_mae_m_s":float(np.mean(err)),
            "signed_east_bias_m_s":float(np.mean([r["residual_east_m_s"] for r in sample])),
            "signed_north_bias_m_s":float(np.mean([r["residual_north_m_s"] for r in sample])),
            "speed_mae_m_s":float(np.mean([abs(r["speed_error_m_s"]) for r in sample])),
            "absolute_direction_error_mean_deg":float(np.mean(directional)) if directional else None,
            "utc_day_block_bootstrap_vector_rmse_95pct_ci_m_s":ci,
            "ci_note":"unavailable: fewer than 5 distinct UTC days" if ci is None else
                      "approximate resampling interval, not independent measurement accuracy",
        }
    return results
