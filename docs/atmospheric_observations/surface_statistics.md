# Surface climatology: observation and statistical sensitivity audit (17–19)

Standalone descriptive analysis of 2025 surface air temperature and dew point. No wind, vertical-profile model, prediction, or flight calculation.

## Reproduce

Python 3.10+, numpy, pandas, matplotlib; pytest for tests. Extract the archive into its own directory. From that directory:

```
python -m pytest -q tests
python surface_statistics.py --summary /path/to/monthly_surface_comparison.csv --dwd-dir /path/to/raw_dwd --out ./results
```

`--dwd-dir` is optional for the monthly summary audit. It expects the original DWD archives `10minutenwerte_TU_01975_20200101_20251231_hist.zip` and `10minutenwerte_TU_03015_20200101_20251231_hist.zip`. Existing output directories are rejected; use a new name for reruns. If processing fails after creating an output directory, treat the partial directory as incomplete. No data are downloaded or modified. Source SHA-256 hashes are recorded, not independently authenticated.

## Stage 17 — daily temporal variability

DWD surface air temperature and dew point only. Keep the full 2025 UTC 10-minute grid; missing values remain NaN. A daily median is reported if at least 130 of 144 observations exist (90% rounded upward). Compute Pearson correlation between valid daily median pairs at lags 1, 2, 3, 7, and 14 days, with pair counts. Calendar gaps are not compressed. Report raw and calendar-month-centered series separately. Centering by the observed monthly daily-median mean reduces annual seasonality but does not guarantee stationarity, and can itself alter correlations. These are descriptive pairwise correlations rather than the conventional full-series ACF. Cabauw daily observations are not available to this script; no claim about Cabauw daily correlations.

## Stage 18 — missingness and measurement limitations

Validate the 72 existing monthly summary rows, counts and quantile ordering. Record expected, observed, valid, missing and valid fraction. For DWD raw records, calculate exact finite-sample median bounds over all possible missing values without imputation. For expected N, observed n, missing m=N-n, sorted observed values x indexed from zero, central ranks r0=floor((N-1)/2), r1=floor(N/2). Each central order statistic has lower bound x[r-m] if r>=m (otherwise -infinity) and upper bound x[r] if r<n (otherwise +infinity). Average the central bounds for the conventional median. Bounds are conditional on valid observations being held fixed. For the derived monthly summary without raw values, only check whether both extreme central ranks lie within the conservative observed IQR rank limits (assumes linear empirical quantiles used in the earlier summaries). This is not an uncertainty interval around the median estimated from an independent population. Missingness may be systematic, and even a finite bound does not establish representativeness. DWD QN is a record-level quality-control process code, not a measurement-error estimate; QN=3 is automatic control and correction. DWD dew point is derived from temperature and relative humidity, not an independent sensor check. Cabauw and DWD differ in nominal measurement configuration and temporal averaging. No calibration uncertainty can be inferred numerically from these summaries.

## Stage 19 — sensitivity

For each pair of sites and each variable, retain months where both sites pass the specified coverage threshold (75%, 90%, 95%, 99%). Report included months and arithmetic mean of differences between monthly medians, weighting each retained month equally. At 90%, omit each eligible month once and recalculate. These are descriptive sensitivity diagnostics, not confidence intervals or estimates of annual median differences. Changing thresholds changes both data coverage and the represented months. No trend, significance, or causal claim is justified by a single annual cycle. No bootstrap confidence interval is asserted; a defensible population and sampling design must be specified before inferential uncertainty can be assigned.

## Outputs

* Always: summary.json, monthly_missingness.csv, coverage_sensitivity.csv, leave_one_month_out.csv; four figures in figures/.
* With DWD archives: daily_medians.csv, daily_lag_correlations.csv, median_missingness_bounds.csv; four extra figures in figures/. No interpolated observations.

## Verification

Six automated tests: median bounds (odd/even/empty cases), preservation of time gaps, constant-series behavior, daily coverage screen, DWD input parsing and station identity, and coverage sensitivity. A separate synthetic full-year two-station integration run produced eight figures and 1,460 daily variable/site rows. Synthetic raw archives were not compared against real monthly values; they exercise the workflow only. Actual monthly summary analysis completed on user-provided data; actual raw DWD execution remains pending. The script does not audit equivalence of raw DWD files to previously derived monthly summaries.

## References

* NIST/SEMATECH e-Handbook, Autocorrelation: https://www.itl.nist.gov/div898/handbook/eda/section3/eda35c.htm
* DWD CDC 10-minute air temperature product description: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf
* Source monthly summary: user-provided Batch 12 CSV; its hash appears in the output manifest.
