import logging
import pathlib
import stat
import subprocess  # ruff:ignore[suspicious-subprocess-import]

import numpy as np
import pandas as pd
import xarray as xr
from omegaconf import OmegaConf

from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def iver(
    *,
    version,
    exp,
    tag,
    date_start,
    date_end,
    forecast_only,
    date_freq,
    profile,
    obstat,
    tech,
    clean,
    nochecks,
    check,
):
    date_freq //= pd.Timedelta('1h')
    if date_freq == 12:
        dbasetime_days = '1'
        basetime = '00, 12'
    else:
        dbasetime_days = str(int(date_freq // 24))
        basetime = '00'
    iver_file = pathlib.Path(__file__).parent / 'iver.sh'
    version = '' if version is None else f'/{version}'
    logger.info('running %s/%s IVER for %s until %s', profile, tag, exp, date_end)
    subprocess.run(  # ruff:ignore[subprocess-without-shell-equals-true]
        [
            '/bin/sh',
            str(iver_file),
            version,
            exp,
            tag,
            date_start.strftime('%m,%d,%Y'),
            date_end.strftime('%m,%d,%Y'),
            '1' if forecast_only else '0',
            dbasetime_days,
            basetime,
            profile,
            '' if obstat else '/noobstat,$',
            '' if tech else '/notech,$',
            '/clean,$' if clean else '',
            '/nochecks,$' if nochecks else '',
        ],
        check=check,
    )


def get_iver_path(profile):
    config_file = pathlib.Path('~').expanduser() / f'.iver.{profile}'
    with pathlib.Path(config_file).open('r', encoding=None) as f:
        return pathlib.Path(f.readline().strip())


def get_profile_config(profile):
    config_file = get_iver_path(profile) / 'watch_duck.yaml'
    return OmegaConf.load(config_file)


def check_full_iver(exp, profile):
    iver_path = get_iver_path(profile)
    iver_stats_sfc = iver_path / f'stats/verify_{exp}_0001_{profile}_sfc.nc'
    iver_stats_lvl = iver_path / f'stats/verify_{exp}_0001_{profile}.nc'
    return iver_stats_sfc.exists() and iver_stats_lvl.exists()


def check_full_netcdf(exp, profile):
    iver_path = get_iver_path(profile)
    netcdf_sfc = iver_path / f'grib/{exp}_sfc_fc.nc'
    netcdf_lvl = iver_path / f'grib/{exp}_fc.nc'
    return netcdf_sfc.exists() and netcdf_lvl.exists()


def get_grib_paths(tmpdir, exp, dates, suffix):
    tmpdir = pathlib.Path(tmpdir)
    return [tmpdir / f'{exp}/{date:%Y%m%d%H}{suffix}.grib' for date in dates]


def get_netcdf_encoding(ds):
    chunked_dims = {'julian_day', 'step'}
    encoding = {}
    for name, variable in ds.data_vars.items():
        variable_encoding = {
            'zlib': True,
            'shuffle': True,
            'complevel': 1,
            'chunksizes': tuple(
                1 if dim in chunked_dims else ds.sizes[dim] for dim in variable.dims
            ),
        }
        if variable.dtype.kind == 'f':
            variable_encoding['dtype'] = 'float32'
        encoding[name] = variable_encoding
    return encoding


def concatenate_grib_files(grib_files, output_file, template_file):
    individual_ds = []
    for path in grib_files:
        logger.info(
            '    reading grib file: %s',
            path,
        )
        individual_ds.append(xr.open_dataset(
            path,
            engine='cfgrib',
        ).drop_vars('valid_time'))
    ds = xr.concat(individual_ds, dim='time').rename(time='julian_day')
    ds = ds.assign_coords(
        step=(ds.step / pd.Timedelta('1h')).astype('float32'),
        latitude=ds.latitude.astype('float32'),
        longitude=ds.longitude.astype('float32'),
    )
    if 'isobaricInhPa' in ds:
        ds = ds.rename(isobaricInhPa='level')
        ds = ds.assign_coords(level=ds.level.astype('float32'))
        ds = ds.sortby('level')
    else:
        ds = ds.expand_dims('level').assign_coords(level=np.array([0], dtype='float32'))
        ds = ds.rename(
            u10='z10u',
            v10='z10v',
            t2m='z2t',
            siconc='ci',
        )
    ds = ds.drop_vars(
        set(ds.coords) - {'julian_day', 'step', 'level', 'latitude', 'longitude'},
    )
    ds = ds.transpose('julian_day', 'step', 'level', 'latitude', 'longitude')
    ds = ds.drop_attrs(deep=True)
    logger.info('reading template netcdf file: %s', template_file)
    template = xr.open_dataset(template_file, engine='h5netcdf')
    # re-assign coords from template
    ds = ds.assign_coords(
        julian_day=template.julian_day,
        step=template.step,
        level=template.level,
        latitude=template.latitude,
        longitude=template.longitude,
    )
    # get attributes from template
    for var in template.data_vars:
        ds[var].attrs = template[var].attrs.copy()
    logger.info('writing netcdf file: %s', output_file)
    ds.to_netcdf(
        output_file,
        engine='h5netcdf',
        encoding=get_netcdf_encoding(ds),
        unlimited_dims=('julian_day',),
    )


def grib_to_netcdf(profile, tmpdir):
    iver_path = get_iver_path(profile)
    config = get_profile_config(profile)
    dates = pd.date_range(
        start=config.date_start,
        end=config.date_end,
        freq=config.date_freq,
    )

    for exp in config.experiments:
        if check_full_iver(exp, profile):
            logger.info('skipping GRIB files for %s (IVER stats already exist)', exp)
            continue

        for suffix in ('', '_sfc'):
            output_file = iver_path / f'grib/{exp}{suffix}_fc.nc'
            template_file = iver_path / f'grib/{config.exp_template}{suffix}_fc.nc'
            if output_file.exists():
                logger.info(
                    'skipping GRIB files for %s%s (nc file already exists)',
                    exp,
                    suffix,
                )
                continue

            grib_files = get_grib_paths(tmpdir, exp, dates, suffix)
            missing_files = [path for path in grib_files if not path.exists()]
            if missing_files:
                logger.info(
                    'skipping GRIB files for %s%s (%d forecast files missing)',
                    exp,
                    suffix,
                    len(missing_files),
                )
                continue

            logger.info('concatenating GRIB files for %s%s', exp, suffix)
            concatenate_grib_files(grib_files, output_file, template_file)
            output_file.chmod(
                output_file.stat().st_mode
                & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH),
            )

            logger.info('removing GRIB files for %s/%s', exp, suffix)
            if not output_file.exists():
                logger.critical('expected output file does not exist: %s', output_file)
                logger.critical('skipping removal of GRIB files')
                continue
            for path in get_grib_paths(iver_path, exp, dates, suffix):
                if path.exists():
                    path.unlink(missing_ok=True)

        output_file = iver_path / f'grib/{exp}_fc.nc'
        output_file_sfc = iver_path / f'grib/{exp}_sfc_fc.nc'
        tmp_path = iver_path / f'grib/{exp}'
        if output_file.exists() and output_file_sfc.exists() and tmp_path.exists():
            tmp_path.rmdir()


def clean_iver(profile, experiments):
    iver_path = get_iver_path(profile)
    for exp in experiments:
        for level in ('', '_sfc'):
            full_iver = iver_path / f'stats/verify_{exp}_0001_{profile}{level}.nc'
            tmp_iver = iver_path / f'stats/verify_{exp}_0001_tmp{level}.nc'
            if full_iver.exists() and tmp_iver.exists():
                logger.info('removing tmp file: %s', tmp_iver)
                tmp_iver.unlink()


def get_date_current(exp_report):
    index_postprocess = exp_report.index_postprocess.to_numpy().item()
    exp_date_start = pd.Timestamp(exp_report.date_start.to_numpy().item())
    exp_date_freq = exp_report.date_freq.to_numpy().item() * pd.Timedelta('1h')
    return exp_date_start + exp_date_freq * index_postprocess


def normalise_date_current(date_current, date_start, date_freq):
    date_current = date_current.normalize() - pd.Timedelta('1D')
    return date_start + date_freq * ((date_current - date_start) // date_freq)


def run_iver(
    *,
    wdir,
    profile,
    experiment,
    experiment_type,
    clean,
):
    wdir = WorkingDirectory(wdir)
    config = get_profile_config(profile)
    date_start = pd.Timestamp(config.date_start)
    date_end = pd.Timestamp(config.date_end)
    date_freq = pd.Timedelta(config.date_freq)

    if experiment == 'all':
        experiments = config.experiments
    else:
        experiments = {experiment: experiment_type}

    report = wdir.get_report(time=-1).load()
    for exp, exp_type in experiments.items():
        if check_full_iver(exp, profile):
            logger.info(
                'skipping %s/%s IVER for %s (already done)',
                profile,
                profile,
                exp,
            )
            continue
        if exp in report.exp.to_numpy():
            date_current = get_date_current(report.sel(exp=exp))
            if date_current <= date_start:
                logger.info('skipping %s/tmp IVER for %s (too early)', profile, exp)
                continue
            date_current = normalise_date_current(date_current, date_start, date_freq)
            tag = 'tmp'
            if date_current >= date_end:
                date_current = date_end
                tag = profile
        else:
            date_current = date_end
            tag = profile
        iver(
            version=config.version,
            exp=exp,
            tag=tag,
            date_start=date_start,
            date_end=date_current,
            forecast_only=(exp_type == 'fc'),
            date_freq=date_freq,
            profile=profile,
            obstat=config.obstat,
            tech=config.tech,
            clean=clean,
            nochecks=False,
            check=False,
        )

    clean_iver(profile, config.experiments)


def run_iver_no_mars(
    *,
    wdir,
    profile,
):
    wdir = WorkingDirectory(wdir)
    config = get_profile_config(profile)
    date_start = pd.Timestamp(config.date_start)
    date_end = pd.Timestamp(config.date_end)
    date_freq = pd.Timedelta(config.date_freq)

    for exp, exp_type in config.experiments.items():
        if check_full_iver(exp, profile):
            logger.info(
                'skipping %s IVER for %s (already done)',
                profile,
                exp,
            )
            continue
        if not check_full_netcdf(exp, profile):
            logger.info(
                'skipping %s IVER for %s (missing forecasts)',
                profile,
                exp,
            )
            continue
        iver(
            version=config.version,
            exp=exp,
            tag=profile,
            date_start=date_start,
            date_end=date_end,
            forecast_only=(exp_type == 'fc'),
            date_freq=date_freq,
            profile=profile,
            obstat=config.obstat,
            tech=config.tech,
            clean=False,
            nochecks=True,
            check=False,
        )
