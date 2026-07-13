import logging
import pathlib
import subprocess  # noqa: S404

import pandas as pd
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
    logger.info('Running %s/%s IVER for %s until %s', profile, tag, exp, date_end)
    subprocess.run(  # noqa: S603
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


def get_profile_config(profile):
    config_file = pathlib.Path('~').expanduser() / f'.iver.{profile}'
    with pathlib.Path(config_file).open('r', encoding=None) as f:
        iver_path = pathlib.Path(f.readline().strip())
    config_file = iver_path / 'watch_duck.yaml'
    return OmegaConf.load(config_file)


def check_full_iver(exp, profile):
    config_file = pathlib.Path('~').expanduser() / f'.iver.{profile}'
    with pathlib.Path(config_file).open('r', encoding=None) as f:
        iver_path = pathlib.Path(f.readline().strip())
    iver_stats_sfc = iver_path / f'stats/verify_{exp}_0001_{profile}_sfc.nc'
    iver_stats_lvl = iver_path / f'stats/verify_{exp}_0001_{profile}.nc'
    return iver_stats_sfc.exists() and iver_stats_lvl.exists()


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
            logger.info('skipping experiment "%s" (already done)', exp)
            continue
        if exp in report.exp.to_numpy():
            date_current = get_date_current(report.sel(exp=exp))
            date_current = normalise_date_current(date_current, date_start, date_freq)
            tag = 'tmp'
            if date_current > date_end:
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
