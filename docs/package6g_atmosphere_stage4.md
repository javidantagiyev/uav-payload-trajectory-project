# Package 6G, Stage 4 — measured-profile validation infrastructure

**Current evidence status:** code and synthetic fixture verified. **No measured Cabauw or IGRA profile has yet been ingested.** The example figures are **not field validation**. This package does not change the legacy atmospheric APIs or connect profiles into Gazebo.

## Source-first rationale

A wind model that reproduces its own analytical equation is not independently validated. Measured, multi-level profiles let us test whether a specified family of wind functions approximates the atmospheric conditions actually observed at one site and time. Our comparison keeps wind reference speed at a single **measured 10 m level**, predicts other heights without fitting their values, quantifies vector/speed/direction discrepancies, and refuses out-of-domain extrapolation.

### Primary observation candidates

1. **KNMI Cabauw CESAR validated tower profiles, `cesar_tower_meteo_lb1_t10`, version `v1.3`**, 10-minute measurements of wind speed/direction, temperature, dew point and other atmospheric variables at tower levels up to 200 m. Dataset: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 . **Current version matters:** v1.2 was deprecated in 2025, and v1.3 changes some wind-direction averaging and boom selection at 10 m and 20 m: https://developer.dataplatform.knmi.nl/deprecation-cesar-tower-meteo-lb1-t10-v1.2 . The KNMI Open Data API requires an API key; keep credentials outside the repository. See https://dataplatform.knmi.nl/dataset/access/cesar-tower-meteo-lb1-t10-v1-3 .
2. **NOAA/NCEI Integrated Global Radiosonde Archive (IGRA), v2.2**, atmospheric soundings and wind measurements from multiple stations: https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive . Temporal/height coverage is irregular; soundings may be **insufficient** for evaluating a 10–40 m profile, and metadata/measurement practice can change. IGRA should be processed separately after matching station, observation time, altitude datum, and available levels.

**Source limitations:** Tower observations are affected by local site, mast, boom selection, and wind instrument characteristics. Even validated data do not validate an atmospheric model for all sites, seasons, weather regimes, or 500 m height. A tower site is a single-location measurement; no three-dimensional wind field or turbulence spectrum can be inferred from just ten-minute mean profiles.

## Equations / implementation map

- Meteorological **FROM** direction `theta` clockwise from true north and speed `S` → ENU **TO** components: `east = -S sin(theta)`, `north = -S cos(theta)`; `src/physics/atmospheric_observations.py:meteorological_from_to_enu`.
- Mean vector error at a height: `e_vector = sqrt((u_pred-u_obs)^2+(v_pred-v_obs)^2)`.
- Aggregate `vector_RMSE = sqrt(mean(e_vector^2))`, `vector_MAE = mean(e_vector)`; signed component biases use the original east/north differences; *speed MAE* compares speed magnitudes, so it can be small even with wrong wind direction.
- Direction error: circular signed difference of meteorological FROM bearings mapped to `[-180°,180°)`. Calm wind has undefined direction and is omitted from this statistic.
- Model baselines: `src/physics/wind_model.py:power_law_wind` with **fixed `1/7` exponent**; `log_law_wind` with externally specified `z0`; neutral Monin–Obukhov and exploratory stable/unstable candidates (`L=+100m` and `-100m` by default) from `atmospheric_extensions.py`. All candidates use the same **measured reference wind** and comparison height window; their parameters are **not fitted to held-out observations**.
- Interpolation baseline: one-level-out altitude interpolation predicts an interior observation from its neighboring **other** heights; the held-out height is removed before constructing its interpolation. Without bracketing points, it abstains. This prevents tautological zero-error evaluation of interpolated observations.
- Domain gate: similarity surface-layer models are assessed **only** inside a researcher-declared height window, default `10–40 m AGL` solely for the demonstration. This is **not a universal** validity limit, and still requires meteorological justification for a given dataset. We do not extrapolate to 500 m based on a 40 m example.
- Repeated-times dependence: reported bootstrap uncertainty resamples complete **UTC calendar days**. It is disabled when fewer than five days are present. This is an approximate resampling diagnostic, not proof of independent weather samples or physical accuracy.

