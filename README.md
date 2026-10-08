# watch-duck

[![PyPI version](https://badge.fury.io/py/watch-duck.svg)](https://badge.fury.io/py/watch-duck)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/watch-duck.svg)](https://anaconda.org/conda-forge/watch-duck)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Toolbox to monitor the progress of ecflow experiments.

## Installation

Install using `pip`:

    $ pip install watch-duck

For some functionalities (see below), you need to install `sitesctl` 
from [here](https://confluence.ecmwf.int/display/UDOC/SitesCTL%3A+Manage+Website+Content).

## Usage

### Configuration

When running, `watch-duck` reads the config file `~/.config/watch-duck.toml`.
The file is organised in sections, each one being associated to a specific command,
except for the main section, which is used in all commands to provide the working
directory:
```toml
[main]
wdir = '/path/to/the/working/directory'
```
In the following, the path to the working directory will simply be called `/wdir`.

### Commands

#### Get status

On the HPC, use the following command to get the state of a given ecflow suite
in a log file:
```sh
ecflow_client --host=<host> --get_state=<suite> "/wdir/log/<suite>_$(date +%Y_%m_%d_%H_%M_%S).log"
```
where `<suite>` should be replaced by the suite (eg. `daaf`) that you want
to monitor and `<host>` by the host of the given suite (eg. `ecflow-pifs-rd-f-1`).

You need to run this command at least once per hour to get a proper report.
Note that if you do so using `hpc-cron`, you would need to run
```sh
source /etc/profile
module load ecflow
```
before you are able to use `ecflow_client`.

#### Parse

On the HPC, use the following command to parse the log files stored in `/wdir/log/`:
```sh
watch-duck parse
```
The progress and state of each experiment will be stored in dedicated zarr archives:
`/wdir/progress/<exp>.zarr` and `/wdir/state/<exp>.zarr`.

For this command, you need to provide the following config:
```toml
[parse]
chunk_size_state = 128
chunk_size_progress = 128
suites = [
    'daaf',
]
exclude_experiments = [
]
exclude_experiment_types = [
    'fc50',
    'unknown',
]
```
where you can specify:
- the zarr chunk size (over time) of the progress and state archives;
- the list of suites that you want to monitor;
- the list of experiments to ignore;
- the list of experiment types to ignore.

Ideally, you should call this command each time you produced new log files, e.g.
using `hpc-cron`.

#### Report

On the HPC, use the following command to produce a short report about
the active experiments:
```sh
watch-duck report
```
This will read the progress archive of each active experiment and write a short
report of the progress over the last 10 days (subsampled to a 1-hour frequency)
in `/wdir/report.h5`.

For this command, you don't need to provide further config.

Ideally, you should call this command each time you updated the progress archive,
e.g. using `hpc-cron`.

#### Upload

On the HPC, use the following command to upload the latest report to the
specified website:
```sh
watch-duck upload
```
For this command, you need `sitesctl` and you need to provide the following config:
```toml
[site]
space = '<space>'
name = '<name>'
```
where `<space>` and `<name>` correspond to the space and name of the website.

Ideally, you should call this command each time you updated the report,
e.g. using `hpc-cron`.

#### Download

On any device, use the following command to download the latest report from
the specified website:
```sh
watch-duck download
```
For this command, you need `sitesctl` and you need to provide the following config:
```toml
[site]
space = '<space>'
name = '<name>'
```
where `<space>` and `<name>` correspond to the space and name of the website.

Ideally, you should call this command before showing a summary.

#### Summary

On any device, use the following command to show a summary of the latest report:
```sh
watch-duck summary
```
Use the help option to show all available options (in particular how to show
the progress only for a given suite or experiment type).

For this command, you need to provide the following config:
```toml
[summary]
delta_t = '48h'
exclude_aborted = true
exclude_suspended = true
vref_fc = 25
vref_lw = 4
vref_elda = 4
```
where you can specify:
- some parameters to compute the instantaneous speed of the experiments 
(averaging period, and whether to excluded times where the experiment was aborted or suspended);
- the reference speed for each experiment type (used to set the upper limit of the 
colour scale).

#### Finished

On any device, use the following command to show the list of experiments
that recently finished (from the latest report):
```sh
watch-duck finished
```
For this command, you don't need to provide further config.

#### Show

The `show` command is simply a concatenation of the `download` (optional),
`summary`, and `finished` commands.

#### Iver

On the HPC, use the following command to compute the IVER scores of compatible
fc experiments:
```sh
watch-duck iver <profile>
```
where `<profile>` is the name of the IVER profile to run. Following IVER's
behaviour, the profile's working directory is found in the `~/.iver.<profile>` file.
Within this directory, `watch-duck iver` will look for a yaml file named 
`/iver-wdir/watch_duck.yaml`. This yaml file contains all the parameters used
to configure IVER for that specific profile:
```yaml
date_start: 2025-01-01
date_end: 2025-12-27
date_freq: 288h
version: 3.17
obstat: false
tech: false
exp_template: <ID>
experiments:
  exp_id: exp_type
  ...
```
where you can specify:
- the IVER version;
- the start and end date of the forecasts;
- the frequency between forecasts;
- whether to include obstat and a tech report;
- a template experiment ID (will only be used in the following section);
- a list of all experiments IDs and their corresponding type.

For each experiment within this list, `watch-duck iver` will use IVER to (1)
either download the latest forecasts if the experiment is still ongoing or (2)
compute the IVER scores if the experiment is finished and the scores have not been
computed yet.

You can bypass the list of experiments and use IVER on a specific
experiment by providing its ID via the `--experiment` option and its type via
the `--experiment-type` option. You can also force IVER to re-download the forecasts
from scratch using the `--clean` option. These additional options are summarised
in the help option of the `watch-duck iver` command.

Ideally, you should call this command on a regular basis, typically once a day,
e.g. using `hpc-cron`.

#### Iver without MARS

Alternatively, you can set up your experiment so that it directly outputs the
forecast fields on disk instead of archiving them on MARS. In that case,
the IVER scores can easily be computed in two steps once the experiment is finished:
1. convert the grib files into NetCDF (as used by IVER);
2. run IVER on the gathered NetCDF files.

Step 1 can be done on the HPC using the following command:
```sh
watch-duck grib-to-nc <profile>
```
where `<profile>` is the name of the IVER profile.
The list of experiments matching that profile is found in the 
`watch_duck.yaml` file of that profile (see previous section).
For each experiment, if the NetCDF file (containing the forecast fields)
is required and if the experiment is finished (i.e. if all the grib files
are available), the grib files will be read and converted into two
NetCDF files (one for surface and one for upper air)

For this command, you need to provide the following config:
```toml
[forecasts]
tmpdir = '/path/to/forecasts'
```
where `tmpdir` is the temporary directory in which the forecast fields will appear.

Note that IVER expects a non-standard encoding of dimensions, that
is difficult to reproduce in python. Therefore, for simplicity the encoding
of the dimensions of the NetCDF files is inferred from a template experiment,
whose ID is specified in the `watch_duck.yaml` file of that profile
(see previous section). For this experiment, the IVER has to be produced using 
the "standard" process (i.e. with the `watch-duck iver` command). 

Then, step 2 can be done on the HPC using the following command:
```sh
watch-duck iver-no-mars <profile>
```
where `<profile>` is the name of the IVER profile.
This command will compute the IVER scores of the profile's experiments
for which the NetCDF files are already available.

#### Clean

On the HPC, use the following command to clean old and temporary files:
```sh
watch-duck clean
```

For this command, you don't need to provide further config, but you need to
provide the IVER configuration (see above) if you want to clean IVER's
temporary files.

Ideally, you should call this command on a regular basis, typically once a day,
e.g. using `hpc-cron`.

### Summary

On the HPC, every hour you should call:
- `ecflow_client` to get the state of the suites;
- `watch-duck parse`;
- `watch-duck report`;
- `watch-duck clean`;
- `watch-duck upload`;

and every day you shoud call:
- `watch-duck iver <profile>` for each profile where forecasts are archived in MARS;
- `watch-duck grib-to-nc <profile>` and `watch-duck iver-no-mars <profile>`
for each profile where forecasts are stored on disk.

NB: if you are only interested in the following suites: daaf, dae, dav, nemc,
these are already covered by daaf, and you can skip this first step. Just
make sure to set your `/wdir` to daaf's `/wdir` if you are on the HPC, or
to use daaf's `iver` site if you are on any other device.

Then, on any device, you can call at any time:
- `watch-duck download` (you don't need this if you are on the HPC);
- `watch-duck summary`;
- `watch-duck finished`;

or simply `watch-duck show -d`.

## Version update checklist

- format and lint the code
- update the README.md
- add the version in the CHANGELOG.md
- bump version number in pyproject.toml
- build and publish (`hatch build` & `hatch publish`)
- add the release on github

