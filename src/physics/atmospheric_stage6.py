"""observational wind-profile analysis with explicitly matched sensor information.

this evaluates atmospheric measurements, not UAV payload outcomes.
"""
from __future__ import annotations

from datetime import timezone
import math
import numpy as np
import pandas as pd

from src.physics.atmospheric_observations import load_profiles

TARGET_LEVELS = (20., 40.)
ALL_HEIGHTS = (10., 20., 40., 80., 140., 200.)
ALPHA_GRID = np.linspace(0., .6, 121)
Z0_GRID = np.geomspace(.001, .5, 121)
PRIMARY_MODELS = (
    "no_shear_10m", "power_1_7_fixed", "neutral_log_z0_003_fixed",
    "power_alpha_heldout_day", "log_z0_heldout_day",
)
EXTRA_MODELS = ("interpolation_extra_sensors", "linear_10_80_extra_sensors")


def make_observation_table(profiles):
    rows = []
    for profile in profiles:
        for p in profile:
            rows.append((p.timestamp_utc, p.station_id, p.height_agl_m,
                         float(p.east_m_s), float(p.north_m_s)))
    df = pd.DataFrame(rows, columns=["timestamp_utc", "station_id", "height_agl_m", "east", "north"])
    if df.empty:
        raise ValueError("no profiles")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["date_utc"] = df.timestamp_utc.dt.strftime("%Y-%m-%d")
    df["speed"] = np.hypot(df.east, df.north)
    df = df.sort_values(["timestamp_utc", "height_agl_m"]).reset_index(drop=True)
    return df


def build_targets(observation_table, ref_height=10., targets=TARGET_LEVELS):
    """use only the same-time 10 m vector to form primary candidate predictions."""
    base = observation_table[observation_table.height_agl_m == ref_height][
        ["timestamp_utc", "east", "north", "speed"]
    ].rename(columns={"east": "ref_east", "north": "ref_north", "speed": "ref_speed"})
    observed = observation_table[observation_table.height_agl_m.isin(targets)].copy()
    joined = observed.merge(base, on="timestamp_utc", how="inner", validate="many_to_one")
    if joined.empty:
        raise ValueError("no eligible same-time target/reference pairs")
    joined["ratio"] = joined.height_agl_m / float(ref_height)
    return joined.reset_index(drop=True)


def log_scale(z, zref, z0):
    if not (0 < z0 < min(z, zref)):
        raise ValueError("roughness must be positive and below measurement heights")
    return math.log(z/z0) / math.log(zref/z0)


def fixed_scale(model, z, zref=10.):
    if model == "no_shear_10m":
        return 1.
    if model == "power_1_7_fixed":
        return float(z/zref)**(1/7)
    if model == "neutral_log_z0_003_fixed":
        return log_scale(float(z), float(zref), .03)
    raise ValueError(f"unsupported primary fixed model {model}")


def _fit_parameter(df, grid, family, zref=10.):
    """grid search on train days only, minimizing 2-d component squared error."""
    if df.empty:
        raise ValueError("empty training set")
    heights = df.height_agl_m.to_numpy(float)
    ref = df[["ref_east", "ref_north"]].to_numpy(float)
    obs = df[["east", "north"]].to_numpy(float)
    if family == "power":
        scale = np.power((heights/zref)[None, :], grid[:, None])
    elif family == "log":
        scale = np.log(heights[None, :]/grid[:, None])/np.log(zref/grid[:, None])
    else:
        raise ValueError("unknown parameter family")
    diff = ref[None, :, :]*scale[:, :, None] - obs[None, :, :]
    loss = np.mean(np.sum(diff*diff, axis=2), axis=1)
    return float(grid[np.argmin(loss)])