## Running the built-in synthetic pipeline

From the existing SDP repository after extracting the Stage-4 ZIP **into the repository root**:

```bash
source .venv/bin/activate
python -m pytest -q tests
python experiments/validate_observed_wind_profiles.py
```

The default fixture (`data/examples/synthetic_wind_tower_6g4.csv`) is explicitly synthetic and does not contain KNMI measurements. Outputs appear in `results/atmospheric_testbed/6g_stage4/`: `holdout_residuals.csv`, `stage4_report.json`, and **six** graphs (including a surface-layer zoom). These examples only test the pipeline.

## Running with actual observational data

**Obtain a NetCDF observation file separately from KNMI** through the official dataset page. No KNMI file or API key is included here. Inspect the actual NetCDF variable names, dimensions, time format, physical units, quality flags, and missing-value conventions first. This package supplies a configurable converter, not a universal automatic NetCDF interpreter.

For example, for a verified downloaded monthly Cabauw NetCDF file (substitute the real path and **verified mapping**, dataset license, and URL):

```bash
python experiments/convert_tower_netcdf.py \
  --netcdf /path/to/verified_cabauw_month.nc \
  --mapping data/examples/knmi_cabauw_variable_mapping_example.json \
  --csv results/atmospheric_testbed/input/cabauw.csv \
  --metadata results/atmospheric_testbed/input/cabauw.metadata.json \
  --data-kind observed \
  --provider KNMI --dataset cesar_tower_meteo_lb1_t10 \
  --version v1.3 --station CABAUW \
  --source-url https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 \
  --license CC-BY-4.0

python experiments/validate_observed_wind_profiles.py \
  --csv results/atmospheric_testbed/input/cabauw.csv \
  --metadata results/atmospheric_testbed/input/cabauw.metadata.json \
  --out results/atmospheric_testbed/6g_stage4_cabauw
```

Optional conversion dependency: `python -m pip install xarray netcdf4` (or xarray with a working netCDF backend). The example mapping uses common CESAR `F010/D010` names; **verify the actual v1.3 file rather than assume these variables, dimension names, units, and direction semantics match**. The converter rejects ambiguous or incorrect unit strings instead of silently interpreting them. Missing/invalid wind samples are counted and omitted; users must inspect the resulting sampling pattern before interpreting residuals. The source metadata and SHA256 hashes are saved.

If the metadata state `data_kind=observed`, this represents the **data provider's claimed provenance**, not independently authenticated origin or physical validity. The report explicitly discloses this.

## Interpretation and next scientific gates

- With the synthetic fixture, the graphs and numeric errors show **pipeline behavior**, not atmospheric accuracy.
- With real observations, report model error by height, direction, time, and environmental regime; investigate observations and quality flags before making scientific claims.
- A fixed `L=±100m` is **exploratory**, not an estimate of atmospheric stability. To claim valid stability-conditioned modeling, obtain independently determined `L` (e.g., flux measurements), surface roughness/displacement/site metadata, and appropriately bounded observation windows.
- A static vertical tower cannot establish spatial turbulence coherence, urban wake effects, atmospheric boundary-layer depth, local three-dimensional wind, or external generalization. These require further measurements/models and separate tests.
- **Do not connect observational wind to Gazebo and declare validation solely because its output changes.** Validate the simulator's wind-force transfer independently and distinguish the simulator force model from the measured wind profile.

**Module inventory:** `atmospheric_observations.py` (strict contract, physics comparisons, statistics); `validate_observed_wind_profiles.py` (figures/CSV/report); `convert_tower_netcdf.py` (optional user-supplied file conversion); tests plus explicitly synthetic fixture and mapping example.
