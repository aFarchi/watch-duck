import logging
import pathlib
import subprocess  # noqa: S404

import pandas as pd

from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def iver(version, exp, tag, date_start, date_end, date_freq, profile, check):
    iver_file = pathlib.Path(__file__).parent / 'iver.sh'
    version = '' if version is None else f'/{version}'
    subprocess.run(  # noqa: S603
        [
            '/bin/sh',
            str(iver_file),
            version,
            exp,
            tag,
            date_start.strftime('%m,%d,%Y'),
            date_end.strftime('%m,%d,%Y'),
            str(int(date_freq // 24)),
            profile,
        ],
        check=check,
    )


def run_partial_iver(wdir, date_start, date_end, date_freq, profile, version=None):
    wdir = WorkingDirectory(wdir)
    date_start = pd.Timestamp(date_start)
    date_end = pd.Timestamp(date_end)
    report = wdir.get_report().isel(time=-1).load()
    report = report.where(report.experiment_type == 'fc', drop=True)
    report = report.where(report.date_start == date_start, drop=True)
    report = report.where(report.date_end == date_end, drop=True)
    report = report.where(report.date_freq == date_freq, drop=True)
    report = report.where(report.index_postprocess > 0, drop=True)
    report['date_current'] = report.date_start + pd.Timedelta(
        '1h',
    ) * report.date_freq * (report.index_postprocess - 1)
    for exp, date_current in zip(
        report.exp.to_numpy(),
        report.date_current.to_numpy(),
        strict=True,
    ):
        time = pd.Timestamp(date_current)
        logger.info('Running partial IVER for %s until %s', exp, time)
        iver(
            version=version,
            exp=exp,
            tag='tmp',
            date_start=date_start,
            date_end=time,
            date_freq=date_freq,
            profile=profile,
            check=False,
        )


def check_full_iver(exp, profile):
    config_file = pathlib.Path('~').expanduser() / f'.iver.{profile}'
    with pathlib.Path(config_file).open('r', encoding=None) as f:
        iver_path = pathlib.Path(f.readline().strip())
    iver_stats_sfc = iver_path / f'stats/verify_{exp}_0001_{profile}_sfc.nc'
    iver_stats_lvl = iver_path / f'stats/verify_{exp}_0001_{profile}.nc'
    return iver_stats_sfc.exists() and iver_stats_lvl.exists()


def run_full_iver(wdir, date_start, date_end, date_freq, profile, version=None):
    wdir = WorkingDirectory(wdir)
    date_start = pd.Timestamp(date_start)
    date_end = pd.Timestamp(date_end)
    report = wdir.get_report().isel(time=-1).load()
    report = report.where(report.finished_experiment_type == 'fc', drop=True)
    report = report.where(report.finished_date_start == date_start, drop=True)
    report = report.where(report.finished_date_end == date_end, drop=True)
    report = report.where(report.finished_date_freq == date_freq, drop=True)
    failed_experiments = []
    for exp in report.finished_exp.to_numpy():
        if check_full_iver(exp, profile):
            logger.info('Skipping IVER for %s (already done)', exp)
            continue
        logger.info('Running full IVER for %s', exp)
        try:
            iver(
                version=version,
                exp=exp,
                tag=profile,
                date_start=date_start,
                date_end=date_end,
                date_freq=date_freq,
                profile=profile,
                check=True,
            )
        except subprocess.CalledProcessError:
            failed_experiments.append(exp)
    if failed_experiments:
        logger.warning('Failed experiments:')
        for exp in failed_experiments:
            logger.warning('    %s', exp)
        raise subprocess.CalledProcessError


def run_iver(*, partial, profiles, **kwargs):
    run_iver_function = run_partial_iver if partial else run_full_iver
    for profile, config in profiles.items():
        run_iver_function(profile=profile, **config, **kwargs)
