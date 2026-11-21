# Stage 10 — descriptive seasonal thermodynamic climatology

## Source and scope

KNMI Cabauw validated non-gapfilled tower profiles, `cesar_tower_meteo_lb1_t10` v1.3, CC BY 4.0. Official source: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 . The provider publishes monthly files, and manual validation may delay availability. Do not substitute gapfilled or unvalidated products. Source filenames must follow the same convention as the verified October file, `cesar_tower_meteo_lb1_t10_v1.3_202610.nc`.

The default requested period is November 2025–October 2026 (12 months). The already downloaded October 2026 file can be reused. Download the other available months from the official dataset catalog into the same local raw directory; the package does not download files or require credentials. Missing requested months are explicitly reported. A month present in the inventory is not necessarily complete: expected, observed and missing interval counts are recorded separately. The input is assumed to be the stated provider product; hashes record the local bytes and are not authentication. Do not mix sources or product versions.

## Method

Uses the existing Stage 8 reader with its strict native unit, time and height checks. The normalized analysis grid is used only for interval accounting. Files with timestamps outside their stated calendar month or inconsistent heights are rejected. Native files are untouched. No gap filling or correction of individual observations is performed.

Monthly and seasonal outputs contain sample counts, medians, quartiles and coverage relative to the full requested calendar interval counts. Thermal-layer temperature differences use simultaneous valid pairs; thresholds 0, 0.1 and 0.5 K are descriptive, not uncertainty bounds. Visibility counts at 20 km retain the documented measurement ceiling. Specific humidity is derived and not independent of dew point. Seasonal statistics pool original observations, not monthly medians. DJF, MAM, JJA and SON denote calendar-month groups. In the default window November 2025 and September–October 2026 form a non-contiguous SON group; this is explicitly reported. Do not interpret it as a continuous autumn. A full group of three local files may still have missing observations.

This is a one-site descriptive seasonal comparison, not a long-term climate normal, an atmospheric-stability inference, a wind-model validation, or a predictive or simulation component.

## Run

Requires the installed Stage 8 `experiments/cabauw_thermodynamic_climatology.py` and its dependencies (numpy, pandas, xarray, netCDF4 or another appropriate backend, matplotlib; scipy and pytest for synthetic tests).

```bash
python -m pytest -q tests/test_cabauw_seasonal_climatology.py
python experiments/cabauw_seasonal_climatology.py \
  --input-dir data/raw/knmi \
  --start-month 2025-11 --end-month 2026-10 \
  --out results/atmospheric_observations/seasonal_climatology
```

Outputs: `seasonal_summary.json` (source hashes, coverage, season groups, limitations), monthly/seasonal statistics and thermal-layer difference CSV files, and five plots in `figures/`. Use an empty output directory for each run. Missing months appear as gaps in the plots. Synthetic tests check pooling, calendar mismatch, missing months, mismatched heights, missing input, figure generation, and output overwrite protection. Real twelve-month compatibility and results require the actual local files.