def fit_daily_cv(targets, min_train_days=3):
    days = sorted(targets.date_utc.unique())
    if len(days) < min_train_days+1:
        raise ValueError("not enough distinct days for held-out-day validation")
    preds = []
    fitlog = []
    for day in days:
        train = targets[targets.date_utc != day]
        test = targets[targets.date_utc == day]
        if train.date_utc.nunique() < min_train_days:
            raise ValueError("insufficient training days")
        alpha = _fit_parameter(train, ALPHA_GRID, "power")
        z0 = _fit_parameter(train, Z0_GRID, "log")
        fitlog.append({"date_utc": day, "train_days": int(train.date_utc.nunique()),
                       "test_days": 1, "power_alpha": alpha, "log_roughness_m": z0})
        for model, scale in (
            ("power_alpha_heldout_day", np.power(test.ratio.to_numpy(), alpha)),
            ("log_z0_heldout_day", np.log(test.height_agl_m.to_numpy()/z0)/np.log(10./z0)),
        ):
            preds.append(_prediction_rows(test, model, scale, "10m_only", "heldout_day_cv"))
    return pd.concat(preds, ignore_index=True), pd.DataFrame(fitlog)


def _prediction_rows(targets, model, scale, information_class, protocol):
    x = targets[["timestamp_utc", "date_utc", "height_agl_m", "east", "north",
                 "ref_east", "ref_north", "ref_speed"]].copy()
    x["model"] = model
    x["information_class"] = information_class
    x["protocol"] = protocol
    x["predicted_east"] = x.ref_east.to_numpy()*np.asarray(scale)
    x["predicted_north"] = x.ref_north.to_numpy()*np.asarray(scale)
    return x


def extra_sensor_predictions(targets, observations):
    """hindsight baselines use additional same-time levels and are not primary comparisons."""
    by_time = {}
    for stamp, group in observations.groupby("timestamp_utc"):
        by_time[stamp] = {float(r.height_agl_m): (float(r.east), float(r.north))
                          for r in group.itertuples()}
    rows = []
    for r in targets.itertuples():
        heights = by_time[r.timestamp_utc]
        for name in EXTRA_MODELS:
            if name == "linear_10_80_extra_sensors":
                lo, hi = 10., 80.
                if lo not in heights or hi not in heights:
                    continue
            else:
                lower = [h for h in heights if h < r.height_agl_m]
                upper = [h for h in heights if h > r.height_agl_m]
                if not lower or not upper:
                    continue
                lo, hi = max(lower), min(upper)
            w = (r.height_agl_m-lo)/(hi-lo)
            vec = (1-w)*np.array(heights[lo])+w*np.array(heights[hi])
            x = {"timestamp_utc": r.timestamp_utc, "date_utc": r.date_utc,
                 "height_agl_m": r.height_agl_m, "east":r.east, "north":r.north,
                 "ref_east":r.ref_east,"ref_north":r.ref_north, "ref_speed":r.ref_speed,
                 "model":name, "information_class":"extra_simultaneous_height_sensors",
                 "protocol":"same_timestamp_interpolation_diagnostic",
                 "predicted_east":float(vec[0]), "predicted_north":float(vec[1])}
            rows.append(x)
    return pd.DataFrame(rows)


def all_model_predictions(obs, targets, min_train_days=3):
    choices = []
    for model in ("no_shear_10m", "power_1_7_fixed", "neutral_log_z0_003_fixed"):
        scales = np.array([fixed_scale(model, z) for z in targets.height_agl_m])
        choices.append(_prediction_rows(targets, model, scales, "10m_only", "fixed_before_test"))
    cv, fitted = fit_daily_cv(targets, min_train_days)
    choices.append(cv)
    choices.append(extra_sensor_predictions(targets, obs))
    predictions = pd.concat(choices, ignore_index=True)
    predictions["residual_east"] = predictions.predicted_east-predictions.east
    predictions["residual_north"] = predictions.predicted_north-predictions.north
    predictions["vector_error"] = np.hypot(predictions.residual_east, predictions.residual_north)
    predictions["observed_speed"] = np.hypot(predictions.east, predictions.north)
    predictions["predicted_speed"] = np.hypot(predictions.predicted_east, predictions.predicted_north)
    predictions["speed_error"] = predictions.predicted_speed-predictions.observed_speed
    return predictions, fitted


