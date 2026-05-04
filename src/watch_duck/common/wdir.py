import pathlib

import xarray as xr


def to_zarr(ds, path):
    if path.exists():
        ds.to_zarr(path, append_dim='time', mode='a', consolidated=False)
    else:
        ds.to_zarr(path, mode='w', consolidated=False)


class WorkingDirectory:
    def __init__(self, wdir):
        self.wdir = pathlib.Path(wdir)
        self.path_log_in = self.wdir / 'log_in'
        self.path_log_arxiv = self.wdir / 'log_arxiv'

        self.path_log_in.mkdir(parents=True, exist_ok=True)
        self.path_log_arxiv.mkdir(parents=True, exist_ok=True)

    def get_log_files(self, suites):
        log_files = sorted(self.path_log_in.glob('*.log'))
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

    def archive_log_file(self, log_file):
        new_name = self.path_log_arxiv / log_file.name
        log_file.rename(new_name)

    def save_experiment_state(self, name, ds):
        path_state = self.wdir / f'state/{name}.zarr'
        path_state.parent.mkdir(parents=True, exist_ok=True)
        to_zarr(ds, path_state)

    def save_experiment_progress(self, name, ds):
        path_progress = self.wdir / f'progress/{name}.zarr'
        path_progress.parent.mkdir(parents=True, exist_ok=True)
        to_zarr(ds, path_progress)

    def get_experiment_progress(self, name):
        path_progress = self.wdir / f'progress/{name}.zarr'
        return xr.open_zarr(path_progress, consolidated=False).load()

    def get_summary_path(self):
        return self.wdir / 'summary.csv'
