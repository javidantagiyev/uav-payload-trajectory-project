# Batch 12 — Descriptive surface meteorology, 2025

This additive, standalone analysis compares monthly observed air temperature and dew-point distributions at Cabauw, Hamburg-Fuhlsbuettel and Lindenberg. No wind, predictive modelling, simulation or release calculations are included.

## Sources and methodology

- DWD historical 10-minute air temperature dataset: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/historical/
- DWD product description (v24.03): https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf
- KNMI Cabauw: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 ; input is the existing Stage 10 monthly CSV, not raw observations. Preserve upstream provenance separately.
- KNMI instrument documentation: https://cdn.knmi.nl/knmi/pdf/bibliotheek/knmipubTR/TR384.pdf

DWD timestamps are interpreted as UTC; the 2025 observations are selected, station IDs and ten-minute grid checked, and missing sentinel -999 removed. Monthly denominators are calendar days times 144. Cabauw nominal 2 m TA and TD summaries are converted from K to degrees Celsius. Nominal near-surface heights, averaging/instantaneous measurement semantics, site exposure and derived dew point differ across providers. No individual timestamps are matched between sites; monthly distributions are compared descriptively. QN counts describe provider procedures, not individual measurement uncertainties. A 90% coverage screen is a convention, not proof of unbiased sampling. IQR intervals are distribution summaries, not confidence intervals.

Stage 16 only consolidates the already computed Cabauw temperature-difference summaries at the existing 0.5 K threshold and flags coverage. No independent tall-tower comparison, stability inference or profile reconstruction is supported by these sources.

## Run from repository root

Dependencies: Python 3.10+, numpy, pandas, matplotlib; pytest for tests.

```bash
cd ~/projects/uav-payload-trajectory-project
source .venv/bin/activate
python -m pytest -q tests/test_surface_climate_comparison.py
mkdir -p data/raw/dwd
base=https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/historical
for id in 01975 03015; do
  name=10minutenwerte_TU_${id}_20200101_20251231_hist.zip
  dest=data/raw/dwd/$name
  curl -fL --retry 3 "$base/$name" -o "$dest.part" && unzip -tq "$dest.part" && mv "$dest.part" "$dest" || break
done
python experiments/surface_climate_comparison.py \
  --stage10 results/atmospheric_observations/seasonal_climatology \
  --dwd-dir data/raw/dwd \
  --out results/atmospheric_observations/geographical_comparison
```

Existing output directories are protected. Keep downloaded archives intact, including instrument metadata. Actual DWD execution is pending. Five synthetic tests and a separate integration check using Stage 10 summaries and synthetic DWD archives passed during package construction.
