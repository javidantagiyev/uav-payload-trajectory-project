# Meteorological Data Acquisition

## Data providers

- Royal Netherlands Meteorological Institute (KNMI)
- German Meteorological Service (DWD)

## Local data storage

Original observation datasets are stored in:

- data/raw/knmi/
- data/raw/dwd/

Raw datasets and authentication credentials are excluded
from version control.

## Authentication

The KNMI API key must be supplied through the
KNMI_API_KEY environment variable.

API keys must not be embedded in source files.

## Data utilities

- fetch_knmi_cabauw.py: Dataset acquisition.
- inspect_cabauw_quality_metadata.py: Native metadata inspection.
- peek_knmi_netcdf.py: NetCDF structure inspection.

## Research integrity

Original measurements, provider metadata and source checksums
should be preserved. Measurement quality flags should not be
interpreted without documented provider definitions.
