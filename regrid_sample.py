"""
Regrids SST and currents onto a common 0.25deg grid, as a first proof of
the Phase 2 pipeline before extending to all 5 surface variables.

Target grid: 5N-30N, 45E-105E, 0.25deg spacing, 100 lat x 240 lon points,
matching the grid your currents data already sits on natively.

Why start with just these two: SST needs real regridding (native 0.05deg
-> 0.25deg, a 5x reduction), currents is already on the exact target
grid (0.25deg, clean 5.0/5.25/... values) so it's a good "should pass
through almost unchanged" sanity check for the pipeline itself.

Requires:
    get esmf              (system dependency, Arch)
    uv add xesmf xarray netCDF4

If xesmf fails to install/build, fall back to xarray's built-in .interp()
method instead (simpler bilinear interpolation, no extra system deps).

Usage:
    python regrid_sample.py --sst-file data/sst/ostia_sst_2019.nc \
        --currents-file data/currents/oscar_currents_20190101.nc \
        --date 2019-01-01
"""

import argparse

import numpy as np
import xarray as xr

try:
    import xesmf as xe
    HAS_XESMF = True
except ImportError:
    HAS_XESMF = False
    print("xesmf not available, falling back to xarray's .interp() "
          "(simpler bilinear interpolation, no conservative regridding)")

LAT_MIN, LAT_MAX = 5.0, 30.0
LON_MIN, LON_MAX = 45.0, 105.0
TARGET_RES = 0.25


def build_target_grid():
    """The common 0.25deg grid every variable will be regridded onto."""
    target_lat = np.arange(LAT_MIN, LAT_MAX + TARGET_RES, TARGET_RES)
    target_lon = np.arange(LON_MIN, LON_MAX + TARGET_RES, TARGET_RES)
    return xr.Dataset({
        "lat": (["lat"], target_lat),
        "lon": (["lon"], target_lon),
    })


def regrid_variable(ds: xr.Dataset, varname: str, lat_name: str, lon_name: str,
                     target_grid: xr.Dataset) -> xr.DataArray:
    """Regrid one variable from its native grid onto the common target
    grid, using xesmf if available, otherwise xarray's .interp()."""
    da = ds[varname]

    # Standardize coordinate names to lat/lon for the regridding step,
    # regardless of what the source file called them (we've seen lat/lon,
    # latitude/longitude, and mismatched dimension orders across sources)
    da = da.rename({lat_name: "lat", lon_name: "lon"})

    if HAS_XESMF:
        regridder = xe.Regridder(da, target_grid, method="bilinear")
        return regridder(da)
    else:
        return da.interp(lat=target_grid["lat"], lon=target_grid["lon"], method="linear")


def main():
    parser = argparse.ArgumentParser(description="Regrid SST and currents onto common 0.25deg grid")
    parser.add_argument("--sst-file", required=True, help="Path to one year's SST NetCDF file")
    parser.add_argument("--currents-file", required=True, help="Path to one day's cropped currents file")
    parser.add_argument("--date", required=True, help="Date to extract from the SST file, e.g. 2019-01-01")
    args = parser.parse_args()

    target_grid = build_target_grid()
    print(f"Target grid: {target_grid.sizes['lat']} lat x {target_grid.sizes['lon']} lon points\n")

    print("=== Regridding SST ===")
    sst_ds = xr.open_dataset(args.sst_file)
    sst_on_day = sst_ds["analysed_sst"].sel(time=args.date, method="nearest")
    sst_regridded = regrid_variable(
        sst_on_day.to_dataset(name="analysed_sst"), "analysed_sst",
        lat_name="latitude", lon_name="longitude",
        target_grid=target_grid,
    )
    print(f"SST regridded shape: {sst_regridded.shape}")
    print(f"SST value range: {float(sst_regridded.min())} to {float(sst_regridded.max())} K")

    print("\n=== Regridding currents (u) ===")
    curr_ds = xr.open_dataset(args.currents_file, decode_times=False)
    u_regridded = regrid_variable(
        curr_ds, "u",
        lat_name="latitude", lon_name="longitude",
        target_grid=target_grid,
    )
    print(f"u regridded shape: {u_regridded.shape}")
    print(f"u value range: {float(u_regridded.min())} to {float(u_regridded.max())} m/s")

    print("\n=== Alignment check ===")
    print("Both variables should now share identical lat/lon coordinates:")
    print(f"SST lat matches currents lat: {bool(np.allclose(sst_regridded.lat, u_regridded.lat))}")
    print(f"SST lon matches currents lon: {bool(np.allclose(sst_regridded.lon, u_regridded.lon))}")


if __name__ == "__main__":
    main()