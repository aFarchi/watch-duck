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
