"""
Downloads daily OSCAR surface current data (u, v) from PO.DAAC for the
North Indian Ocean domain used in the OceanEmbed problem statement,
using NASA's Harmony service to crop the data SERVER-SIDE.

Dataset : OSCAR_L4_OC_FINAL_V2.0
          (Final quality, ~1 year latency, 0.25deg, daily, 1993-present)
          Collection Concept ID: C2098858642-POCLOUD
          DOI: 10.5067/OSCAR-25F20

Region  : 5N-30N, 45E-105E  (North Indian Ocean, matches the other scripts)

WHY THIS VERSION EXISTS: podaac-data-downloader's -b flag only filters
WHICH granules get downloaded, it does not crop them. OSCAR ships one
global file per day (~28MB/day), so the naive approach downloads the
entire globe every day just to keep a small regional slice. On a slow/
capped connection this wastes most of your bandwidth. Harmony instead
crops the file on NASA's servers before sending it to you, so you only
ever download the small cropped file.

Requires:
    uv add harmony-py

You also need a free Earthdata Login (register at urs.earthdata.nasa.gov)
and a ~/.netrc file with your credentials:
    echo "machine urs.earthdata.nasa.gov login USER password PASS" > ~/.netrc
    chmod 600 ~/.netrc

Usage:
    python download_currents.py --start 2019-01-01 --end 2023-12-31 \
        --outdir ./data/currents
"""

import argparse
from datetime import datetime
from pathlib import Path

from harmony import BBox, Client, Collection, Request

COLLECTION_ID = "C2098858642-POCLOUD"

# North Indian Ocean bounding box: BBox(west, south, east, north)
BBOX = BBox(45.0, 5.0, 105.0, 30.0)

# We only need total current (u, v), not the geostrophic-only pair (ug, vg)
VARIABLES = ["u", "v"]


def main():
    parser = argparse.ArgumentParser(
        description="Download OSCAR currents for North Indian Ocean via Harmony (server-side crop)"
    )
    parser.add_argument("--start", required=True, help="Start date, e.g. 2019-01-01")
    parser.add_argument("--end", required=True, help="End date, e.g. 2023-12-31")
    parser.add_argument("--outdir", default="./data/currents", help="Output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.fromisoformat(f"{args.start}T00:00:00")
    end_dt = datetime.fromisoformat(f"{args.end}T23:59:59")

    # Client() picks up credentials automatically from ~/.netrc
    client = Client()

    request = Request(
        collection=Collection(id=COLLECTION_ID),
        spatial=BBOX,
        temporal={"start": start_dt, "stop": end_dt},
        variables=VARIABLES,
    )

    print(f"Submitting Harmony job for {args.start} to {args.end}, "
          f"region 45-105E, 5-30N, variables {VARIABLES} ...")
    job_id = client.submit(request)

    print(f"Job submitted: {job_id}")
    print("Waiting for Harmony to crop the data server-side "
          "(this runs on NASA's servers, not your connection)...")

    import time
    while True:
        status = client.status(job_id)
        job_status = status.get("status")
        progress = status.get("progress", 0)
        print(f"  status={job_status} progress={progress}%")
        if job_status in ("successful", "failed", "canceled", "complete_with_errors"):
            break
        time.sleep(5)

    errors = status.get("errors", [])
    if errors:
        print(f"\n{len(errors)} granule-level error(s), showing first 5:")
        for err in errors[:5]:
            print(f"  - {err}")

    if job_status == "failed":
        print("\nJob failed entirely, stopping here.")
        return

    print(f"Downloading cropped result(s) to {outdir} ...")
    futures = client.download_all(job_id, directory=str(outdir), overwrite=True)
    for f in futures:
        filename = f.result()
        print(f"  saved: {filename}")

    print("\nDone. Only the cropped region was downloaded, not the full global files.")


if __name__ == "__main__":
    main()