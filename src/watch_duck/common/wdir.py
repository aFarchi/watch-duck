import contextlib
import logging
import os
import pathlib

import pandas as pd
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
        log_files = sorted(self.wdir.glob('log/*.log'))
        return [
            log_file
            for log_file in log_files
            if log_file.name.split('_', 1)[0] in suites
        ]

    def archive_log_file(self, log_file):
        path_archive = self.wdir / 'log/arxiv' / log_file.name
        path_archive.parent.mkdir(parents=True, exist_ok=True)
        log_file.rename(path_archive)

    def get_active_path(self, name, date):
        if date is None:
            path_active = self.wdir / f'active/{name}.txt'
        else:
            path_active = self.wdir / f'active/arxiv/{name}_{date}.txt'
        path_active.parent.mkdir(parents=True, exist_ok=True)
        return path_active

    def get_all_active_paths(self):
        return sorted(self.wdir.glob('active/*.txt'))

    def get_all_active_arxiv_paths(self):
        return sorted(self.wdir.glob('active/arxiv/*.txt'))

    def save_active_experiments(self, name, date, active_experiments):
        path_active = self.get_active_path(name, date.strftime('%Y_%m_%d_%H_%M_%S'))
        with path_active.open('w', encoding=None) as f:
            for experiment_name, experiment_type in active_experiments.items():
                f.write(f'{experiment_name}: {experiment_type}\n')
        path_latest_active = self.get_active_path(name, None)
        if path_latest_active.exists():
            path_latest_active.unlink()
        path_latest_active.symlink_to(path_active)

    def get_active_experiments(self, name, experiment_type):
        if name is None:
            path_active_files = self.get_all_active_paths()
        else:
            path_active_files = [self.get_active_path(name, None)]
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

    def get_report(self, **isel):
        path_report = self.wdir / 'report.h5'
        if not path_report.exists():
            message = f'Report file does not exist: {path_report}'
            raise FileNotFoundError(message)
        with xr.open_dataset(path_report, engine='h5netcdf') as ds:
            return ds.isel(**isel).load()

    def save_report_diff(self, ds, now):
        path_report_diff = (
            self.wdir / f'report_diff/{now.strftime("%Y_%m_%d_%H_%M_%S")}.h5'
        )
        path_report_diff.parent.mkdir(parents=True, exist_ok=True)
        ds.to_netcdf(path_report_diff, engine='h5netcdf')

    def get_report_diff_files(self):
        return sorted(self.wdir.glob('report_diff/*.h5'))

    def clean_log_arxiv(self, now):
        log_arxiv_dir = self.wdir / 'log/arxiv'
        if log_arxiv_dir.exists():
            for log_file in log_arxiv_dir.glob('*.log'):
                _, date = log_file.stem.split('_', 1)
                date = pd.to_datetime(date, format='%Y_%m_%d_%H_%M_%S')
                if now - date > pd.Timedelta('30d'):
                    logger.info('removing log file: %s', log_file)
                    log_file.unlink()

    def clean_active_arxiv(self, now):
        active_arxiv_dir = self.wdir / 'active/arxiv'
        if active_arxiv_dir.exists():
            for active_file in active_arxiv_dir.glob('*.txt'):
                _, date = active_file.stem.split('_', 1)
                date = pd.to_datetime(date, format='%Y_%m_%d_%H_%M_%S')
                if now - date > pd.Timedelta('30d'):
                    logger.info('removing active file: %s', active_file)
                    active_file.unlink()

    def clean_slurm_arxiv(self, now):
        slurm_dir = self.wdir / 'slurm'
        if slurm_dir.exists():
            for slurm_file in slurm_dir.glob('*.out'):
                date = pd.Timestamp(slurm_file.stat().st_mtime, unit='s')
                if now - date > pd.Timedelta('30d'):
                    logger.info('removing slurm file: %s', slurm_file)
                    slurm_file.unlink()


def clean_iver(profile):
    config_file = pathlib.Path('~').expanduser() / f'.iver.{profile}'
    with pathlib.Path(config_file).open('r', encoding=None) as f:
        iver_path = pathlib.Path(f.readline().strip())
    for iver_file in iver_path.glob('stats/verify_*_0001_tmp*.nc'):
        logger.info('removing IVER file: %s', iver_file)
        iver_file.unlink()


def clean_all(wdir, profiles):
    wdir = WorkingDirectory(wdir)
    now = pd.Timestamp.now()
    wdir.clean_log_arxiv(now)
    wdir.clean_active_arxiv(now)
    wdir.clean_slurm_arxiv(now)
    for profile in profiles:
        clean_iver(profile)
