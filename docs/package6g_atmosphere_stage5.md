# Package 6G — Stage 5: Official Cabauw data acquisition and observed-profile evaluation

## Evidence status

**No real observations were downloaded in the package-building environment.** The network there could not resolve KNMI's API host. Code and synthetic NetCDF test fixtures were verified; **real atmospheric-model performance remains unmeasured until you run the official-data workflow.** The tests do not establish which model performs better in actual weather.

## Verified source and rationale

KNMI publishes the validated CESAR Cabauw tower dataset **`cesar_tower_meteo_lb1_t10/v1.3`**, 10-minute measured profiles including wind speed and direction, with wind instruments at multiple heights to 200 m. Files are issued monthly. Website: https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3 . License CC BY 4.0. Dataset updates are manual and can lag real time. Version 1.3 changes wind-direction averaging and boom selection at 10 and 20 m relative to v1.2: https://developer.dataplatform.knmi.nl/deprecation-cesar-tower-meteo-lb1-t10-v1.2 .

The official API requires a key and uses `Authorization` headers. KNMI publishes a **shared anonymous key valid until August 1, 2027** at https://developer.dataplatform.knmi.nl/open-data-api . The downloader includes that **public shared key** as a fallback. For more reliable access, create a registered key on KNMI's Developer Portal, then export it as `KNMI_API_KEY` locally. **Never commit personal API keys**. The downloader logs no credential or signed temporary download URL; it records only the API endpoint, filename, byte size, SHA-256, and retrieval time.

## Install and run from existing repo (Ubuntu WSL)

```bash
cd ~/projects/uav-payload-trajectory-project
unzip -o SDP_Package6G_Stage5_Cabauw_Real_Data_Pipeline.zip
source .venv/bin/activate
python -m pytest -q tests
```

1. List the latest validated monthly files:

```bash
python experiments/fetch_knmi_cabauw.py --list-only
```

2. Download **one** latest monthly NetCDF and write `knmi_download_manifest.json`:

```bash
python experiments/fetch_knmi_cabauw.py
```

Default output folder: `results/atmospheric_testbed/6g_stage5/raw/`. The downloader deliberately refuses to overwrite a previously retrieved file or manifest. For a second monthly file, supply a **different** `--out` directory. For a specific older monthly filename, use `--filename <exact_name_from_knmi_browser>`, or `--month YYYY-MM` only when the month is among the newest files returned by the listing.

3. Run the **actual observed-data pipeline**, substituting the filename printed by step 2:

```bash
python experiments/run_knmi_cabauw_stage5.py \
  --netcdf results/atmospheric_testbed/6g_stage5/raw/<ACTUAL_MONTHLY_FILENAME>.nc \
  --manifest results/atmospheric_testbed/6g_stage5/raw/knmi_download_manifest.json \
  --max-times 1008
```

`--max-times 1008` evaluates the first seven days of 10-minute samples, if present. That is a useful first experiment with time-correlated data; after examining the source QC and schema, rerun without `--max-times` for the full month (use a different `--out` to retain the seven-day output). The selected `10–40 m` domain and roughness parameter `z0=0.03 m` are **illustrative** until independently justified at this site.

The script first checks raw file SHA-256 against the KNMI download manifest, then NetCDF dimensions, variable names, UTC-decodable time, six expected vertical wind speed/direction variable pairs, and units. It converts meteorological FROM bearings to ENU wind TO components, checks invalid directions (`0–360°` only), and passes the observed CSV to Stage-4's held-out wind-profile comparison. If any contract is violated, **stop and inspect** the file. Do not rename variables or remove checks merely to force conversion.

Expected outputs (inside `results/atmospheric_testbed/6g_stage5/verified/`):

- `netcdf_schema_inspection.json`: detected variables, measured height levels, first/last UTC time, unit contracts, candidate QC variables, missing-data diagnostics.
- `cabauw_observations_enu.csv` and `.metadata.json`: processed observations and raw file/source hashes.
- `comparison/stage4_report.json`, `comparison/holdout_residuals.csv`, and six figures: speed, vector, direction, altitude and temporal residual summaries.
- `stage5_summary.json`: model metrics and explicit evidence/interpretation limits.

## What the experiment can and cannot establish

- It compares specified **near-surface mean wind-profile formulas** against actual **10-minute mean tower observations** under externally assumed parameters. No model parameters are fitted to held-out levels. It is legitimate to report the conditional error statistics if the source and units are verified.
- KNMI's manual validation reduces some observational problems, but **the raw NetCDF native quality flags and site/instrument metadata still need inspection**. We do not assert every converted row is physically perfect. In particular, v1.3's changed 10/20 m boom and averaging must be reported for any cross-version comparison.
- Fixed `L=±100 m` are **exploratory atmospheres**, not measured stability classes. Independent heat/momentum fluxes would be needed to estimate stability. Likewise, `z0=0.03 m` is a hypothesis, not a measured site roughness.
- A 200 m tower **does not validate a 500 m wind field**. The observed mean profile also does not validate 3D gusts, spatial turbulence coherence, Dryden spectra, aerodynamic forces, or Gazebo physics.
- Measurements within the same day and neighboring timestamps are correlated; UTC-day bootstrap gives only approximate uncertainty intervals, not independent replication.
- Download verification uses KNMI API/manifest paths and SHA-256 checks, **not independent cryptographic authentication of the provider data**. Keep the original downloaded file as the immutable reference.

## Fix from Stage 4

`experiments/convert_tower_netcdf.py` now rejects invalid meteorological directions outside 0–360 degrees. Previously, it only rejected nonfinite angles. The rest of the Stage-4 conversion API is unchanged. This is why the archive intentionally includes that **one replacement** rather than being wholly add-only.

## Work after ingesting data

Inspect missingness and quality metadata, validate wind direction convention with the KNMI provider documentation, stratify by measured wind speed and direction, expand cross-month generalization, integrate independent stability observations, and only then consider a measured-wind forcing interface to Gazebo. Keep observational model comparison separate from physics engine validation.
