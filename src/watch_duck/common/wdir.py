import contextlib
import logging
import os
import pathlib

import xarray as xr

logger = logging.getLogger(__name__)


def to_zarr(ds, path, *, overwrite=False):
    if path.exists() and not overwrite:
        ds.to_zarr(path, append_dim='time', mode='a', consolidated=False)
    else:
        ds.to_zarr(path, mode='w', consolidated=False)


class WorkingDirectory:
    def __init__(self, wdir):
        self.wdir = pathlib.Path(wdir)

    @contextlib.contextmanager
    def working_directory(self):
        old_cwd = pathlib.Path.cwd()
        os.chdir(self.wdir)
        try:
            yield self
        finally:
            os.chdir(old_cwd)

    def get_log_files(self, suites):
        log_files = sorted(self.wdir.glob('log_in/*.log'))
        return [
            log_file
            for log_file in log_files
            if log_file.name.split('_', 1)[0] in suites
        ]

    def get_active_path(self, name):
        path_active = self.wdir / f'active/{name}.txt'
        path_active.parent.mkdir(parents=True, exist_ok=True)
        return path_active

    def get_all_active_paths(self):
        return sorted(self.wdir.glob('active/*.txt'))

    def save_active_experiments(self, name, active_experiments):
        path_active = self.get_active_path(name)
        with path_active.open('w', encoding=None) as f:
            for experiment_name, experiment_type in active_experiments.items():
                f.write(f'{experiment_name}: {experiment_type}\n')

    def get_active_experiments(self, name, experiment_type):
        if name is None:
            path_active_files = self.get_all_active_paths()
        else:
            path_active_files = [self.get_active_path(name)]
        experiments = []
        for path_active in path_active_files:
            with path_active.open('r', encoding=None) as file:
                for line in file:
                    experiment_name, the_type = line.strip().split(': ')
                    if experiment_type is None or the_type == experiment_type:
                        experiments.append(experiment_name)
        return experiments

    def save_experiment_state(self, name, ds):
        path_state = self.wdir / f'state/{name}.zarr'
        path_state.parent.mkdir(parents=True, exist_ok=True)
        try:
            to_zarr(ds, path_state, overwrite=False)
        except ValueError:
            logger.warning('removing previous state values for experiment "%s"', name)
            to_zarr(ds, path_state, overwrite=True)

    def save_experiment_progress(self, name, ds):
        path_progress = self.wdir / f'progress/{name}.zarr'
        path_progress.parent.mkdir(parents=True, exist_ok=True)
        to_zarr(ds, path_progress, overwrite=False)

    def get_experiment_progress(self, name):
        path_progress = self.wdir / f'progress/{name}.zarr'
        return xr.open_zarr(path_progress, consolidated=False)

    def save_report(self, ds):
        path_report = self.wdir / 'report.h5'
        path_report.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(path_report, engine='h5netcdf')

    def get_report(self):
        path_report = self.wdir / 'report.h5'
        if not path_report.exists():
            message = f'Report file does not exist: {path_report}'
            raise FileNotFoundError(message)
        return xr.open_dataset(path_report, engine='h5netcdf')

    def save_report_diff(self, ds, now):
        path_report_diff = (
            self.wdir / f'report_diff/{now.strftime("%Y_%m_%d_%H_%M_%S")}.h5'
        )
        path_report_diff.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(path_report_diff, engine='h5netcdf')

    def get_report_diff_files(self):
        return sorted(self.wdir.glob('report_diff/*.h5'))
