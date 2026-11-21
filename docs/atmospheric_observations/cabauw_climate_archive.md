# Batch 11 — descriptive meteorological climatology

## 6G.11 Matched-month comparison
Use only identical calendar months between 2025 and 2026. Compare medians of observed temperature, dew point and derived specific humidity at the nominal 10 m channel; report coverage and interquartile ranges for each source month. Difference = median(other year) − median(base year), not an estimate of a climate trend. The 90% coverage flag is an explicitly arbitrary screening convention and cannot rule out selective missingness. Visibility is treated as instrument-censored; no uncensored visibility median difference is claimed. No missing months are imputed.

## 6G.12 Historical archive
Inventory separates advertised months from locally present files. A blank inventory month is not proof that no observations were collected. The user-reported inventory contains 40 monthly filenames; the local collection at the start contains 19. The code reads all locally available months and records hashes, coverage and basic validity checks using the existing Stage 8/10 readers. Additional historical files are not required for the inventory analysis; historical measurement summaries remain absent until files are supplied. Instrument periods are grouped by documented configuration: before April 2010, April 2010–2013, 2014 onward. The categories are not a substitute for per-file calibration records. Do not estimate a multidecadal trend from these discontinuous data.

## 6G.13 Independent dataset acquisition catalogue
See `cabauw_independent_sources.md`. This is a source/access audit, not an assertion that independent data have been obtained. Restrict the study to descriptive near-surface temperature, humidity and observation quality. Do not silently harmonize unlike temporal averages, units, or instruments.

## Source documentation
- KNMI technical report TR-384, section 9: https://cdn.knmi.nl/knmi/pdf/bibliotheek/knmipubTR/TR384.pdf
- Ruisdael dataset description: https://ruisdael-catalog.citg.tudelft.nl/index.php?title=KNMI_meteorological_profiles_in_the_Cabauw_tower

## Running
Requires Stage 8 and Stage 10 scripts already installed in `experiments/`, and numpy, pandas, xarray, matplotlib and an appropriate NetCDF backend. Do not overwrite these older scripts. The inventory passed to the CLI is the list of provider filenames saved earlier. If that file was saved in a different directory, use its absolute path.

```bash
cd ~/projects/uav-payload-trajectory-project
source .venv/bin/activate
python -m pytest -q tests/test_cabauw_climate_archive.py
python experiments/cabauw_climate_archive.py --input-dir data/raw/knmi --inventory data/raw/knmi/cabauw_available_files.json --out results/atmospheric_observations/interannual_comparison
```

Outputs: historical_inventory.csv, monthly_surface_statistics.csv, matched_2025_2026.csv, summary.json, figures/ (five PNGs). Existing nonempty output directories are rejected. Original measurements are read-only. Synthetic tests are not evidence of real-data success.
