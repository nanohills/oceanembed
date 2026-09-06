"""
Downloads daily-averaged CCMP surface wind data (u, v) from PO.DAAC for
the North Indian Ocean domain used in the OceanEmbed problem statement,
using OPeNDAP for server-side cropping (same approach validated for
currents, since Harmony fails there too, and CCMP shares an OSCAR-style
grid/access pattern).

Dataset : CCMP_WINDS_10M6HR_L4_V3.1
          (Collection Concept ID: C2916514952-POCLOUD)
          6-hourly, 0.25deg, native grid. Confirmed via DMR: dimension
          order is (time, latitude, longitude) -- note this is DIFFERENT
          from OSCAR currents, which uses (time, longitude, latitude).
          Coordinate variable names are "latitude"/"longitude" (full
          words), not "lat"/"lon" like OSCAR uses.

Region  : 5N-30N, 45E-105E  (North Indian Ocean, matches the other scripts)

Each granule covers ONE FULL DAY with 4 timesteps (6-hourly). Since the
PS wants daily resolution, this script downloads all 4 timesteps cropped
to our region, then averages across time locally to produce one daily
mean value per grid cell.

Requires:
    uv add requests xarray netCDF4

Needs a free Earthdata Login with ~/.netrc credentials (same as the
other scripts):
    echo "machine urs.earthdata.nasa.gov login USER password PASS" > ~/.netrc
    chmod 600 ~/.netrc

Usage:
    python download_winds.py --start 2019-01-01 --end 2023-12-31 \
        --outdir ./data/winds
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import requests
import xarray as xr

COLLECTION_CONCEPT_ID = "C2916514952-POCLOUD"
LAT_MIN, LAT_MAX = 5.0, 30.0
LON_MIN, LON_MAX = 45.0, 105.0


def daterange(start: datetime, end: datetime):
    days = (end - start).days
    for i in range(days + 1):
        yield start + timedelta(days=i)


def get_opendap_url(session: requests.Session, date: datetime) -> str | None:
    """Look up a single day's granule in CMR and return its OPeNDAP URL."""
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
    """Fetch latitude/longitude coordinate arrays once to compute exact
    array indices for our bounding box. Note: CCMP uses full names
    "latitude"/"longitude", not "lat"/"lon" like OSCAR."""
    url = f"{sample_url}.dap.nc4?dap4.ce=/latitude;/longitude"
    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path("_ccmp_coord_check.nc")
    tmp.write_bytes(resp.content)
    ds = xr.open_dataset(tmp)

    lat_vals = ds["latitude"].values
    lon_vals = ds["longitude"].values
    lat_idx = [i for i, v in enumerate(lat_vals) if LAT_MIN <= v <= LAT_MAX]
    lon_idx = [i for i, v in enumerate(lon_vals) if LON_MIN <= v <= LON_MAX]

    ds.close()
    tmp.unlink()

    return lat_idx[0], lat_idx[-1], lon_idx[0], lon_idx[-1]


def get_coord_values(session: requests.Session, opendap_url: str, indices: tuple):
    lat_start, lat_end, lon_start, lon_end = indices
    ce = f"/latitude[{lat_start}:1:{lat_end}];/longitude[{lon_start}:1:{lon_end}]"
    url = f"{opendap_url}.dap.nc4?dap4.ce={ce}"

    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path("_ccmp_latlon.nc")
    tmp.write_bytes(resp.content)
    ds = xr.open_dataset(tmp)
    lat_values = ds["latitude"].values.copy()
    lon_values = ds["longitude"].values.copy()
    ds.close()
    tmp.unlink()

    return lat_values, lon_values


def download_cropped_day(session: requests.Session, opendap_url: str,
                          indices: tuple, lat_values, lon_values, out_path: Path):
    """Fetch all 4 six-hourly timesteps of uwnd/vwnd cropped to our
    region, average across time to get one daily value per cell."""
    lat_start, lat_end, lon_start, lon_end = indices
    # Confirmed via DMR: uwnd/vwnd dims are (time, latitude, longitude),
    # so brackets go [time][lat][lon] in that order, matching declaration.
    ce = (f"/uwnd[0:1:3][{lat_start}:1:{lat_end}][{lon_start}:1:{lon_end}];"
          f"/vwnd[0:1:3][{lat_start}:1:{lat_end}][{lon_start}:1:{lon_end}]")
    url = f"{opendap_url}.dap.nc4?dap4.ce={ce}"

    resp = session.get(url)
    resp.raise_for_status()

    tmp = Path(str(out_path) + ".tmp")
    tmp.write_bytes(resp.content)

    ds = xr.open_dataset(tmp, decode_times=False)
    ds = ds.assign_coords(latitude=("latitude", lat_values), longitude=("longitude", lon_values))

    # Average the 4 six-hourly timesteps down to one daily mean value
    daily_mean = ds[["uwnd", "vwnd"]].mean(dim="time", skipna=True)
    daily_mean.to_netcdf(out_path)

    ds.close()
    tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description="Download CCMP winds for North Indian Ocean")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2019-01-01")
    parser.add_argument("--end", required=True, help="End date, e.g. 2023-12-31")
    parser.add_argument("--outdir", default="./data/winds", help="Output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    session = requests.Session()
    session.trust_env = True

    print("Looking up bounding box indices from a sample granule...")
    sample_url = get_opendap_url(session, start)
    if sample_url is None:
        raise SystemExit(f"No granule found for start date {args.start}, check the date.")
    indices = get_bbox_indices(session, sample_url)
    print(f"Using indices: lat {indices[0]}:{indices[1]}, lon {indices[2]}:{indices[3]}")

    print("Fetching actual lat/lon coordinate values (once, reused for all days)...")
    lat_values, lon_values = get_coord_values(session, sample_url, indices)

    dates = list(daterange(start, end))
    print(f"\nDownloading {len(dates)} day(s), cropped server-side via OPeNDAP, "
          f"averaged from 6-hourly to daily...")

    for date in dates:
        out_path = outdir / f"ccmp_winds_{date.strftime('%Y%m%d')}.nc"
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

    print(f"\nDone. Cropped, daily-averaged files saved under {outdir}, variables: uwnd, vwnd.")


if __name__ == "__main__":
    main()