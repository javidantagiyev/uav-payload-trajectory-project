# Stage 9 — descriptive meteorological measurement consistency

Requires the Stage 8 package (the Stage 8 reader is imported unchanged). Offline only; the source is never modified. Use the original monthly KNMI NetCDF with its recorded SHA-256. Output directory must not exist. Figures are saved under `figures/`.

## Evidence and interpretation

- KNMI, dataset `cesar_tower_meteo_lb1_t10` v1.3: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3
- Bosveld, F.C. (2020), KNMI TR-384, *The Cabauw In-situ Observational Program 2000 – Present: Instruments, Calibrations and Set-up*, https://cdn.knmi.nl/knmi/pdf/bibliotheek/knmipubTR/TR384.pdf . Sections 7.2 and 7.8 document a 20 km visibility range and maximum readings; sections 9.3–9.4 describe sensor accuracy and wetting-related high dew point; section 9.10 documents specific humidity derived from dew point and pressure, and the water/frost point convention. Instrument configuration may change; the technical report is not an independent October 2026 calibration certificate. Section 9.1 identifies the nominal 2 m temperature/humidity channel as measured at 1.5 m in the described configuration. We retain the NetCDF nominal coordinate.

Positive TD−TA values are flagged, not deleted or repaired. Thresholds 0, 0.1, 0.2, 0.5, and 1 K are descriptive sensitivity choices, not independently established uncertainty thresholds. Low recorded visibility is not proof of wetting. Specific humidity is not an independent humidity measurement. Visibility values at the published maximum are range-limited; do not extrapolate beyond it. The 72-hour figure covers the first 432 records (72 hours for a complete grid). Missing values are not filled. No prediction, stability fitting, or simulation integration.

## Reproduce

From repository root with Stage 8 installed:

```bash
python -m pytest -q tests/test_cabauw_measurement_consistency.py
python experiments/cabauw_measurement_consistency.py \
  --netcdf data/raw/knmi/cesar_tower_meteo_lb1_t10_v1.3_202610.nc \
  --sha256 97f6a73542473193e6d6ad7a8c08c59ebe832b1cd3e2706811926c854f16ec0f \
  --out results/atmospheric_observations/measurement_consistency
```

Five synthetic tests passed. Native October data not run here. CSV files include height/day threshold counts, positive-excess records, counts by recorded visibility class, visibility ceiling and low-visibility fractions, and paired missingness of derived humidity and dew point. Results are descriptive and do not establish causes for individual anomalous measurements.
