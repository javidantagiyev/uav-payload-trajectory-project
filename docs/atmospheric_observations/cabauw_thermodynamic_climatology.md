# Stage 8: Observational thermodynamic climatology

Standalone meteorological analysis, using the original Cabauw native NetCDF. No forecast, wind model, physical simulation, or UAV integration. Requires NumPy, Pandas, Xarray, a NetCDF backend and Matplotlib. Test dependency: pytest and SciPy (synthetic fixture writer).

Source: KNMI, *Meteo profiles — validated tower profiles of wind, dew point, temperature and visibility at 10 minute interval at Cabauw*, v1.3, CC BY 4.0. https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3

## Method

- Read TA, TD (K), Q (g/kg) and ZMA (m). Require dimensions time and z and explicit units. Missing values are decoded with Xarray. Reject only basic impossibilities; this is not instrument QC. Preserve native times, and store the independent nearest-ten-minute UTC coordinate for descriptive grouping. Reject time offsets greater than 0.5 s and collisions. Missing intervals remain gaps.
- Compute simultaneous upper-minus-lower air temperature differences for adjacent measured heights and the lowest/highest pair. Count positive differences per valid pair, with sensitivity checks at 0, 0.1 and 0.5 K. These thresholds are descriptive, not validated instrument error bounds. Do not equate a positive temperature difference with a complete dynamical stability diagnosis or assume uniform temperature between sensors.
- Count consecutive qualifying ten-minute means; missing observations or intervals break runs. Mark runs censored at data edges and gaps. Nominal duration is the number of occupied intervals times ten minutes; it is not a measurement of continuous inversion duration at finer scales.
- Summarize observed temperature, dew point, specific humidity, visibility and dew-point depression (TA minus TD) by UTC hour, using medians and quartiles with sample counts. Count TD greater than TA as an audit diagnostic without deleting such observations.
- Count values exactly at 20,000 m and above per height. A pile-up at a value is not independent proof of an instrument ceiling. No censoring correction is made.
- Plot actual measurement heights, not interpolated profiles; missing time slots are masked. All reporting is descriptive and conditional on provider measurement quality.

## Run

```bash
python -m pytest -q tests/test_cabauw_thermodynamic_climatology.py
python experiments/cabauw_thermodynamic_climatology.py \
  --netcdf data/raw/knmi/cesar_tower_meteo_lb1_t10_v1.3_202610.nc \
  --sha256 97f6a73542473193e6d6ad7a8c08c59ebe832b1cd3e2706811926c854f16ec0f \
  --out results/atmospheric_observations/monthly_climatology
```

The output directory must be empty. The optional expected hash pins the source to a previously audited file. For other months supply their correct independently recorded hash. The original file is not changed.

## Output

`climatology_summary.json`, `inversion_summary.csv`, `inversion_events.csv`, `daily_temperature_difference.csv`, `diurnal_summary.csv`, `visibility_ceiling_diagnostic.csv`, `time_mapping.csv`, nine descriptive PNG figures. The figure time axis is UTC. The 72 h zoom is preselected at the start of the record to avoid selecting an impressive-looking event after examining data.

## Evidence status

Synthetic fixture tests verify implementation behavior. Real-data execution remains to be performed on the local original NetCDF. This is a single-site, single-period descriptive study and does not validate atmospheric simulations or predictive models.
