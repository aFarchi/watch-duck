import logging
import subprocess  # noqa: S404


import pandas as pd
import xarray as xr

from watch_duck.common.live_progress import overall_progres_bar
from watch_duck.common.wdir import WorkingDirectory

logger = logging.getLogger(__name__)


def get_experiment_report(wdir, experiment, now):
    ds = wdir.get_experiment_progress(experiment).isel(time=slice(-256, None)).load()
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


def get_coord(ds, name):
    return ds[name].to_numpy() if name in ds.coords else []


def get_data_var(ds, name):
    return ds[name].to_numpy() if name in ds else []


def get_finished_exp(now, previous_report, report):
    exp_current = get_coord(report, 'exp')
    exp_previous = get_coord(previous_report, 'exp')
    finished_exp_current = list(set(exp_previous) - set(exp_current))
    finished_exp_previous = get_coord(previous_report, 'finished_exp')
    finished_date_current = [now] * len(finished_exp_current)
    finished_date_previous = get_data_var(previous_report, 'finished_date')
    finished_type_current = previous_report.sel(exp=finished_exp_current).experiment_type.to_numpy()
    finished_type_previous = get_data_var(previous_report, 'finished_type')
    finished_suite_current = previous_report.sel(exp=finished_exp_current).suite.to_numpy()
    finished_suite_previous = get_data_var(previous_report, 'finished_suite')
    finished_exp = xr.Dataset(
        data_vars={
            'finished_date': (('finished_exp',), [*finished_date_previous, *finished_date_current]),
            'finished_type': (('finished_exp',), [*finished_type_previous, *finished_type_current]),
            'finished_suite': (('finished_exp',), [*finished_suite_previous, *finished_suite_current]),
        },
        coords={
            'finished_exp': ('finished_exp', [*finished_exp_previous, *finished_exp_current]),
        },
    )
    return finished_exp.where(now.to_datetime64() - finished_exp.finished_date < pd.Timedelta(hours=240), drop=True)


def get_report_diff(previous_report, report):
    exp_current = get_coord(report, 'exp')
    exp_previous = get_coord(previous_report, 'exp')
    exp_diff = list(set(exp_previous) - set(exp_current))
    return previous_report.sel(exp=exp_diff) if exp_diff else None


def get_report(now, wdir, previous_report):
    with overall_progres_bar() as progress:
        report = [
            get_experiment_report(wdir, experiment, now)
            for experiment in progress.track(
                wdir.get_active_experiments(name=None, experiment_type=None),
                description='preparing report',
            )
        ]
    report = xr.concat(report, dim='exp')
    report = xr.merge((report, get_finished_exp(now, previous_report, report)))
    return report


def get_previous_report(wdir):
    try:
        previous_report = wdir.get_report().isel(time=-1).load()
        previous_report.close()
    except FileNotFoundError:
        previous_report = xr.Dataset()
    return previous_report


def write_report(wdir):
    wdir = WorkingDirectory(wdir)
    now = pd.Timestamp.now().floor('h')
    previous_report = get_previous_report(wdir)
    report = get_report(now, wdir, previous_report)
    wdir.save_report(report)
    report_diff = get_report_diff(previous_report, report)
    if report_diff is not None:
        wdir.save_report_diff(report_diff, now)


def download_report(wdir):
    wdir = WorkingDirectory(wdir)
    with wdir.working_directory():
        subprocess.run(  # noqa: S603
            [
                'sitesctl',
                'site',
                '--space',
                'daaf',
                '--name',
                'iver',
                'content',
                'download',
                '--path',
                'report.h5',
                '--yes',
            ],
            check=True,
        )
    report = wdir.wdir / 'daaf/iver/report.h5'
    report.rename(wdir.wdir / 'report.h5')
    (wdir.wdir / 'daaf/iver').rmdir()
    (wdir.wdir / 'daaf').rmdir()
