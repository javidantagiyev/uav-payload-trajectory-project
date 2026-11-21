# Package 6G Stage 6 — observed atmospheric profiles: diagnostics and fair model comparisons

This stage investigates **observed wind at Cabauw**. It is not a UAV trajectory evaluation, a validation at 500 m, nor a substitute for the raw provider's instrument-quality documentation.

## What this stage changes

Stage 5 compared neutral, stability-exploratory, power law, and a leave-one-height-out interpolation baseline. Its interpolation baseline accessed additional **simultaneous observations**, so the apparent accuracy advantage confounds model type with data availability. Stage 6 introduces a matching-information experimental protocol:

1. Every *primary* model may observe only the **10 m horizontal wind vector at the evaluated timestamp**. These models use no current-time measurements from 20, 40, 80, 140 or 200 m.
2. Compare the zero-shear baseline, fixed `alpha=1/7` power law, and fixed neutral log-law `z0=0.03 m` with an empirically calibrated power exponent and effective log roughness.
3. Fitting uses **other UTC dates only**, never the evaluated date. For chronology, report a separate experiment trained on the earlier dates and tested on later dates. Leave-one-day-out cross-validation is a transfer check **not a prospective prediction**, because its training set may include later days.
4. Two *secondary* models interpolate using **additional same-time height measurements** (`10/80 m` and leave-one-height-out brackets). They answer *what does additional vertical information buy?*, not *is interpolation a better physical law?*
5. Primary performance is measured on 20 m and 40 m levels only. Any 80–200 m values are used for observational context and, where explicitly labeled, the extra-sensor baseline. A 10–40 m gate here is an illustrative study restriction and **not proof of surface-layer validity**.
6. Directional errors are computed only when *reference*, *observed*, and *predicted* wind speeds all meet the declared threshold (default `2 m/s`). Vector errors keep all eligible observations, including calm conditions, to avoid selective removal of difficult cases.
7. Time plots use UTC timestamps rather than indexing adjacent heights as if they were successive times. Day-level bootstrap comparisons are paired across models; they are exploratory with seven days of data and **do not rerun model fitting in each bootstrap sample**.

## Equations and protocols

Let the horizontal wind measured at 10 m be the vector **u₁₀**. Candidate same-information vector extrapolations are:

- zero shear: **u(z)=u₁₀**;
- power law: **u(z)=u₁₀ (z/10)^α**, with `α=1/7` fixed or fitted using training days;
- neutral log-law: **u(z)=u₁₀ ln(z/z₀)/ln(10/z₀)**, with `z₀=0.03 m` fixed or fitted using training days.

The fitted `α` and `z₀` are **effective empirical parameters**. Estimating roughness from vertical tower winds does not measure the actual terrain roughness or atmospheric stability, because wind veer, stability, tower exposure, and other omitted processes also affect the fit.

For observed vector **oᵢ** and prediction **pᵢ**, vector RMSE is `sqrt(mean(||pᵢ-oᵢ||²))`. The paired daily block bootstrap resamples each UTC day as a whole and recomputes RMSE differences on matched height–timestamp observations.

Missing heights are excluded from **all** compared primary models equally. 10-minute time stamps may differ by ±1 second from nominal grid points owing to timestamp conversion / NetCDF representation; do not interpret these as data gaps without examining source time bounds. Native quality flags and instrument-boom selection remain an explicit evidence gap.

## External literature and data provenance

- KNMI Cabauw, validated 10-minute wind profiles: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 . Dataset v1.3 is manually validated and represents a single tower/site.
- KNMI v1.3 changes: https://developer.dataplatform.knmi.nl/deprecation-cesar-tower-meteo-lb1-t10-v1.2 . Updated 10/20 m boom selection and direction averaging make the native instrument conventions critical.
- Optis, Monahan & Bosveld (2015), *Wind Energy*, doi:10.1002/we.1883, documents sensitivity to roughness estimates and the limitations of Monin–Obukhov methods under stable stratification, using Cabauw observations: https://www.knmi.nl/kennis-en-datacentrum/publicatie/limitations-and-breakdown-of-monin-obukhov-similarity-theory-for-wind-profile-extrapolation-under-stable-stratification

This stage does **not** estimate Monin–Obukhov length from flux measurements, label day/night as observed stability, assign meanings to KNMI variables `PF/MF/SF/SD` without their native documentation, or validate any payload behavior.

## Run on your already converted Stage 5 seven-day CSV

```bash
python experiments/evaluate_cabauw_stage6.py \
  --csv results/atmospheric_testbed/6g_stage5/verified/cabauw_observations_enu.csv \
  --metadata results/atmospheric_testbed/6g_stage5/verified/cabauw_observations.metadata.json \
  --stage4-report results/atmospheric_testbed/6g_stage5/verified/comparison/stage4_report.json
```

Outputs under `results/atmospheric_testbed/6g_stage6/`:

- `stage6_report.json`: data integrity, QA, model scores, paired daily bootstrap, past-to-future holdout, model limitations.
- `matched_input_residuals.csv`: all prediction/outcome pairs and their information class.
- `model_metrics.csv`, `by_height.csv`, `by_day.csv`, `by_reference_speed.csv`: tabular statistics.
- `heldout_day_parameters.csv`: fitted α and log roughness for each left-out day.
- `figures/`: ten actual-time/height/regime/evaluation-quality figures.

## Run the entire October 2026 file, not merely seven days

The previous Stage 5 command used `--max-times 1008`. It selected seven days out of the October NetCDF file, which contains **4,464** timestamps. The wrapper below **does not impose a sample limit** and uses a separate destination so it does not destroy the seven-day results.

```bash
FILE=$(find results/atmospheric_testbed/6g_stage5/raw -maxdepth 1 -name '*.nc' -print -quit)
python experiments/run_cabauw_full_month_stage6.py \
  --netcdf "$FILE" \
  --manifest results/atmospheric_testbed/6g_stage5/raw/knmi_download_manifest.json
```

The full-month workflow also generates a **native-variable attribute inventory** (`native_variable_metadata.json`). If its metadata is insufficient to interpret KNMI quality semantics, mark the analysis conditional and examine the provider documentation before scientific publication. The full-month results are to be run on the user's WSL; they **were not** executed during this package's creation because the original NetCDF has not been provided here.

## Remaining scientific work

1. Verify original CF time bounds, native wind quality/selection fields and selected instrument booms with the KNMI documentation; never interpret zeros automatically as missing.
2. Complete full-month and multiple-season evaluations. Include robust blocked uncertainty and comparisons across weather regimes.
3. Acquire independent flux measurements if fitting physically meaningful Obukhov lengths; test direction veer and weak-wind behavior separately.
4. Add second-site measurements, independent atmospheric profiles, and spatial turbulence evidence before making cross-site or 500 m claims.
5. Maintain the distinction between observation-model agreement, simulator behavior, and real-world UAV validation.
