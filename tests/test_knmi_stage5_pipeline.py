"""Offline tests for KNMI retrieval and strictly gated observation conversion."""

from pathlib import Path
import hashlib
import json
import sys
import io

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from fetch_knmi_cabauw import (select_filename, list_files, get_download_url,
                               stream_file, FILE_NAME, DATASET)
from inspect_knmi_cabauw import inspect_file


class FakeResponse:
    def __init__(self, content):
        self.buffer = io.BytesIO(content)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.buffer.close()
    def read(self, n=-1):
        return self.buffer.read(n)


def fake_opener(request, timeout=30):
    url = request.full_url
    if url.endswith("/url"):
        payload = {"temporaryDownloadUrl": "https://example.org/month.nc"}
        return FakeResponse(json.dumps(payload).encode())
    if "?" in url and url.split("?", 1)[0].endswith("/files"):
        return FakeResponse(json.dumps({"files": [
            {"filename":"cesar_tower_meteo_lb1_t10_v1.3_202401.nc"},
            {"filename":"cesar_tower_meteo_lb1_t10_v1.3_202402.nc"}]}).encode())
    if url == "https://example.org/month.nc":
        return FakeResponse(b"CDF\001" + b"a" * 100)
    raise AssertionError(f"unexpected url {url}")


def test_file_selection_month_latest_and_reject_invalid():
    records = [{"filename":"cesar_tower_meteo_lb1_t10_v1.3_202401.nc"},
               {"filename":"cesar_tower_meteo_lb1_t10_v1.3_202402.nc"},
               {"filename":"some_other_file.zip"}]
    assert select_filename(records).endswith("202402.nc")
    assert select_filename(records,requested_month="2024-01").endswith("202401.nc")
    with pytest.raises(ValueError):
        select_filename(records,requested_month="2024-03")
    with pytest.raises(ValueError):
        select_filename(records,requested_filename="../../bad.nc")
    assert not FILE_NAME.fullmatch("not_cabauw.nc")


def test_mocked_knmi_api_retrieval(tmp_path):
    records = list_files("public", opener=fake_opener)
    name = select_filename(records["files"])
    assert name.endswith("202402.nc")
    url = get_download_url(name, "public", opener=fake_opener)
    out = tmp_path / name
    info = stream_file(url,out,opener=fake_opener)
    assert info["size_bytes"] == 104
    assert info["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert not (tmp_path/(name+".part")).exists()


def test_reject_non_https_download_url():
    def bad(request, timeout=45):
        return FakeResponse(json.dumps({"temporaryDownloadUrl":"http://example.com/test.nc"}).encode())
    with pytest.raises(ValueError):
        get_download_url("cesar_tower_meteo_lb1_t10_v1.3_202401.nc", "anonymous",opener=bad)


def _make_tower(path, swap_units=False):
    xr=pytest.importorskip("xarray")
    pytest.importorskip("scipy")
    timestamps=np.arange("2024-06-01T00:00", "2024-06-01T01:00", dtype="datetime64[10m]").astype("datetime64[ns]")
    coords={"time":timestamps}
    variables={}
    for z in (10,20,40,80,140,200):
        variables[f"F{z:03d}"] = ("time", np.full(len(timestamps), 3+z/100.,dtype=float), {"units":"km/h" if swap_units else "m/s"})
        variables[f"D{z:03d}"] = ("time", np.full(len(timestamps),180.+z/20,dtype=float),{"units":"degree","long_name":"wind direction from"})
    ds=xr.Dataset(variables,coords=coords,attrs={"title":"synthetic fixture for testing only"})
    ds.to_netcdf(path, engine="scipy")


def test_inspector_validates_schema_and_provenance(tmp_path):
    p=tmp_path/"test.nc"; _make_tower(p)
    mapping=ROOT/"data/examples/knmi_cabauw_variable_mapping_example.json"
    manifest=tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
          "filename":p.name,"dataset":DATASET,"version":"v1.3"}))
    r=inspect_file(p,mapping,manifest)
    assert r["time_count"]==6
    assert len(r["levels"])==6
    assert "checksum_matches" in r["provenance"]
    manifest.write_text(json.dumps({"sha256":"not the hash", "filename":p.name,"dataset":DATASET,"version":"v1.3"}))
    with pytest.raises(ValueError,match="checksum"):
        inspect_file(p,mapping,manifest)


def test_inspector_fails_wrong_units(tmp_path):
    p=tmp_path/"test.nc"; _make_tower(p,swap_units=True)
    with pytest.raises(ValueError,match="unit"):
        inspect_file(p,ROOT/"data/examples/knmi_cabauw_variable_mapping_example.json")


def test_reject_duplicate_and_invalid_cabauw_records():
    with pytest.raises(ValueError):
        select_filename([{"filename":"fake.nc"}])
    with pytest.raises(ValueError):
        select_filename([{"filename":"cesar_tower_meteo_lb1_t10_v1.3_202402.nc"}],requested_month="2040-01")


def test_stage5_complete_pipeline_on_synthetic_netcdf(tmp_path):
    """Synthetic file tests code flow; its output is not observational evidence."""
    pytest.importorskip("matplotlib")
    p=tmp_path/"test.nc"; _make_tower(p)
    manifest=tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
           "filename":p.name,"dataset":DATASET,"version":"v1.3"}))
    from run_knmi_cabauw_stage5 import execute
    r = execute(p,manifest,ROOT/"data/examples/knmi_cabauw_variable_mapping_example.json", tmp_path/"out")
    assert r["manifest_checksum_verified"]
    assert r["observations_converted"] == 36
    assert r["profiles"] == 6
    assert len(r["figures"]) == 6
    assert (tmp_path/"out"/"stage5_summary.json").exists()
