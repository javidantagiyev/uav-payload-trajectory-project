# Stage 5: Cabauw tower NetCDF layout correction

The previous Stage-5 mapping incorrectly assumed separate scalar-height variables such as `F010` and `D010`. The tower-profile source generally uses the 2D wind variables `F(time, z)` and `D(time, z)`, with observed heights represented by `z`. The 1D `F010` / `D010` variables are associated with the separate Cabauw surface meteorology product. Our previous synthetic tests copied the incorrect representation, so they did not catch the mismatch.

This patch preserves legacy mapping support, adds strict `profile`-mapping support, and makes the actual tower profile mapping the Stage-5 default. It verifies physical height coordinate units, selected heights, time and height dimensions, wind speed and meteorological FROM direction units, and available direction standard-name metadata. It does not silently interpolate missing heights or infer a new data convention. The user can inspect any NetCDF schema using `experiments/peek_knmi_netcdf.py` before processing.

The raw KNMI observation remains unchanged, as does its checksum manifest. No API credentials are needed to inspect or convert an already downloaded file.

Run:

```bash
FILE=$(find results/atmospheric_testbed/6g_stage5/raw -maxdepth 1 -name '*.nc' -print -quit)
python experiments/peek_knmi_netcdf.py --netcdf "$FILE"
python experiments/run_knmi_cabauw_stage5.py \
  --netcdf "$FILE" \
  --manifest results/atmospheric_testbed/6g_stage5/raw/knmi_download_manifest.json \
  --max-times 1008
```

If the actual file lacks `F`, `D`, `z`, or declares different units or dimensions, **stop** and inspect its native metadata instead of forcing a conversion. The code was verified with synthetic multidimensional NetCDF fixtures; only the WSL run against the downloaded provider file will establish end-to-end compatibility.

This corrects the data ingestion representation. It does not replace provider quality-control review, site stability measurements, or prove atmospheric-model accuracy.
