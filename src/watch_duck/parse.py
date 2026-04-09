import logging
import pathlib
import time

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)


def encode_state(state):
    return {
        'complete': 0,
        'queued': 1,
        'active': 2,
        'aborted': 3,
        'suspended': 4,
        'submitted': 5,
    }[state]


def get_state_family(prefix, family):
    state = {prefix: encode_state(family['state'])}
    if 'children' in family:
        for key, value in family['children'].items():
            state.update(get_state_family(f'{prefix}/{key}', value))
    return state


def check_frequencies(freq_00, freq_12, freq):
    if freq_00 != 2 * freq or freq_12 != 2 * freq:
        message = f"""inconsistent date frequencies:
    freq_00={freq_00},
    freq_12={freq_12},
    freq={freq}
"""
        raise ValueError(message)


def current_date_to_index(progress):
    date_start = progress['date_start']
    date_freq = progress['date_freq']
    return {
        key: value
        if not key.startswith('current_')
        else (value - date_start) // date_freq
        for key, value in progress.items()
    }


def encode_state_nodes(nodes, groups):
    return {
        f'state_{node}_{group}': encode_state(nodes[node]['children'][group]['state'])
        for node in nodes
        for group in groups
    }


def merge_progress(progress_00, progress_12, nodes):
    if progress_00['date_start'] < progress_12['date_start']:
        date_start = progress_00['date_start']
        date_end = progress_12['date_end']
        date_freq = progress_12['date_start'] - progress_00['date_start']
    else:
        date_start = progress_12['date_start']
        date_end = progress_00['date_end']
        date_freq = progress_00['date_start'] - progress_12['date_start']
    check_frequencies(progress_00['date_freq'], progress_12['date_freq'], date_freq)
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
    } | {
        f'current_{key}': min(
            progress_00[f'current_{key}'],
            progress_12[f'current_{key}'],
        )
        for key in nodes
    }


def get_progress_fc_1_experiment(nodes, group):
    step = int(group) * pd.Timedelta('1h')
    date_start = pd.Timestamp(nodes['ini']['children'][group]['ymd_start']) + step
    date_end = pd.Timestamp(nodes['ini']['children'][group]['ymd_end']) + step
    date_freq = int(nodes['ini']['children'][group]['ymd_freq']) * pd.Timedelta('1D')
    date_ini = pd.Timestamp(nodes['ini']['children'][group]['ymd_current']) + step
    date_fc = pd.Timestamp(nodes['fc']['children'][group]['ymd_current']) + step
    date_lag = pd.Timestamp(nodes['lag']['children'][group]['ymd_current']) + step
    if nodes['ini']['children'][group]['state'] == 'complete':
        date_ini += date_freq
        nodes['ini']['children'][group]['state'] = 'queued'
    if nodes['fc']['children'][group]['state'] == 'complete':
        date_fc += date_freq
        nodes['fc']['children'][group]['state'] = 'queued'
    if nodes['lag']['children'][group]['state'] == 'complete':
        date_lag += date_freq
        nodes['lag']['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_ini': date_ini,
        'current_fc': date_fc,
        'current_lag': date_lag,
    } | encode_state_nodes(nodes, groups=[group])


def get_progress_fc_2_experiment(nodes):
    progress_00 = get_progress_fc_1_experiment(nodes, '00')
    progress_12 = get_progress_fc_1_experiment(nodes, '12')
    progress = merge_progress(progress_00, progress_12, nodes=('ini', 'fc', 'lag'))
    return progress | encode_state_nodes(nodes, groups=('00', '12'))


def get_progress_fc_experiment(experiment):
    nodes = {
        'ini': experiment['children']['fc']['children']['main']['children']['inigroup'],
        'fc': experiment['children']['fc']['children']['main']['children']['fcgroup'],
        'lag': experiment['children']['fc']['children']['lag'],
    }
    groups = list(nodes['ini']['children'].keys())
    if len(groups) == 1:
        progress = get_progress_fc_1_experiment(nodes, groups[0])
    else:
        progress = get_progress_fc_2_experiment(nodes)
    progress['state'] = encode_state(experiment['state'])
    progress['experiment_type'] = 'fc'
    return progress


