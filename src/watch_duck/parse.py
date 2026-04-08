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


def get_state_suite(suite):
    state = {}
    for key, value in suite['experiments'].items():
        state.update(get_state_family(f'/{key}', value))
    return state


def check_group(group, kind=''):
    if group not in {f'{kind}00', f'{kind}12'}:
        message = f'unsupported group "{group}"'
        raise ValueError(message)


def check_groups(groups, kind=''):
    if groups != [f'{kind}00', f'{kind}12']:
        message = f'unsupported groups "{groups}"'
        raise ValueError(message)


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


def get_progress_fc_1_experiment(node_ini, node_fc, node_lag, group):
    check_group(group)
    step = int(group) * pd.Timedelta('1h')
    date_start = pd.Timestamp(node_ini['children'][group]['ymd_start']) + step
    date_end = pd.Timestamp(node_ini['children'][group]['ymd_end']) + step
    date_freq = int(node_ini['children'][group]['ymd_freq']) * pd.Timedelta('1D')
    date_ini = pd.Timestamp(node_ini['children'][group]['ymd_current']) + step
    date_fc = pd.Timestamp(node_fc['children'][group]['ymd_current']) + step
    date_lag = pd.Timestamp(node_lag['children'][group]['ymd_current']) + step
    if node_ini['children'][group]['state'] == 'complete':
        date_ini += date_freq
        node_ini['children'][group]['state'] = 'queued'
    if node_fc['children'][group]['state'] == 'complete':
        date_fc += date_freq
        node_fc['children'][group]['state'] = 'queued'
    if node_lag['children'][group]['state'] == 'complete':
        date_lag += date_freq
        node_lag['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_ini': date_ini,
        'current_fc': date_fc,
        'current_lag': date_lag,
        'state_ini': encode_state(node_ini['children'][group]['state']),
        'state_fc': encode_state(node_fc['children'][group]['state']),
        'state_lag': encode_state(node_lag['children'][group]['state']),
    }


def get_progress_fc_2_experiment(node_ini, node_fc, node_lag, ini_groups):
    check_groups(ini_groups)
    progress_00 = get_progress_fc_1_experiment(node_ini, node_fc, node_lag, '00')
    progress_12 = get_progress_fc_1_experiment(node_ini, node_fc, node_lag, '12')
    if progress_00['date_start'] < progress_12['date_start']:
        date_start = progress_00['date_start']
        date_end = progress_12['date_end']
        date_freq = progress_12['date_start'] - progress_00['date_start']
    else:
        date_start = progress_12['date_start']
        date_end = progress_00['date_end']
        date_freq = progress_00['date_start'] - progress_12['date_start']
    check_frequencies(progress_00['date_freq'], progress_12['date_freq'], date_freq)
    date_ini = min(progress_00['current_ini'], progress_12['current_ini'])
    date_fc = min(progress_00['current_fc'], progress_12['current_fc'])
    date_lag = min(progress_00['current_lag'], progress_12['current_lag'])
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_ini': date_ini,
        'current_fc': date_fc,
        'current_lag': date_lag,
        'state_ini_00': encode_state(node_ini['children']['00']['state']),
        'state_fc_00': encode_state(node_fc['children']['00']['state']),
        'state_lag_00': encode_state(node_lag['children']['00']['state']),
        'state_ini_12': encode_state(node_ini['children']['12']['state']),
        'state_fc_12': encode_state(node_fc['children']['12']['state']),
        'state_lag_12': encode_state(node_lag['children']['12']['state']),
    }


def check_fc_experiment(experiment):
    if list(experiment['children'].keys()) != ['fc', 'cancel']:
        message = (
            f'unexpected experiment children "{list(experiment["children"].keys())}"'
        )
        raise ValueError(message)
    node_fc = experiment['children']['fc']
    if list(node_fc['children'].keys()) != ['make', 'main', 'lag']:
        message = f'unexpected fc children "{list(node_fc["children"].keys())}"'
        raise ValueError(message)
    node_main = node_fc['children']['main']
    if list(node_main['children'].keys()) != ['inigroup', 'fcgroup']:
        message = f'unexpected main children "{list(node_main["children"].keys())}"'
        raise ValueError(message)
    node_lag = node_fc['children']['lag']
    node_ini = node_main['children']['inigroup']
    node_fc = node_main['children']['fcgroup']
    ini_groups = list(node_ini['children'].keys())
    fc_groups = list(node_fc['children'].keys())
    lag_groups = list(node_lag['children'].keys())
    if ini_groups != fc_groups or ini_groups != lag_groups:
        message = f"""ini, fc, and lag groups should have the same children:
    ini_groups={ini_groups},
    fc_groups={fc_groups},
    lag_groups={lag_groups}
"""
        raise ValueError(message)


def get_progress_fc_experiment(experiment):
    check_fc_experiment(experiment)
    node_fc = experiment['children']['fc']
    node_main = node_fc['children']['main']
    node_lag = node_fc['children']['lag']
    node_ini = node_main['children']['inigroup']
    node_fc = node_main['children']['fcgroup']
    ini_groups = list(node_ini['children'].keys())
    if len(ini_groups) == 1:
        return get_progress_fc_1_experiment(node_ini, node_fc, node_lag, ini_groups[0])
    return get_progress_fc_2_experiment(node_ini, node_fc, node_lag, ini_groups)


