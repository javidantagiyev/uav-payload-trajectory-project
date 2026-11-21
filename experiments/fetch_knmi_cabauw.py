"""Retrieve a single validated Cabauw monthly file from the official KNMI API.

The bundled fallback is KNMI's published, shared anonymous key, not a user credential.
A private registered key can be provided through KNMI_API_KEY (never committed).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATASET = "cesar_tower_meteo_lb1_t10"
VERSION = "v1.3"
API = "https://api.dataplatform.knmi.nl/open-data/v1"
CATALOG = "https://dataplatform.knmi.nl/dataset/cesar-tower-meteo-lb1-t10-v1-3"
# public anonymous key published on https://developer.dataplatform.knmi.nl/open-data-api
# listed validity: through august 1, 2027; user-supplied keys override this
PUBLIC_ANONYMOUS_KEY = ""
FILE_NAME = re.compile(r"^cesar_tower_meteo_lb1_t10_v1[.]3_([0-9]{6})[.]nc$", re.I)


def _read_json(request, opener=urlopen):
    with opener(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def _api_request(url, api_key):
    return Request(url, headers={"Authorization": api_key, "Accept": "application/json"})


def select_filename(records, requested_month=None, requested_filename=None):
    files = []
    for entry in records:
        name = entry.get("filename", "") if isinstance(entry, dict) else ""
        if not FILE_NAME.fullmatch(name):
            continue
        files.append(name)
    if requested_filename:
        if not FILE_NAME.fullmatch(requested_filename):
            raise ValueError("filename must match the validated Cabauw v1.3 monthly NetCDF naming pattern")
        if requested_filename not in files:
            raise ValueError("requested filename is absent from listed API results")
        return requested_filename
    if requested_month:
        month = requested_month.replace("-", "")
        hits = [name for name in files if FILE_NAME.fullmatch(name).group(1) == month]
        if len(hits) != 1:
            raise ValueError("month not found in the queried file page; use --filename for older months")
        return hits[0]
    if not files:
        raise ValueError("KNMI file listing returned no matching validated Cabauw monthly NetCDF")
    return max(files, key=lambda name: FILE_NAME.fullmatch(name).group(1))


def list_files(api_key, max_keys=100, begin=None, opener=urlopen):
    params = {"maxKeys": max_keys, "sorting": "desc", "orderBy": "filename"}
    if begin:
        params["begin"] = begin
    endpoint = f"{API}/datasets/{DATASET}/versions/{VERSION}/files?{urlencode(params)}"
    result = _read_json(_api_request(endpoint, api_key), opener)
    if not isinstance(result, dict) or not isinstance(result.get("files"), list):
        raise ValueError("unexpected KNMI API listing response")
    return result


def get_download_url(filename, api_key, opener=urlopen):
    endpoint = f"{API}/datasets/{DATASET}/versions/{VERSION}/files/{quote(filename)}/url"
    payload = _read_json(_api_request(endpoint, api_key), opener)
    url = payload.get("temporaryDownloadUrl") if isinstance(payload, dict) else None
    if not isinstance(url, str) or urlparse(url).scheme != "https":
        raise ValueError("KNMI API did not return an HTTPS temporary download URL")
    return url


def stream_file(url, target, max_bytes=120_000_000, opener=urlopen):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    h = hashlib.sha256()
    total = 0
    try:
        with opener(Request(url, headers={"User-Agent": "sdp-atmospheric-research/6g5"}), timeout=90) as response, part.open("wb") as fout:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise ValueError("remote file exceeds configured size safety limit")
                h.update(block)
                fout.write(block)
        if total < 100:
            raise ValueError("downloaded NetCDF is unexpectedly small")
        part.replace(target)
    finally:
        if part.exists():
            part.unlink()
    return {"size_bytes": total, "sha256": h.hexdigest()}


def download_one(destination, requested_month=None, requested_filename=None, api_key=None,
                 opener=urlopen):
    key = api_key or os.environ.get("KNMI_API_KEY") or PUBLIC_ANONYMOUS_KEY
    destination = Path(destination)
    if requested_month and not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", requested_month):
        raise ValueError("--month must be YYYY-MM")
    # The API's first descending file page provides a reproducible latest-month choice.
    # For older data, use the exact name from the KNMI file browser with --filename.
    if requested_filename:
        if not FILE_NAME.fullmatch(requested_filename):
            raise ValueError("filename must match the validated Cabauw v1.3 monthly naming pattern")
        filename = requested_filename
    else:
        listing = list_files(key, max_keys=100, opener=opener)
        filename = select_filename(listing["files"], requested_month)
    target = destination / filename
    manifest_path = destination / "knmi_download_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing observation file: {target}")
    url = get_download_url(filename, key, opener=opener)
    info = stream_file(url, target, opener=opener)
    manifest = {
        "status": "downloaded_from_declared_knmi_api_endpoint_not_independently_authenticated",
        "data_kind": "observed", "dataset": DATASET, "version": VERSION,
        "provider": "KNMI", "station": "Cabauw", "filename": filename,
        "catalog_url": CATALOG,
        "api_endpoint": f"{API}/datasets/{DATASET}/versions/{VERSION}/files",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": info["sha256"], "size_bytes": info["size_bytes"],
        "file_path": str(target.resolve()),
        "metadata_warning": "source is KNMI's validated dataset; station flags, missing values and actual file units still need inspection",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "data/raw/knmi")
    parser.add_argument("--month", help="YYYY-MM, if present in latest API listing")
    parser.add_argument("--filename", help="exact filename listed by the KNMI file browser")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.list_only:
            key = os.environ.get("KNMI_API_KEY") or PUBLIC_ANONYMOUS_KEY
            files = [x.get("filename", "") for x in list_files(key)["files"]]
            print(json.dumps({"matching_cabauw_files": [x for x in files if FILE_NAME.fullmatch(x)],
                              "raw_api_filename_examples": files[:10]}, indent=2))
        else:
            manifest = download_one(args.out, args.month, args.filename)
            print(json.dumps({"status": manifest["status"], "file_path": manifest["file_path"],
                              "sha256": manifest["sha256"], "size_bytes": manifest["size_bytes"]}, indent=2))
    except Exception as e:
        print(f"KNMI retrieval failed: {e}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
