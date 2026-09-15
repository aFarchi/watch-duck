import logging
import pathlib
import stat
import subprocess  # ruff:ignore[suspicious-subprocess-import]

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


def get_grib_paths(iver_path, exp, dates, suffix):
    return [
        iver_path / f'grib/{exp}/{date:%Y%m%d%H}{suffix}.grib' for date in dates
    ]


def concatenate_grib_files(grib_files, output_file):
    ds = xr.concat(
        [xr.open_dataset(path, engine='cfgrib') for path in grib_files],
        dim='time',
    ).rename(
        time='julian_day',
        isobaricInhPa='level',
    ).sortby('level')
    ds = ds.assign_coords(
        step=(ds.step / pd.Timedelta('1h')).astype('float32'),
        level=ds.level.astype('float32'),
        latitude=ds.latitude.astype('float32'),
        longitude=ds.longitude.astype('float32'),
    )
    ds = ds.drop_vars(
        set(ds.coords) - {'julian_day', 'step', 'level', 'latitude', 'longitude'}
    )
    ds = ds.drop_attrs(deep=True)
    ds.to_netcdf(output_file, engine='h5netcdf')


def grib_to_netcdf(profile):
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
            if output_file.exists():
                logger.info('skipping GRIB files for %s/%s (nc file already exists)', exp, suffix)
                continue

            grib_files = get_grib_paths(iver_path, exp, dates, suffix)
            missing_files = [path for path in grib_files if not path.exists()]
            if missing_files:
                logger.info(
                    'skipping GRIB files for %s/%s (%d forecast files missing)',
                    exp,
                    suffix,
                    len(missing_files),
                )
                continue

            logger.info('concatenating GRIB files for %s/%s', exp, suffix)
            concatenate_grib_files(grib_files, output_file)
            output_file.chmod(
                output_file.stat().st_mode
                & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            )

        logger.info('removing GRIB files for %s', exp)
        for suffix in ('', '_sfc'):
            output_file = iver_path / f'grib/{exp}{suffix}_fc.nc'
            if not output_file.exists():
                logger.critical('expected output file does not exist: %s', output_file)
                logger.critical('skipping removal of GRIB files')
                continue
            for path in get_grib_paths(iver_path, exp, dates, suffix):
                if path.exists():
                    path.unlink()
        (iver_path / f'grib/{exp}').rmdir()


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
            check=False,
        )
