import pandas as pd

from watch_duck.common.live_progress import overall_progres_bar
from watch_duck.common.state import decode_state


def get_current_progress(ds, progress, nodes):
    for node in nodes:
        progress[f'index_{node}'] = ds[f'current_{node}'].isel(time=-1).item()
        progress[f'date_{node}'] = (
            progress['date_start'] + progress[f'index_{node}'] * progress['date_freq']
        )
    return progress


def get_current_speed(
    ds,
    progress,
    nodes,
    delta_t,
    exclude_aborted,
    exclude_suspended,
):
    delta_t = pd.Timedelta(delta_t)
    actual_delta_t = pd.Timedelta('0h')
    time_diff = ds.time.diff(dim='time').to_numpy()
    index = len(ds.time) - 1
    if decode_state(ds.state.isel(time=index).item()) != 'aborted':
        while actual_delta_t < delta_t and index > 0:
            index -= 1
            if (
                exclude_aborted
                and decode_state(ds.state.isel(time=index).item()) == 'aborted'
            ):
                continue
            if (
                exclude_suspended
                and decode_state(ds.state.isel(time=index).item()) == 'suspended'
            ):
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


def get_experiment_summary(
    wdir,
    experiment,
    delta_t,
    exclude_aborted,
    exclude_suspended,
):
    ds = wdir.get_experiment_progress(experiment)
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
    progress = get_current_progress(ds, progress, nodes)
    progress = get_current_speed(
        ds,
        progress,
        nodes,
        delta_t,
        exclude_aborted,
        exclude_suspended,
    )
    return get_eta_experiment(progress, nodes)


def get_summary(
    wdir,
    suite,
    experiment_type,
    delta_t,
    exclude_aborted,
    exclude_suspended,
):
    summary = {}
    with overall_progres_bar() as progress:
        for experiment in progress.track(
            wdir.get_active_experiments(suite, experiment_type),
            description='preparing report',
        ):
            summary[experiment] = get_experiment_summary(
                wdir,
                experiment,
                delta_t,
                exclude_aborted,
                exclude_suspended,
            )
    return summary
