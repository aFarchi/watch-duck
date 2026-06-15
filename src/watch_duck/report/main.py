import logging

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


def get_report(wdir, previous_report):
    now = pd.Timestamp.now().floor('h')
    with overall_progres_bar() as progress:
        report = [
            get_experiment_report(wdir, experiment, now)
            for experiment in progress.track(
                wdir.get_active_experiments(name=None, experiment_type=None),
                description='preparing report',
            )
        ]
    report = xr.concat(report, dim='exp')
    exp_diff = {
        experiment: now.strftime('%Y-%m-%dT%H:%M:%S')
        for experiment in (
            previous_report.exp.to_numpy() if 'exp' in previous_report.coords else []
        )
        if experiment not in report.exp.to_numpy()
    }
    updated_exp_diff = {
        key: value
        for key, value in previous_report.attrs.items()
        if now - pd.Timestamp(value) < pd.Timedelta(hours=240)
    } | exp_diff
    report_diff = (
        previous_report.sel(exp=list(exp_diff.keys())).isel(time=-1)
        if 'exp' in previous_report.coords
        else xr.Dataset()
    )
    wdir.save_report_diff(report_diff, now)
    return report.assign_attrs(**updated_exp_diff)


def get_previous_report(wdir):
    try:
        return wdir.get_report()
    except FileNotFoundError:
        return xr.Dataset()


def write_report(wdir):
    wdir = WorkingDirectory(wdir)
    previous_report = get_previous_report(wdir).load()
    previous_report.close()
    report = get_report(wdir, previous_report)
    wdir.save_report(report)