def circular_difference(a, b):
    return (a-b+180.)%360.-180.


def direction_errors(pred, threshold=2.):
    if threshold < 0:
        raise ValueError("direction threshold must be nonnegative")
    p = pred.copy()
    p["direction_evaluable"] = ((p.observed_speed >= threshold) &
                                 (p.predicted_speed >= threshold) &
                                 (p.ref_speed >= threshold) &
                                 (p.observed_speed > 0) & (p.predicted_speed > 0))
    obs_dir = np.rad2deg(np.arctan2(-p.east, -p.north)) % 360
    pred_dir = np.rad2deg(np.arctan2(-p.predicted_east, -p.predicted_north)) % 360
    p["direction_error_deg"] = np.where(p.direction_evaluable, circular_difference(pred_dir,obs_dir), np.nan)
    return p


def metrics(df):
    if len(df) == 0:
        return {"samples":0}
    err = df.vector_error.to_numpy(float)
    out={"samples":len(err), "rmse_m_s":float(np.sqrt(np.mean(err**2))),
         "mae_vector_m_s":float(np.mean(err)), "median_vector_error_m_s":float(np.median(err)),
         "p95_vector_error_m_s":float(np.quantile(err, .95)),
         "speed_mae_m_s":float(np.mean(np.abs(df.speed_error))),
         "direction_samples":int(df.direction_evaluable.sum())}
    values = df.direction_error_deg.dropna()
    out["mean_abs_direction_error_deg"] = float(np.abs(values).mean()) if len(values) else None
    return out


def grouped_metrics(pred, group_cols):
    rows=[]
    for keys, sub in pred.groupby(group_cols, dropna=False, sort=True, observed=True):
        if not isinstance(keys, tuple):
            keys=(keys,)
        rows.append({**dict(zip(group_cols, keys)), **metrics(sub)})
    return pd.DataFrame(rows)


def paired_day_bootstrap(pred, baseline="power_1_7_fixed", comparisons=("power_alpha_heldout_day","log_z0_heldout_day"),
                         seed=2026, replicates=1000):
    """paired block bootstrap by UTC day; blocks not independent site replication."""
    days=sorted(pred.date_utc.unique())
    if len(days)<5:
        return {"status":"insufficient_days", "day_blocks":len(days), "comparisons":{}}
    mse={}
    for model in (baseline,)+tuple(comparisons):
        d=pred[pred.model==model].groupby("date_utc").vector_error.apply(
            lambda v:(float(np.sum(v**2)), len(v)))
        if len(d)!=len(days):
            raise ValueError("paired bootstrap requires same days across models")
        mse[model] = np.array([d.loc[day] for day in days],dtype=float)
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(days),size=(replicates,len(days)))
    def bootstrap_rmse(model):
        dat=mse[model]
        return np.sqrt(dat[draws,0].sum(axis=1)/dat[draws,1].sum(axis=1))
    base=bootstrap_rmse(baseline)
    report={}
    for model in comparisons:
        diffs=bootstrap_rmse(model)-base
        report[model]={"point_delta_rmse_m_s": float(np.sqrt(mse[model][:,0].sum()/mse[model][:,1].sum()) -
                                                   np.sqrt(mse[baseline][:,0].sum()/mse[baseline][:,1].sum())),
                       "paired_utc_day_bootstrap_95pct_delta_rmse_m_s":list(map(float,np.quantile(diffs,[.025,.975])))}
    return {"status":"exploratory_paired_block_bootstrap", "day_blocks":len(days),
            "replicates":replicates, "baseline":baseline, "comparisons":report,
            "warning":"few days and temporal dependence; interval not a generalization or causal bound"}


