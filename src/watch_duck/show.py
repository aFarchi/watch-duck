import logging
import pathlib

import pandas as pd
import xarray as xr
from rich.console import Console
import rich.progress
from rich.table import Table

logger = logging.getLogger(__name__)


def decode_state(state):
    return {
        0: 'complete',
        1: 'queued',
        2: 'active',
        3: 'aborted',
        4: 'suspended',
        5: 'submitted',
    }[state]


def get_active_experiments(wdir, experiment_type):
    wdir = pathlib.Path(wdir) / 'active'
    experiments = []
    for filename in wdir.glob('*.txt'):
        with filename.open('r', encoding=None) as file:
            for line in file:
                name, the_type = line.strip().split(': ')
                if the_type == experiment_type:
                    experiments.append(name)
    return experiments


def get_progress_experiment(ds, progress, nodes):
    for node in nodes:
        progress[f'index_{node}'] = ds[f'current_{node}'].isel(time=-1).item()
        progress[f'date_{node}'] = (
            progress['date_start'] + progress[f'index_{node}'] * progress['date_freq']
        )
    return progress


def get_speed_experiment(
    ds,
    progress,
    nodes,
    *,
    delta_t='48h',
    exclude_aborted=True,
    exclude_suspended=True,
):
    delta_t = pd.Timedelta(delta_t)
    actual_delta_t = pd.Timedelta('0h')
    time_diff = ds.time.diff(dim='time').to_numpy()
    index = len(ds.time) - 1
    while actual_delta_t < delta_t and index > 0:
        index -= 1
        if exclude_aborted and ds.state.isel(time=index).item() == 3:
            continue
        if exclude_suspended and ds.state.isel(time=index).item() == 4:
            continue
        actual_delta_t += pd.Timedelta(time_diff[index])
    for node in nodes:
        progress[f'speed_{node}_it_day'] = (
            (progress[f'index_{node}'] - ds[f'current_{node}'].isel(time=index).item())
            / (actual_delta_t / pd.Timedelta('1D'))
            if actual_delta_t > pd.Timedelta('0h')
            else 0
        )
        progress[f'speed_{node}_day_day'] = (
            progress[f'speed_{node}_it_day']
            * progress['date_freq']
            / pd.Timedelta('1D')
        )
    return progress


def get_eta_experiment(progress, nodes):
    for node in nodes:
        if progress[f'speed_{node}_day_day'] > 0:
            progress[f'remaining_{node}'] = (
                progress['date_end'] - progress[f'date_{node}']
            ) / progress[f'speed_{node}_day_day']
            progress[f'eta_{node}'] = pd.Timestamp.now() + progress[f'remaining_{node}']
        else:
            progress[f'remaining_{node}'] = pd.NaT
            progress[f'eta_{node}'] = pd.NaT
    return progress


def get_experiment_progress(wdir, experiment):
    logger.debug('Getting progress of experiment: "%s"', experiment)
    wdir = pathlib.Path(wdir) / 'progress'
    filename = wdir / f'{experiment}.zarr'
    ds = xr.open_zarr(filename, consolidated=False).load()
    progress = {
        'experiment_type': ds.attrs['experiment_type'],
        'date_start': pd.Timestamp(ds.attrs['date_start']),
        'date_end': pd.Timestamp(ds.attrs['date_end']),
        'date_freq': ds.attrs['date_freq'] * pd.Timedelta('1h'),
        'state': decode_state(ds.state.isel(time=-1).item()),
    }
    progress['total'] = (progress['date_end'] - progress['date_start']) // progress[
        'date_freq'
    ] + 1
    if ds.attrs['experiment_type'] == 'fc':
        nodes = ('ini', 'fc', 'lag')
    elif ds.attrs['experiment_type'] in {'lw', 'elda'}:
        nodes = ('obs', 'main', 'lag')
    progress = get_progress_experiment(ds, progress, nodes)
    progress = get_speed_experiment(ds, progress, nodes)
    return get_eta_experiment(progress, nodes)


def format_state(state):
    color = {
        'complete': 'bright_yellow',
        'queued': 'bright_cyan',
        'active': 'green',
        'aborted': 'red',
        'suspended': 'yellow',
        'submitted': 'bright_cyan',
    }
    return f'[{color[state]}]{state}[/]'


def format_progress(index, total):
    return f'{index} / {total} ({100 * index / total:.2f}%)'


def format_speed(speed):
    if speed > 0:
        return f'[green]{speed:.2f}[/]'
    return f'[red]{speed:.2f}[/]'


def format_remaining(speed, remaining):
    remaining = remaining.ceil('h')
    if speed > 0:
        return f'[green]{remaining}[/]'
    return f'[red]{remaining}[/]'


def format_eta(speed, eta):
    eta = eta.ceil('h')
    if speed > 0:
        return f'[green]{eta}[/]'
    return f'[red]{eta}[/]'


def overall_progres_bar():
    return rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn('[green]{task.description}'),
        rich.progress.BarColumn(),
        rich.progress.MofNCompleteColumn(),
        rich.progress.TextColumn('•'),
        rich.progress.TaskProgressColumn(),
        rich.progress.TextColumn('• Elapsed:'),
        rich.progress.TimeElapsedColumn(),
        rich.progress.TextColumn('• Remaining:'),
        rich.progress.TimeRemainingColumn(),
    )


def prepare_report(wdir, experiment_type, wrt):
    report = []
    with overall_progres_bar() as progress:
        for experiment in progress.track(
            get_active_experiments(wdir, experiment_type),
            description='preparing report',
        ):
            progress = get_experiment_progress(wdir, experiment)
            report.append({
                'experiment': experiment,
                'state': format_state(progress['state']),
                f'progress_{wrt}': format_progress(progress[f'index_{wrt}'], progress['total']),
                f'speed_{wrt}_it_day': format_speed(progress[f'speed_{wrt}_it_day']),
                f'speed_{wrt}_day_day': format_speed(progress[f'speed_{wrt}_day_day']),
                'time_remaining': format_remaining(
                    progress[f'speed_{wrt}_day_day'], progress[f'remaining_{wrt}'],
                ),
                'eta': format_eta(progress[f'speed_{wrt}_day_day'], progress[f'eta_{wrt}']),
            })
    return report


def show_progress(wdir, experiment_type, wrt='lag'):
    table = Table(title=f'Active "{experiment_type}" Experiments')
    table.add_column('ID', style='cyan')
    table.add_column('State', style='green')
    table.add_column(f'Progress on "{wrt}"', style='yellow', justify='right')
    table.add_column(f'Speed (it/day)', style='magenta', justify='right')
    table.add_column(f'Speed (day/day)', style='magenta', justify='right')
    table.add_column('Time remaining', style='magenta', justify='right')
    table.add_column('ETA', style='magenta', justify='right')
    for experiment in prepare_report(wdir, experiment_type, wrt):
        table.add_row(
            experiment['experiment'],
            experiment['state'],
            experiment[f'progress_{wrt}'],
            experiment[f'speed_{wrt}_it_day'],
            experiment[f'speed_{wrt}_day_day'],
            experiment['time_remaining'],
            experiment['eta'],
        )
    console = Console()
    console.print(table)
