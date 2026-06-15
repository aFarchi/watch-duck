import logging
import pathlib
import subprocess  # noqa: S404

import pandas as pd
import xarray as xr

from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def iver(exp, tag, date_start, date_end, date_freq, profile, check):
    iver_file = pathlib.Path(__file__).parent / 'iver.sh'
    subprocess.run(  # noqa: S603
        [
            '/bin/sh',
            str(iver_file),
            exp,
            tag,
            date_start.strftime('%m,%d,%Y'),
            date_end.strftime('%m,%d,%Y'),
            str(int(date_freq // 24)),
            profile,
        ],
        check=check,
    )


def run_partial_iver(wdir, date_start, date_end, date_freq, profile):
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
            exp=exp,
            tag='tmp',
            date_start=date_start,
            date_end=time,
            date_freq=date_freq,
            profile=profile,
            check=False,
        )


def run_full_iver(report, date_start, date_end, date_freq, profile):
    report = report.where(report.experiment_type == 'fc', drop=True)
    report = report.where(report.date_start == date_start, drop=True)
    report = report.where(report.date_end == date_end, drop=True)
    report = report.where(report.date_freq == date_freq, drop=True)
    failed_experiments = []
    for exp in report.exp.to_numpy():
        logger.info('Running full IVER for %s', exp)
        try:
            iver(
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
    return failed_experiments


def run_full_iver_all(wdir, profiles):
    wdir = WorkingDirectory(wdir)
    report_diff_files = wdir.get_report_diff_files()
    failed_experiments = []
    for report_diff_file in report_diff_files:
        report = xr.open_dataset(report_diff_file, engine='h5netcdf').load()
        report.close()
        for profile, config in profiles.items():
            failed_experiments.extend(
                run_full_iver(
                    report=report,
                    profile=profile,
                    **config,
                ),
            )
        report_diff_file.unlink()
    if failed_experiments:
        logger.warning('Failed experiments:')
        for exp in failed_experiments:
            logger.warning('    %s', exp)
        raise subprocess.CalledProcessError


def run_iver(*, partial, profiles, **kwargs):
    if partial:
        for profile, config in profiles.items():
            run_partial_iver(profile=profile, **config, **kwargs)
    else:
        run_full_iver(**kwargs)
