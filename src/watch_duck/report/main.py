import pandas as pd
import xarray as xr

from watch_duck.common.live_progress import overall_progres_bar
from watch_duck.common.wdir import WorkingDirectory


def get_experiment_report(wdir, experiment, now):
    ds = wdir.get_experiment_progress(experiment)
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


def get_report(wdir):
    now = pd.Timestamp.now().floor('h')
    with overall_progres_bar() as progress:
        report = [
            get_experiment_report(wdir, experiment, now)
            for experiment in progress.track(
                wdir.get_active_experiments(name=None, experiment_type=None),
                description='preparing report',
            )
        ]
    return xr.concat(report, dim='exp')


def write_report(wdir):
    wdir = WorkingDirectory(wdir)
    report = get_report(wdir)
    wdir.save_report(report)
