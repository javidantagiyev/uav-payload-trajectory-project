# Stage 7 — Native Cabauw observational data audit

## Scope and sources

This is a standalone descriptive meteorological and data-quality audit. It does not fit wind models, reconstruct operational wind fields, generate trajectories, or modify simulator physics. The raw observation file is not included. The original Stage 5 and Stage 6 outputs are left untouched.

Source: KNMI, Cabauw validated tower profiles, `cesar_tower_meteo_lb1_t10/v1.3`, CC BY 4.0. https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 . The provider describes manually validated ten-minute observations. The v1.3 release changed wind direction averaging and boom selection at 10 and 20 m, so avoid pooling versions without investigating comparability: https://developer.dataplatform.knmi.nl/deprecation-cesar-tower-meteo-lb1-t10-v1.2 .

The supplied October 2026 native metadata identifies F and D as mean wind speed and direction, PF and MF as maximum and minimum speed, SF and SD as speed and direction standard deviations. MF is explicitly not corrected. These are physical statistics rather than QC flags. Their native missing marker is -9999. TA, TD, Q and ZMA are air temperature, dew point, specific humidity and visibility, respectively. The archive of converted observations only contains six levels and horizontal wind components; the native file contains seven levels. Additional measured variables must be obtained from the original local file, not reconstructed from the converted CSV.

## Findings already reproduced from the full-month converted archive

- 4,464 timestamps; 26,769 finite converted observations out of 26,784 possible in the selected six-level product.
- 2,977 timestamps align with the ten-minute grid at printed-second resolution; 1,487 occur one second early. Nearest-grid rounding causes no collisions in the converted archive. This does not prove that rounding is correct. Native numeric time encoding and time bounds are the next evidence.
- Valid row counts: 10 m 4459; 20 m 4460; 40 m 4461; 80 m 4463; 140 m 4463; 200 m 4463.

## Run on the original file

From the repository root, after extracting the ZIP:

```bash
source .venv/bin/activate
python -m pytest -q tests/test_cabauw_native_audit.py
python experiments/audit_cabauw_native.py \
  --netcdf data/raw/knmi/cesar_tower_meteo_lb1_t10_v1.3_202610.nc \
  --sha256 97f6a73542473193e6d6ad7a8c08c59ebe832b1cd3e2706811926c854f16ec0f \
  --out results/atmospheric_observations/native_data_audit
```

Dependencies: NumPy, pandas, xarray, matplotlib, a compatible NetCDF backend. No API request or API key needed. Use a new empty output directory for subsequent runs. The raw file and earlier reports are never rewritten.

## Outputs

- `native_audit.json`: checksum, decoded and native clock information, time-bound diagnostics, actual height coordinate values, limitations.
- `variable_completeness.csv`: per-variable and per-height counts of missing/nonfinite values and basic range violations. Unknown units or dimensions are explicitly marked unsupported rather than interpreted.
- `timestamp_audit.csv`: native decoded time and nearest ten-minute grid offset, without applying any correction.
- `daily_thermodynamic_summary.csv`: count, median and quartiles for air temperature, dew point, humidity and visibility by date and measurement height; missing data not imputed.
- Up to four plots of these daily medians in native units.

## Interpretation gates

1. Confirm the time bounds and float encoding before correcting timestamps. Report any clock correction separately and retain the original times.
2. Native provider validation is not replaced by simplistic range checks. Review observation documentation and source instrument corrections; an absent flag variable is not evidence that every measurement is correct.
3. Ten-minute standard deviations and extrema do not reconstruct a high-frequency turbulence signal. No spectral inference is performed here.
4. Temperature and humidity observations describe local conditions; dry temperature gradients alone do not establish a flux-based Monin–Obukhov classification. Surface pressure and independently measured fluxes are not supplied in the uploaded metadata.
5. The output is descriptive, not a test of predictive skill or physical validation outside this site/month. Longer-term comparisons require explicit seasonal coverage and metadata compatibility.

Six tests passed with synthetic NetCDF fixtures in the package-building environment. No real native auxiliary data were available here for execution.
