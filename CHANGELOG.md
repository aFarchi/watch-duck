# Version history

## Version 1.0.0 (2026-06-19)

- First release.

## Version 1.1.0 (2026-08-17)

- Update in IVER.

## Version 1.1.1 (2026-08-17)

- Added option to show version number.

## Version 1.2.0 (2026-10-09)

- Added the IVER without MARS commands.
- Fixed negative speeds shown after an experiment is restarted.
- `grib-to-nc` reads the GRIB files from the `tmpdir` directory of the `[forecasts]` config, also converts the surface (`_sfc`) files, and takes the coordinates and attributes of the NetCDF output from a template experiment (`exp_template` in the profile config).
- `iver-no-mars` runs IVER with the `/nochecks` option.

## Version 1.2.1 (2026-10-28)

- Fixed `grib-to-nc` not removing the GRIB files after converting them to NetCDF.
- `grib-to-nc` no longer creates cfgrib index (`.idx`) files.
- Removed the `-d` short form of the `--debug` option, which clashed with `show -d` (download).
- Reworded the help text of the `show` command.
- Updated the README.

## Version 1.3.0 (2026-11-03)

- Added the `iver-postprocess` command, which merges the IVER stats files of a profile into a single zarr archive.
- `iver-postprocess` keeps the region statistic (`STAT_REGION`), stores the forecast dates as a `date` coordinate (from `JULIAN_DAY`, rounded to the hour), and says which data variables differ when it skips an experiment.
- Added `cftime` to the dependencies (needed by `grib-to-nc`).
- Fixed the speed shown by `summary` and `show` after an experiment is restarted: only the hours after the last restart (when the progress falls back to the start) are used, and the hours when the experiment was finished (state complete or progress at the end) are no longer counted.
- Added the `restart_max_index` option to the `[summary]` config (default 2): a drop in progress counts as a restart only if the progress falls back to this index or below.
- Updated the README.