def check_an_experiment(experiment):
    if list(experiment['children'].keys()) != ['an', 'cancel']:
        message = (
            f'unexpected experiment children "{list(experiment["children"].keys())}"'
        )
        raise ValueError(message)
    node_an = experiment['children']['an']
    if list(node_an['children'].keys()) != ['make', 'obs', 'main', 'lag', 'wsjobs']:
        message = f'unexpected an children "{list(node_an["children"].keys())}"'
        raise ValueError(message)
    node_obs = node_an['children']['obs']
    node_main = node_an['children']['main']
    node_lag = node_an['children']['lag']
    obs_groups = list(node_obs['children'].keys())
    main_groups = list(node_main['children'].keys())
    lag_groups = list(node_lag['children'].keys())
    if obs_groups != main_groups or obs_groups != lag_groups:
        message = f"""obs, main, and lag groups should have the same children:
    obs_groups={obs_groups},
    main_groups={main_groups},
    lag_groups={lag_groups}
"""
        raise ValueError(message)


def get_progress_an_1_experiment(node_obs, node_main, node_lag, kind, group):
    check_group(group, kind=kind)
    step = int(group[len(kind) :]) * pd.Timedelta('1h')
    date_start = pd.Timestamp(node_obs['children'][group]['ymd_start']) + step
    date_end = pd.Timestamp(node_obs['children'][group]['ymd_end']) + step
    date_freq = int(node_obs['children'][group]['ymd_freq']) * pd.Timedelta('1D')
    date_obs = pd.Timestamp(node_obs['children'][group]['ymd_current']) + step
    date_main = pd.Timestamp(node_main['children'][group]['ymd_current']) + step
    date_lag = pd.Timestamp(node_lag['children'][group]['ymd_current']) + step
    if node_obs['children'][group]['state'] == 'complete':
        date_obs += date_freq
        node_obs['children'][group]['state'] = 'queued'
    if node_main['children'][group]['state'] == 'complete':
        date_main += date_freq
        node_main['children'][group]['state'] = 'queued'
    if node_lag['children'][group]['state'] == 'complete':
        date_lag += date_freq
        node_lag['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_obs': date_obs,
        'current_main': date_main,
        'current_lag': date_lag,
        'state_obs': encode_state(node_obs['children'][group]['state']),
        'state_main': encode_state(node_main['children'][group]['state']),
        'state_lag': encode_state(node_lag['children'][group]['state']),
    }


def get_progress_an_2_experiment(node_obs, node_main, node_lag, kind, obs_groups):
    check_groups(obs_groups, kind=kind)
    progress_00 = get_progress_an_1_experiment(
        node_obs,
        node_main,
        node_lag,
        kind,
        f'{kind}00',
    )
    progress_12 = get_progress_an_1_experiment(
        node_obs,
        node_main,
        node_lag,
        kind,
        f'{kind}12',
    )
    if progress_00['date_start'] < progress_12['date_start']:
        date_start = progress_00['date_start']
        date_end = progress_12['date_end']
        date_freq = progress_12['date_start'] - progress_00['date_start']
    else:
        date_start = progress_12['date_start']
        date_end = progress_00['date_end']
        date_freq = progress_00['date_start'] - progress_12['date_start']
    check_frequencies(progress_00['date_freq'], progress_12['date_freq'], date_freq)
    date_obs = min(progress_00['current_obs'], progress_12['current_obs'])
    date_main = min(progress_00['current_main'], progress_12['current_main'])
    date_lag = min(progress_00['current_lag'], progress_12['current_lag'])
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_obs': date_obs,
        'current_main': date_main,
        'current_lag': date_lag,
        'state_obs_00': encode_state(node_obs['children'][f'{kind}00']['state']),
        'state_main_00': encode_state(node_main['children'][f'{kind}00']['state']),
        'state_lag_00': encode_state(node_lag['children'][f'{kind}00']['state']),
        'state_obs_12': encode_state(node_obs['children'][f'{kind}12']['state']),
        'state_main_12': encode_state(node_main['children'][f'{kind}12']['state']),
        'state_lag_12': encode_state(node_lag['children'][f'{kind}12']['state']),
    }


def get_progress_an_experiment(experiment, kind):
    check_an_experiment(experiment)
    node_an = experiment['children']['an']
    node_obs = node_an['children']['obs']
    node_main = node_an['children']['main']
    node_lag = node_an['children']['lag']
    obs_groups = list(node_obs['children'].keys())
    if len(obs_groups) == 1:
        return get_progress_an_1_experiment(
            node_obs,
            node_main,
            node_lag,
            kind,
            obs_groups[0],
        )
    return get_progress_an_2_experiment(node_obs, node_main, node_lag, kind, obs_groups)


def get_experiment_type(experiment):
    main_type = next(iter(experiment['children'].keys()))
    if main_type == 'fc':
        return 'fc'
    if next(iter(experiment['children'].keys())) != 'an':
        message = (
            f'unexpected experiment children "{list(experiment["children"].keys())}"'
        )
        raise ValueError(message)
    return next(
        iter(experiment['children']['an']['children']['obs']['children'].keys()),
    )[:-2]


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
            if 'date' not in key
        },
        coords={
            'time': (('time',), [date]),
        },
        attrs={
            key: progress[key].strftime('%Y-%m-%dT%H:%M:%S')
            for key in ('date_start', 'date_end')
        }|{'date_freq': int(progress['date_freq'].total_seconds()) // 3600},
    )
    # chunking in time
    for key in progress:
        if 'date' not in key:
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
