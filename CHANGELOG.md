# Version history

## Version 1.0.0 (2026-06-19)

- First release.

## Version 1.1.0 (2026-08-17)

- Update in IVER.

## Version 1.1.1 (2026-08-17)

- Added option to show version number.

## Version 1.2.0 (2026-10-09)

- Added the IVER without MARS commands.

## Version 1.2.1 (2026-10-28)

- Fixed `grib-to-nc` not removing the GRIB files after converting them to NetCDF.
- `grib-to-nc` no longer creates cfgrib index (`.idx`) files.
- Removed the `-d` short form of the `--debug` option, which clashed with `show -d` (download).
- Reworded the help text of the `show` command.
- Updated the README.

## Version 1.3.0 (2026-11-02)

- Added the `iver-postprocess` command, which merges the IVER stats files of a profile into a single zarr archive.
- Added `cftime` to the dependencies (needed by `grib-to-nc`).
- Fixed the speed shown by `summary` and `show` after an experiment is restarted: only the hours after the last restart (when the progress falls back to the start) are used, and the hours when the experiment was finished (state complete or progress at the end) are no longer counted.
- Added the `restart_max_index` option to the `[summary]` config (default 2): a drop in progress counts as a restart only if the progress falls back to this index or below.
- Updated the README.