def temporal_holdout(targets, first_fraction=.7):
    """fit on earlier UTC days, evaluate later days with no future observations in training."""
    days=sorted(targets.date_utc.unique())
    split=min(len(days)-1,max(3,int(len(days)*first_fraction)))
    if split >= len(days):
        raise ValueError("not enough distinct days")
    train=targets[targets.date_utc.isin(days[:split])]
    test=targets[targets.date_utc.isin(days[split:])]
    alpha=_fit_parameter(train, ALPHA_GRID, "power")
    z0=_fit_parameter(train, Z0_GRID, "log")
    out={"train_days": days[:split], "test_days": days[split:], "power_alpha":alpha,
         "log_roughness_m":z0, "metrics":{}}
    for model, scale in (
        ("no_shear_10m",np.ones(len(test))),
        ("power_1_7_fixed",np.power(test.ratio.to_numpy(),1/7)),
        ("neutral_log_z0_003_fixed",np.log(test.height_agl_m.to_numpy()/.03)/np.log(10./.03)),
        ("power_alpha_train_past",np.power(test.ratio.to_numpy(),alpha)),
        ("log_z0_train_past",np.log(test.height_agl_m.to_numpy()/z0)/np.log(10./z0)),
    ):
        pred=_prediction_rows(test,model,scale,"10m_only","train_earlier_days_evaluate_later_days")
        pred["vector_error"]=np.hypot(pred.predicted_east-pred.east,pred.predicted_north-pred.north)
        out["metrics"][model]={"samples":int(len(pred)),
                               "rmse_m_s":float(np.sqrt(np.mean(pred.vector_error**2)))}
    return out


def quality_report(obs, ref_height=10., calm_threshold=2.):
    stamps=sorted(obs.timestamp_utc.unique())
    interval=np.diff(pd.DatetimeIndex(stamps).asi8)/1e9
    levelrows=[]
    for z, sub in obs.groupby("height_agl_m"):
        levelrows.append({"height_agl_m":float(z), "observations":int(len(sub)),
                          "timestamps_without_level":int(len(stamps)-len(sub)),
                          "zero_speed":int((sub.speed==0).sum()),
                          "speed_below_threshold":int((sub.speed<calm_threshold).sum()),
                          "mean_speed_m_s":float(sub.speed.mean())})
    ref=obs[obs.height_agl_m==ref_height]
    daily=ref.groupby('date_utc').agg(ref_samples=('speed','size'),
                       reference_calm_count=('speed',lambda s:int((s<calm_threshold).sum())),
                       ref_mean_speed=('speed','mean')).reset_index()
    return {"timestamp_count":len(stamps),"start_utc":str(stamps[0]), "end_utc":str(stamps[-1]),
            "interval_median_s":float(np.median(interval)) if len(interval) else None,
            "interval_max_s":int(max(interval)) if len(interval) else None,
            "expected_cadence_s":600,
            "intervals_outside_600s_plus_minus_1s":int(np.sum(np.abs(interval-600)>1)),
            "observed_interval_counts_s":{str(round(float(v), 3)):int((interval==v).sum())
                                          for v in np.unique(interval)},
            "days":int(obs.date_utc.nunique()),"reference_calm_threshold_m_s":calm_threshold,
            "reference_calm_samples":int((ref.speed<calm_threshold).sum()),
            "zero_reference_samples":int((ref.speed==0).sum()),
            "height_quality":levelrows,"reference_daily":daily.to_dict(orient='records'),
            "quality_flags_checked":False,
            "native_boom_metadata_checked":False}


def reference_speed_bins(pred):
    out=pred.copy()
    out["ref_speed_bin"] = pd.cut(out.ref_speed, bins=[-1e-10,2.,4.,float('inf')],
                                   labels=["below_2", "2_to_4", "4_plus"], right=False)
    return out