def get_progress_an_1_experiment(nodes, kind, group):
    step = int(group[len(kind) :]) * pd.Timedelta('1h')
    date_start = pd.Timestamp(nodes['obs']['children'][group]['ymd_start']) + step
    date_end = pd.Timestamp(nodes['obs']['children'][group]['ymd_end']) + step
    date_freq = int(nodes['obs']['children'][group]['ymd_freq']) * pd.Timedelta('1D')
    date_obs = pd.Timestamp(nodes['obs']['children'][group]['ymd_current']) + step
    date_main = pd.Timestamp(nodes['main']['children'][group]['ymd_current']) + step
    date_lag = pd.Timestamp(nodes['lag']['children'][group]['ymd_current']) + step
    if nodes['obs']['children'][group]['state'] == 'complete':
        date_obs += date_freq
        nodes['obs']['children'][group]['state'] = 'queued'
    if nodes['main']['children'][group]['state'] == 'complete':
        date_main += date_freq
        nodes['main']['children'][group]['state'] = 'queued'
    if nodes['lag']['children'][group]['state'] == 'complete':
        date_lag += date_freq
        nodes['lag']['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_obs': date_obs,
        'current_main': date_main,
        'current_lag': date_lag,
    } | encode_state_nodes(nodes, groups=[group])


def get_progress_an_2_experiment(nodes, kind):
    progress_00 = get_progress_an_1_experiment(nodes, kind, f'{kind}00')
    progress_12 = get_progress_an_1_experiment(nodes, kind, f'{kind}12')
    progress = merge_progress(progress_00, progress_12, nodes=('obs', 'main', 'lag'))
    return progress | encode_state_nodes(nodes, groups=(f'{kind}00', f'{kind}12'))


def get_progress_an_experiment(experiment, kind):
    nodes = {
        'obs': experiment['children']['an']['children']['obs'],
        'main': experiment['children']['an']['children']['main'],
        'lag': experiment['children']['an']['children']['lag'],
    }
    groups = list(nodes['obs']['children'].keys())
    if len(groups) == 1:
        progress = get_progress_an_1_experiment(nodes, kind, groups[0])
    else:
        progress = get_progress_an_2_experiment(nodes, kind)
    progress['state'] = encode_state(experiment['state'])
    progress['experiment_type'] = kind
    return progress


def check_fc_experiment(experiment):
    children = list(experiment['children'].keys())
    if children != ['fc', 'cancel']:
        message = f'unexpected experiment children: "{children}"'
        raise ValueError(message)
    children = list(experiment['children']['fc']['children'].keys())
    if children != ['make', 'main', 'lag']:
        message = f'unexpected experiment/fc children: "{children}"'
        raise ValueError(message)
    children = list(experiment['children']['fc']['children']['main']['children'].keys())
    if children != ['inigroup', 'fcgroup']:
        message = f'unexpected experiment/fc/main children: "{children}"'
        raise ValueError(message)
    ini_groups = list(
        experiment['children']['fc']['children']['main']['children']['inigroup'][
            'children'
        ].keys(),
    )
    fc_groups = list(
        experiment['children']['fc']['children']['main']['children']['fcgroup'][
            'children'
        ].keys(),
    )
    lag_groups = list(
        experiment['children']['fc']['children']['lag']['children'].keys(),
    )
    if ini_groups != fc_groups or ini_groups != lag_groups:
        message = f"""ini, fc, and lag groups should have the same children:
    ini_groups={ini_groups},
    fc_groups={fc_groups},
    lag_groups={lag_groups}
"""
        raise ValueError(message)
    if ini_groups not in [['00'], ['12'], ['00', '12']]:
        message = f'unexpected groups: "{ini_groups}"'
        raise ValueError(message)


