import logging
import pathlib
import subprocess  # noqa: S404

import pandas as pd

from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def run_iver_f2025(wdir):
    wdir = WorkingDirectory(wdir)
    report = wdir.get_report().isel(time=-1).load()
    report = report.where(report.experiment_type == 'fc', drop=True)
    report = report.where(report.date_start == pd.Timestamp('2025-01-01'), drop=True)
    report = report.where(report.date_end == pd.Timestamp('2025-12-31'), drop=True)
    report = report.where(report.date_freq == 48, drop=True)
    report = report.where(report.index_postprocess > 0, drop=True)
    report['date_current'] = report.date_start + pd.Timedelta(
        '1h',
    ) * report.date_freq * (report.index_postprocess - 1)
    iver = pathlib.Path(__file__).parent / 'f2025.sh'
    for exp, date_current in zip(
        report.exp.to_numpy(), report.date_current.to_numpy(), strict=True,
    ):
        time = pd.Timestamp(date_current)
        logger.info('Running IVER for %s until %s', exp, time)
        subprocess.run(  # noqa: S603
            ['/bin/sh', str(iver), exp, str(time.month), str(time.day)],
            check=True,
        )


def run_iver_sf2025(wdir):
    wdir = WorkingDirectory(wdir)
    report = wdir.get_report().isel(time=-1).load()
    report = report.where(report.experiment_type == 'fc', drop=True)
    report = report.where(report.date_start == pd.Timestamp('2025-01-01'), drop=True)
    report = report.where(report.date_end == pd.Timestamp('2025-12-27'), drop=True)
    report = report.where(report.date_freq == 144, drop=True)
    report = report.where(report.index_postprocess > 0, drop=True)
    report['date_current'] = report.date_start + pd.Timedelta(
        '1h',
    ) * report.date_freq * (report.index_postprocess - 1)
    iver = pathlib.Path(__file__).parent / 'sf2025.sh'
    for exp, date_current in zip(
        report.exp.to_numpy(), report.date_current.to_numpy(), strict=True,
    ):
        time = pd.Timestamp(date_current)
        logger.info('Running IVER for %s until %s', exp, time)
        subprocess.run(  # noqa: S603
            ['/bin/sh', str(iver), exp, str(time.month), str(time.day)],
            check=True,
        )


def run_iver(wdir, iver_config):
    match iver_config:
        case 'f2025':
            run_iver_f2025(wdir)
        case 'sf2025':
            run_iver_sf2025(wdir)
        case _:
            message = f'Unknown IVER configuration: {iver_config}'
            raise ValueError(message)
