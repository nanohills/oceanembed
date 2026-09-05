"""
Downloads daily Sea Surface Salinity (SSS) data from Copernicus Marine
(CMEMS) for the North Indian Ocean domain used in the OceanEmbed
problem statement.

Product : MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013
          (Multi Observation Global Ocean SSS, blends SMAP + SMOS + in-situ,
          0.125deg, daily, reprocessed 1993-2024)
          This is the exact product cited in the PS (DOI moi-00051).

Region  : 5N-30N, 45E-105E  (North Indian Ocean, matches the SST script)

Requires the copernicusmarine toolbox and a free CMEMS account:
    pip install copernicusmarine --break-system-packages
    copernicusmarine login          # only needed once, shared across scripts

Usage:
    python download_sss.py --start 2019-01-01 --end 2023-12-31 \
        --outdir ./data/sss
"""

import argparse
import calendar
from pathlib import Path

import copernicusmarine

DATASET_ID = "cmems_obs-mob_glo_phy-sss_my_multi_P1D"  # reprocessed daily SSS
VARIABLES = ["sos"]  # Sea Surface Salinity, in PSU

# North Indian Ocean bounding box (same as download_sst.py)
LON_MIN, LON_MAX = 45.0, 105.0
LAT_MIN, LAT_MAX = 5.0, 30.0


def download_year(year: int, outdir: Path, dry_run: bool = False):
    """Download one calendar year as a single NetCDF file (skips if exists).

    If dry_run=True, does not download anything, just asks the toolbox to
    report the estimated file size for that year and returns it in MB.
    """
    out_file = outdir / f"sss_{year}.nc"
    if not dry_run and out_file.exists():
        print(f"[skip] {out_file.name} already downloaded")
        return None

    start = f"{year}-01-01T00:00:00"
    end = f"{year}-{12:02d}-{calendar.monthrange(year, 12)[1]:02d}T23:59:59"

    action = "check size of" if dry_run else "download"
    print(f"[{action}] {year} -> {out_file.name}")

    response = copernicusmarine.subset(
        dataset_id=DATASET_ID,
        variables=VARIABLES,
        minimum_longitude=LON_MIN,
        maximum_longitude=LON_MAX,
        minimum_latitude=LAT_MIN,
        maximum_latitude=LAT_MAX,
        start_datetime=start,
        end_datetime=end,
        output_directory=str(outdir),
        output_filename=out_file.name,
        dry_run=dry_run,
    )

    if dry_run:
        size_mb = response.file_size
        print(f"    -> estimated size: {size_mb:.1f} MB")
        return size_mb
    return None


def main():
    parser = argparse.ArgumentParser(description="Download SSS for North Indian Ocean")
    parser.add_argument("--start", required=True, help="Start date, e.g. 2019-01-01")
    parser.add_argument("--end", required=True, help="End date, e.g. 2023-12-31")
    parser.add_argument("--outdir", default="./data/sss", help="Output directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't download anything, just report the total size for the date range",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start_year = int(args.start[:4])
    end_year = int(args.end[:4])

    if args.dry_run:
        total_mb = 0.0
        for year in range(start_year, end_year + 1):
            total_mb += download_year(year, outdir, dry_run=True) # type: ignore
        print(f"\nEstimated total size for {args.start} to {args.end}: "
              f"{total_mb:.1f} MB ({total_mb / 1024:.2f} GB)")
        return

    for year in range(start_year, end_year + 1):
        download_year(year, outdir)

    print("Done. Each file is one year, ~daily 0.125deg SSS over 5-30N, 45-105E.")


if __name__ == "__main__":
    main()