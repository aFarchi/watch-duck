import logging
import subprocess  # noqa: S404

import numpy as np
import pandas as pd
import xarray as xr

from watch_duck.common.live_progress import overall_progres_bar
from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def get_report_active_experiment(wdir, experiment, now):
    ds = wdir.get_experiment_progress(experiment)
    time = ds.time.to_numpy()
    indices = time.searchsorted(np.unique(time))
    ds = ds.isel(time=indices)
    ds = ds.isel(time=slice(-256, None)).load()
    dr = pd.date_range(end=now, freq='1h', periods=241)
    ds = ds.reindex(time=dr, method='nearest', tolerance='30m').ffill(dim='time')
    ds = ds.drop_vars(
        var
        for var in ds.data_vars
        if var
        not in {
            'state',
            'state_preprocess',
            'state_main',
            'state_postprocess',
            'index_preprocess',
            'index_main',
            'index_postprocess',
        }
    )
    ds = ds.fillna(-1).astype(int)
    attributes = xr.Dataset(
        data_vars={
            'date_start': (('exp',), [pd.Timestamp(ds.date_start)]),
            'date_end': (('exp',), [pd.Timestamp(ds.date_end)]),
            'date_freq': (('exp',), [ds.date_freq]),
            'experiment_type': (('exp',), [ds.experiment_type]),
            'suite': (('exp',), [ds.suite]),
        },
        coords={
            'exp': ('exp', [experiment]),
        },
    )
    ds = ds.expand_dims(exp=[experiment]).drop_attrs(deep=True)
    return xr.merge((ds, attributes))


def get_report_active(wdir, now):
    with overall_progres_bar() as progress:
        report = [
            get_report_active_experiment(wdir, experiment, now)
            for experiment in progress.track(
                wdir.get_active_experiments(name=None, experiment_type=None),
                description='preparing report (active exp.)',
            )
        ]
    return xr.concat(report, dim='exp')


def get_report_finished(wdir, now):
    active_paths = wdir.get_all_active_arxiv_paths()
    experiments = {}
    with overall_progres_bar() as progress:
        for active_path in progress.track(
            active_paths,
            description='preparing report (finished exp.)',
        ):
            suite, date = active_path.stem.split('_', 1)
            date = pd.to_datetime(date, format='%Y_%m_%d_%H_%M_%S').floor('h')
            if now - date > pd.Timedelta('244h'):
                continue
            if suite not in experiments:
                experiments[suite] = {}
                experiments[suite]['date'] = date
                experiments[suite]['experiments'] = {}
            experiments[suite]['date'] = max(date, experiments[suite]['date'])
            with active_path.open('r', encoding=None) as file:
                for line in file:
                    experiment_name, experiment_type = line.strip().split(': ')
                    if experiment_name not in experiments[suite]['experiments']:
                        experiments[suite]['experiments'][experiment_name] = {
                            'experiment_type': experiment_type,
                            'suite': suite,
                            'date': date,
                        }
                    experiments[suite]['experiments'][experiment_name]['date'] = max(
                        experiments[suite]['experiments'][experiment_name]['date'],
                        date,
                    )
    finished_experiments = {
        experiment_name: experiments[suite]['experiments'][experiment_name]
        for suite in experiments
        for experiment_name in experiments[suite]['experiments']
        if experiments[suite]['experiments'][experiment_name]['date']
        < experiments[suite]['date']
    }
    for experiment_name in finished_experiments:
        try:
            ds = wdir.get_experiment_progress(experiment_name)
            finished_experiments[experiment_name] |= {
                'date_start': pd.Timestamp(ds.date_start),
                'date_end': pd.Timestamp(ds.date_end),
                'date_freq': ds.date_freq,
            }
        except FileNotFoundError:
            finished_experiments[experiment_name] |= {
                'date_start': pd.NaT,
                'date_end': pd.NaT,
                'date_freq': np.nan,
            }
    return xr.Dataset(
        data_vars={
            f'finished_{key}': (
                ('finished_exp',),
                [
                    finished_experiments[experiment_name][key]
                    for experiment_name in finished_experiments
                ],
            )
            for key in (
                'experiment_type',
                'suite',
                'date',
                'date_start',
                'date_end',
                'date_freq',
            )
        },
        coords={
            'finished_exp': ('finished_exp', list(finished_experiments)),
        },
    )


def write_report(wdir):
    wdir = WorkingDirectory(wdir)
    now = pd.Timestamp.now().floor('h')
    report_active = get_report_active(wdir, now)
    report_finished = get_report_finished(wdir, now)
    total_report = xr.merge((report_active, report_finished))
    wdir.save_report(total_report)


def download_report(wdir, space, name):
    wdir = WorkingDirectory(wdir)
    with wdir.working_directory():
        subprocess.run(
            [  # noqa: S607
                'sitesctl',
                'site',
                '--space',
                space,
                '--name',
                name,
                'content',
                'download',
                '--path',
                'report.h5',
                '--yes',
            ],
            check=True,
        )
    report = wdir.wdir / space / name / 'report.h5'
    report.rename(wdir.wdir / 'report.h5')
    (wdir.wdir / space / name).rmdir()
    (wdir.wdir / space).rmdir()


def upload_report(wdir, space, name):
    wdir = WorkingDirectory(wdir)
    with wdir.working_directory():
        subprocess.run(
            [  # noqa: S607
                'sitesctl',
                'site',
                '--space',
                space,
                '--name',
                name,
                'content',
                'upload',
                '--source',
                'report.h5',
                '--yes',
            ],
            check=True,
        )