def check_an_experiment(experiment, kind):
    children = list(experiment['children'].keys())
    if children != ['an', 'cancel']:
        message = f'unexpected experiment children: "{children}"'
        raise ValueError(message)
    children = list(experiment['children']['an']['children'].keys())
    if children != ['make', 'obs', 'main', 'lag', 'wsjobs']:
        message = f'unexpected experiment/an children: "{children}"'
        raise ValueError(message)
    obs_groups = list(
        experiment['children']['an']['children']['obs']['children'].keys(),
    )
    main_groups = list(
        experiment['children']['an']['children']['main']['children'].keys(),
    )
    lag_groups = list(
        experiment['children']['an']['children']['lag']['children'].keys(),
    )
    if obs_groups != main_groups or obs_groups != lag_groups:
        message = f"""obs, main, and lag groups should have the same children:
    obs_groups={obs_groups},
    main_groups={main_groups},
    lag_groups={lag_groups}
"""
        raise ValueError(message)
    if obs_groups not in [[f'{kind}00'], [f'{kind}12'], [f'{kind}00', f'{kind}12']]:
        message = f'unexpected groups: "{obs_groups}"'
        raise ValueError(message)


def get_experiment_type(experiment):
    main_type = next(iter(experiment['children'].keys()))
    if main_type == 'fc':
        check_fc_experiment(experiment)
        return 'fc'
    if main_type == 'an' and 'obs' in experiment['children']['an']['children']:
        obs_groups = list(
            experiment['children']['an']['children']['obs']['children'].keys(),
        )
        if obs_groups in [['lw00'], ['lw12'], ['lw00', 'lw12']]:
            check_an_experiment(experiment, kind='lw')
            return 'lw'
        if obs_groups in [['elda00'], ['elda12'], ['elda00', 'elda12']]:
            check_an_experiment(experiment, kind='elda')
            return 'elda'
        message = f'unexpected obs groups: "{obs_groups}"'
        raise ValueError(message)
    message = 'unable to determine experiment type'
    raise ValueError(message)


def get_progress_experiment(experiment):
    experiment_type = get_experiment_type(experiment)
    match experiment_type:
        case 'fc':
            progress = get_progress_fc_experiment(experiment)
        case 'lw' | 'elda':
            progress = get_progress_an_experiment(experiment, kind=experiment_type)
    return current_date_to_index(progress)


def parse_family_line(line):
    family_name = line.split('#', 1)[0].replace('family ', '').strip()
    family_state = line.split('#', 1)[1].split('state:', 1)[1].split(' ', 1)[0]
    return family_name, family_state


def parse_task_line(line):
    task_name = line.split('#', 1)[0].replace('task ', '').strip()
    task_state = line.split('#', 1)[1].split('state:', 1)[1].split(' ', 1)[0]
    return task_name, task_state


def parse_repeat_date_line(line):
    line = line.replace('repeat date YMD', '').strip()
    return {
        'ymd_start': line.split('#', 1)[0].split(' ')[0],
        'ymd_end': line.split('#', 1)[0].split(' ')[1],
        'ymd_freq': line.split('#', 1)[0].split(' ')[2],
        'ymd_current': line.split('#', 1)[1].strip()
        if '#' in line
        else line.split('#', 1)[0].split(' ')[0],
    }


def parse_family(log_file, state):
    family = {
        'state': state,
        'children': {},
    }
    for line in log_file:
        if line.startswith('family'):
            name, state = parse_family_line(line)
            family['children'][name] = parse_family(log_file, state)
        elif line.startswith('task'):
            name, state = parse_task_line(line)
            family['children'][name] = {'state': state}
        elif line.startswith('repeat date YMD'):
            family.update(parse_repeat_date_line(line))
        elif line.startswith('endfamily'):
            break
    return family


def parse_suite(log_file):
    full_log = False
    with pathlib.Path(log_file).open('r', encoding=None) as f:
        experiments = {}
        for line in f:
            if line.startswith('suite'):
                suite_name = line.split('#', 1)[0].replace('suite ', '').strip()
            elif line.startswith('# edit ECF_DATE'):
                suite_date = (
                    line.replace('# edit ECF_DATE', '').replace("'", '').strip()
                )
            elif line.startswith('# edit ECF_TIME'):
                suite_time = (
                    line.replace('# edit ECF_TIME', '').replace("'", '').strip() + ':00'
                )
            elif line.startswith('family'):
                name, state = parse_family_line(line)
                logger.info('found experiment "%s"', name)
                if name == 'experiment_launcher':
                    logger.info('skipping...')
                    parse_family(f, state)
                else:
                    experiments[name] = parse_family(f, state)
            elif line.startswith('endsuite'):
                full_log = True
                break
    if not full_log:
        return None
    return {
        'name': suite_name,
        'date': pd.Timestamp(suite_date) + pd.Timedelta(suite_time),
        'experiments': experiments,
    }


