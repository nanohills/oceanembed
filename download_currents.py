"""
Downloads daily OSCAR surface current data (u, v) from PO.DAAC for the
North Indian Ocean domain used in the OceanEmbed problem statement,
using OPeNDAP for genuine SERVER-SIDE cropping.

Dataset : OSCAR_L4_OC_FINAL_V2.0 (Collection Concept ID: C2098858642-POCLOUD)
Region  : 5N-30N, 45E-105E  (North Indian Ocean, matches the other scripts)

BACKGROUND: NASA's Harmony service fails for this dataset entirely
("Projected variable '/u' does not have an associated 'grid_mapping'
metadata attribute"), for every variable, with or without variable
subsetting. OPeNDAP, an older/simpler protocol, works fine instead and
was verified: cropping one day's global ~28MB file down to just our
region + u/v gives a ~325KB result, roughly 85x smaller.

HOW THIS WORKS:
1. Query CMR for each day's granule and its real OPeNDAP URL (per NASA's
   own docs, this URL must be fetched from metadata, never guessed/built
   by hand, since the exact path structure varies per collection).
2. Fetch just the lat/lon coordinate arrays once, to compute exact array
   indices for our bounding box (OPeNDAP slices by index, not degrees).
3. For each day, request only u/v cropped to those indices via a DAP4
   constraint expression, and save the small result directly. No full
   global file is ever downloaded.

Requires:
    uv add requests xarray netCDF4

Needs a free Earthdata Login with ~/.netrc credentials:
    echo "machine urs.earthdata.nasa.gov login USER password PASS" > ~/.netrc
    chmod 600 ~/.netrc

Usage:
    python download_currents.py --start 2019-01-01 --end 2023-12-31 \
        --outdir ./data/currents
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import requests
import xarray as xr

COLLECTION_CONCEPT_ID = "C2098858642-POCLOUD"
LAT_MIN, LAT_MAX = 5.0, 30.0
LON_MIN, LON_MAX = 45.0, 105.0


def daterange(start: datetime, end: datetime):
    days = (end - start).days
    for i in range(days + 1):
        yield start + timedelta(days=i)


def get_opendap_url(session: requests.Session, date: datetime) -> str | None:
    """Look up a single day's granule in CMR and return its real OPeNDAP
    URL from the metadata. Returns None if no granule exists for that day
    (can happen for very recent dates not yet processed)."""
    day_str = date.strftime("%Y-%m-%d")
    next_day_str = (date + timedelta(days=1)).strftime("%Y-%m-%d")

    resp = session.get(
        "https://cmr.earthdata.nasa.gov/search/granules.umm_json",
        params={
            "collection_concept_id": COLLECTION_CONCEPT_ID,
            "temporal": f"{day_str}T00:00:00Z,{next_day_str}T00:00:00Z",
            "page_size": 1,
        },
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None

    for url_entry in items[0]["umm"].get("RelatedUrls", []):
        if url_entry.get("Subtype") == "OPENDAP DATA":
            return url_entry["URL"]
    return None


def get_bbox_indices(session: requests.Session, sample_url: str):
    """Fetch lat/lon coordinate arrays once from a sample granule to
    compute exact array indices for our bounding box. OSCAR uses the
    same global 0.25deg grid for every granule, so these indices are
    reused for all days."""
    url = f"{sample_url}.dap.nc4?dap4.ce=/lat;/lon"
    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path("_coord_check.nc")
    tmp.write_bytes(resp.content)
    ds = xr.open_dataset(tmp)

    lat_vals = ds["lat"].values
    lon_vals = ds["lon"].values
    lat_idx = [i for i, v in enumerate(lat_vals) if LAT_MIN <= v <= LAT_MAX]
    lon_idx = [i for i, v in enumerate(lon_vals) if LON_MIN <= v <= LON_MAX]

    ds.close()
    tmp.unlink()

    return lat_idx[0], lat_idx[-1], lon_idx[0], lon_idx[-1]


def get_lat_lon_values(session: requests.Session, opendap_url: str, indices: tuple):
    """Fetch the actual lat/lon coordinate values once (grid is identical
    across all days, so this only needs to run against one sample day)."""
    lat_start, lat_end, lon_start, lon_end = indices
    ce = f"/lat[{lat_start}:1:{lat_end}];/lon[{lon_start}:1:{lon_end}]"
    url = f"{opendap_url}.dap.nc4?dap4.ce={ce}"

    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path("_latlon.nc")
    tmp.write_bytes(resp.content)
    ds = xr.open_dataset(tmp)
    lat_values = ds["lat"].values.copy()
    lon_values = ds["lon"].values.copy()
    ds.close()
    tmp.unlink()

    return lat_values, lon_values


def download_cropped_day(session: requests.Session, opendap_url: str,
                          indices: tuple, lat_values, lon_values, out_path: Path):
    """Fetch u/v cropped to our region, then attach the real lat/lon
    coordinate values locally (fetching lat/lon per-day would be
    redundant network calls for data that never changes)."""
    lat_start, lat_end, lon_start, lon_end = indices
    # u/v's real dimension order, confirmed via DMR, is (time, longitude,
    # latitude), so brackets must be ordered lon then lat to match.
    ce = (f"/u[0:1:0][{lon_start}:1:{lon_end}][{lat_start}:1:{lat_end}];"
          f"/v[0:1:0][{lon_start}:1:{lon_end}][{lat_start}:1:{lat_end}]")
    url = f"{opendap_url}.dap.nc4?dap4.ce={ce}"

    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path(str(out_path) + ".tmp")
    tmp.write_bytes(resp.content)

    ds = xr.open_dataset(tmp, decode_times=False)

    # Confirmed via DMR: u/v dims are (time, longitude, latitude), and the
    # dimension names genuinely match their meaning, longitude -> lon_values,
    # latitude -> lat_values, no swap needed.
    ds = ds.assign_coords(longitude=("longitude", lon_values), latitude=("latitude", lat_values))

    ds.to_netcdf(out_path)
    ds.close()
    tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description="Download OSCAR currents for North Indian Ocean")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2019-01-01")
    parser.add_argument("--end", required=True, help="End date, e.g. 2023-12-31")
    parser.add_argument("--outdir", default="./data/currents", help="Output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    session = requests.Session()
    session.trust_env = True  # picks up ~/.netrc automatically

    print("Looking up bounding box indices from a sample granule...")
    sample_url = get_opendap_url(session, start)
    if sample_url is None:
        raise SystemExit(f"No granule found for start date {args.start}, check the date.")
    indices = get_bbox_indices(session, sample_url)
    print(f"Using indices: lat {indices[0]}:{indices[1]}, lon {indices[2]}:{indices[3]}")

    print("Fetching actual lat/lon coordinate values (once, reused for all days)...")
    lat_values, lon_values = get_lat_lon_values(session, sample_url, indices)

    dates = list(daterange(start, end))
    print(f"\nDownloading {len(dates)} day(s), cropped server-side via OPeNDAP...")

    for date in dates:
        out_path = outdir / f"oscar_currents_{date.strftime('%Y%m%d')}.nc"
        if out_path.exists():
            print(f"[skip] {out_path.name} already downloaded")
            continue

        opendap_url = get_opendap_url(session, date)
        if opendap_url is None:
            print(f"[missing] no granule for {date.strftime('%Y-%m-%d')}, skipping")
            continue

        try:
            download_cropped_day(session, opendap_url, indices, lat_values, lon_values, out_path)
            print(f"[saved] {out_path.name} ({out_path.stat().st_size / 1024:.1f} KB)")
        except requests.HTTPError as e:
            print(f"[error] {date.strftime('%Y-%m-%d')}: {e}")

    print(f"\nDone. Cropped files saved under {outdir}, variables: u, v.")


if __name__ == "__main__":
    main()