def to_zarr(ds, path):
    if path.exists():
        logger.info('appending to existing zarr store "%s"', path)
        ds.to_zarr(path, append_dim='time', mode='a', consolidated=False)
    else:
        logger.info('creating new zarr store "%s"', path)
        ds.to_zarr(path, mode='w', consolidated=False)


def save_experiment_state(wdir, name, experiment, date, chunk_size=16):
    path_state = wdir / f'state/{name}.zarr'
    path_state.parent.mkdir(parents=True, exist_ok=True)
    state = get_state_family(name, experiment)
    ds = xr.Dataset(
        data_vars={
            'state': (('node',), list(state.values())),
        },
        coords={
            'node': (('node',), list(state.keys())),
        },
    ).expand_dims(time=[date])
    # temporary fix for zarr v3 issue with strings
    ds['node'] = ds['node'].astype('O')
    # chunking in time
    ds['state'].encoding['chunks'] = (chunk_size, len(ds.node))
    # encoding for time
    ds['time'].encoding = {
        'dtype': 'int64',
        'units': 'minutes since 2026-01-01T00:00:00',
    }
    to_zarr(ds, path_state)


def save_experiment_progress(wdir, name, experiment, date, chunk_size=128):
    path_progress = wdir / f'progress/{name}.zarr'
    path_progress.parent.mkdir(parents=True, exist_ok=True)
    progress = get_progress_experiment(experiment)
    ds = xr.Dataset(
        data_vars={
            key: (('time',), [value])
            for key, value in progress.items()
            if 'current' in key or 'state' in key
        },
        coords={
            'time': (('time',), [date]),
        },
        attrs={
            key: progress[key].strftime('%Y-%m-%dT%H:%M:%S')
            for key in ('date_start', 'date_end')
        }
        | {
            'date_freq': int(progress['date_freq'].total_seconds()) // 3600,
            'experiment_type': progress['experiment_type'],
        },
    )
    # chunking in time
    for key in progress:
        if 'current' in key or 'state' in key:
            ds[key].encoding['chunks'] = (chunk_size,)
    # encoding for time
    ds['time'].encoding = {
        'dtype': 'int64',
        'units': 'minutes since 2026-01-01T00:00:00',
    }
    to_zarr(ds, path_progress)


def parse_log_files(wdir):
    wdir = pathlib.Path(wdir)
    path_log_in = wdir / 'log_in'
    path_log_arxiv = wdir / 'log_arxiv'
    logger.info('building list of log files to parse')
    path_log_in.mkdir(parents=True, exist_ok=True)
    path_log_arxiv.mkdir(parents=True, exist_ok=True)
    log_files = sorted(path_log_in.glob('*.log'))
    logger.info('waiting 2 seconds before opening log files')
    time.sleep(2)
    for log_file in log_files:
        logger.info('parsing log file "%s"', log_file)
        suite = parse_suite(log_file)
        if suite is None:
            logger.info('skipping log file (incomplete)')
            continue

        for name, experiment in suite['experiments'].items():
            logger.info('processing experiment "%s"', name)
            save_experiment_state(wdir, name, experiment, suite['date'])
            save_experiment_progress(wdir, name, experiment, suite['date'])

        path_active = wdir / f'active/{suite["name"]}.txt'
        path_active.parent.mkdir(parents=True, exist_ok=True)
        logger.info('saving active experiment list into "%s"', path_active)
        with pathlib.Path(path_active).open('w', encoding=None) as f:
            for name in suite['experiments']:
                f.write(f'{name}\n')

        new_name = path_log_arxiv / log_file.name
        logger.info('renaming log file into "%s"', new_name)
        log_file.rename(new_name)
