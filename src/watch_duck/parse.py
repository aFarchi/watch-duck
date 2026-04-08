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


def get_progress_fc_1_experiment(node_ini, node_fc, node_lag, group):
    check_group(group)
    node_ini_00 = node_ini['children'][group]
    node_fc_00 = node_fc['children'][group]
    node_lag_00 = node_lag['children'][group]
    step = int(group) * pd.Timedelta('1h')
    date_start = pd.Timestamp(node_ini_00['ymd_start']) + step
    date_end = pd.Timestamp(node_ini_00['ymd_end']) + step
    date_freq = int(node_ini_00['ymd_freq']) * pd.Timedelta('1D')
    date_current_ini = pd.Timestamp(node_ini_00['ymd_current']) + step
    date_current_fc = pd.Timestamp(node_fc_00['ymd_current']) + step
    date_current_lag = pd.Timestamp(node_lag_00['ymd_current']) + step
    index_ini = (date_current_ini - date_start) // date_freq
    index_fc = (date_current_fc - date_start) // date_freq
    index_lag = (date_current_lag - date_start) // date_freq
    if node_ini_00['state'] == 'complete':
        index_ini += 1
        node_ini_00['state'] = 'queued'
    if node_fc_00['state'] == 'complete':
        index_fc += 1
        node_fc_00['state'] = 'queued'
    if node_lag_00['state'] == 'complete':
        index_lag += 1
        node_lag_00['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'index_ini': index_ini,
        'index_fc': index_fc,
        'index_lag': index_lag,
        'state_ini': encode_state(node_ini_00['state']),
        'state_fc': encode_state(node_fc_00['state']),
        'state_lag': encode_state(node_lag_00['state']),
    }


def get_progress_fc_2_experiment(node_ini, node_fc, node_lag, ini_groups):
    check_groups(ini_groups)
    node_ini_00 = node_ini['children']['00']
    node_fc_00 = node_fc['children']['00']
    node_lag_00 = node_lag['children']['00']
    node_ini_12 = node_ini['children']['12']
    node_fc_12 = node_fc['children']['12']
    node_lag_12 = node_lag['children']['12']
    ini_00_state = node_ini_00['state']
    fc_00_state = node_fc_00['state']
    lag_00_state = node_lag_00['state']
    ini_12_state = node_ini_12['state']
    fc_12_state = node_fc_12['state']
    lag_12_state = node_lag_12['state']
    step_00 = pd.Timedelta('0h')
    step_12 = pd.Timedelta('12h')
    date_start_00 = pd.Timestamp(node_ini_00['ymd_start']) + step_00
    date_end_00 = pd.Timestamp(node_ini_00['ymd_end']) + step_00
    date_freq_00 = int(node_ini_00['ymd_freq']) * pd.Timedelta('1D')
    date_current_ini_00 = pd.Timestamp(node_ini_00['ymd_current']) + step_00
    date_current_fc_00 = pd.Timestamp(node_fc_00['ymd_current']) + step_00
    date_current_lag_00 = pd.Timestamp(node_lag_00['ymd_current']) + step_00
    if ini_00_state == 'complete':
        date_current_ini_00 += date_freq_00
        ini_00_state = 'queued'
    if fc_00_state == 'complete':
        date_current_fc_00 += date_freq_00
        fc_00_state = 'queued'
    if lag_00_state == 'complete':
        date_current_lag_00 += date_freq_00
        lag_00_state = 'queued'
    date_start_12 = pd.Timestamp(node_ini_12['ymd_start']) + step_12
    date_end_12 = pd.Timestamp(node_ini_12['ymd_end']) + step_12
    date_freq_12 = int(node_ini_12['ymd_freq']) * pd.Timedelta('1D')
    date_current_ini_12 = pd.Timestamp(node_ini_12['ymd_current']) + step_12
    date_current_fc_12 = pd.Timestamp(node_fc_12['ymd_current']) + step_12
    date_current_lag_12 = pd.Timestamp(node_lag_12['ymd_current']) + step_12
    if ini_12_state == 'complete':
        date_current_ini_12 += date_freq_12
        ini_12_state = 'queued'
    if fc_12_state == 'complete':
        date_current_fc_12 += date_freq_12
        fc_12_state = 'queued'
    if lag_12_state == 'complete':
        date_current_lag_12 += date_freq_12
        lag_12_state = 'queued'
    if date_start_00 < date_start_12:
        date_start = date_start_00
        date_end = date_end_12
        date_freq = date_start_12 - date_start_00
    else:
        date_start = date_start_12
        date_end = date_end_00
        date_freq = date_start_00 - date_start_12
    check_frequencies(date_freq_00, date_freq_12, date_freq)
    date_current_ini = min(date_current_ini_00, date_current_ini_12)
    date_current_fc = min(date_current_fc_00, date_current_fc_12)
    date_current_lag = min(date_current_lag_00, date_current_lag_12)
    index_ini = (date_current_ini - date_start) // date_freq
    index_fc = (date_current_fc - date_start) // date_freq
    index_lag = (date_current_lag - date_start) // date_freq
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'index_ini': index_ini,
        'index_fc': index_fc,
        'index_lag': index_lag,
        'state_ini_00': encode_state(ini_00_state),
        'state_fc_00': encode_state(fc_00_state),
        'state_lag_00': encode_state(lag_00_state),
        'state_ini_12': encode_state(ini_12_state),
        'state_fc_12': encode_state(fc_12_state),
        'state_lag_12': encode_state(lag_12_state),
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
    node_obs_00 = node_obs['children'][group]
    node_main_00 = node_main['children'][group]
    node_lag_00 = node_lag['children'][group]
    obs_00_state = node_obs_00['state']
    main_00_state = node_main_00['state']
    lag_00_state = node_lag_00['state']
    step = int(group[len(kind) :]) * pd.Timedelta('1h')
    date_start = pd.Timestamp(node_obs_00['ymd_start']) + step
    date_end = pd.Timestamp(node_obs_00['ymd_end']) + step
    date_freq = int(node_obs_00['ymd_freq']) * pd.Timedelta('1D')
    date_current_obs = pd.Timestamp(node_obs_00['ymd_current']) + step
    date_current_main = pd.Timestamp(node_main_00['ymd_current']) + step
    date_current_lag = pd.Timestamp(node_lag_00['ymd_current']) + step
    if obs_00_state == 'complete':
        date_current_obs += date_freq
        obs_00_state = 'queued'
    if main_00_state == 'complete':
        date_current_main += date_freq
        main_00_state = 'queued'
    if lag_00_state == 'complete':
        date_current_lag += date_freq
        lag_00_state = 'queued'
    index_obs = (date_current_obs - date_start) // date_freq
    index_main = (date_current_main - date_start) // date_freq
    index_lag = (date_current_lag - date_start) // date_freq
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'index_obs': index_obs,
        'index_main': index_main,
        'index_lag': index_lag,
        'state_obs': encode_state(obs_00_state),
        'state_main': encode_state(main_00_state),
        'state_lag': encode_state(lag_00_state),
    }


def get_progress_an_2_experiment(node_obs, node_main, node_lag, kind, obs_groups):
    check_groups(obs_groups, kind=kind)
    node_obs_00 = node_obs['children'][f'{kind}00']
    node_main_00 = node_main['children'][f'{kind}00']
    node_lag_00 = node_lag['children'][f'{kind}00']
    node_obs_12 = node_obs['children'][f'{kind}12']
    node_main_12 = node_main['children'][f'{kind}12']
    node_lag_12 = node_lag['children'][f'{kind}12']
    obs_00_state = node_obs_00['state']
    main_00_state = node_main_00['state']
    lag_00_state = node_lag_00['state']
    obs_12_state = node_obs_12['state']
    main_12_state = node_main_12['state']
    lag_12_state = node_lag_12['state']
    step_00 = pd.Timedelta('0h')
    step_12 = pd.Timedelta('12h')
    date_start_00 = pd.Timestamp(node_obs_00['ymd_start']) + step_00
    date_end_00 = pd.Timestamp(node_obs_00['ymd_end']) + step_00
    date_freq_00 = int(node_obs_00['ymd_freq']) * pd.Timedelta('1D')
    date_current_obs_00 = pd.Timestamp(node_obs_00['ymd_current']) + step_00
    date_current_main_00 = pd.Timestamp(node_main_00['ymd_current']) + step_00
    date_current_lag_00 = pd.Timestamp(node_lag_00['ymd_current']) + step_00
    if obs_00_state == 'complete':
        date_current_obs_00 += date_freq_00
        obs_00_state = 'queued'
    if main_00_state == 'complete':
        date_current_main_00 += date_freq_00
        main_00_state = 'queued'
    if lag_00_state == 'complete':
        date_current_lag_00 += date_freq_00
        lag_00_state = 'queued'
    date_start_12 = pd.Timestamp(node_obs_12['ymd_start']) + step_12
    date_end_12 = pd.Timestamp(node_obs_12['ymd_end']) + step_12
    date_freq_12 = int(node_obs_12['ymd_freq']) * pd.Timedelta('1D')
    date_current_obs_12 = pd.Timestamp(node_obs_12['ymd_current']) + step_12
    date_current_main_12 = pd.Timestamp(node_main_12['ymd_current']) + step_12
    date_current_lag_12 = pd.Timestamp(node_lag_12['ymd_current']) + step_12
    if obs_12_state == 'complete':
        date_current_obs_12 += date_freq_12
        obs_12_state = 'queued'
    if main_12_state == 'complete':
        date_current_main_12 += date_freq_12
        main_12_state = 'queued'
    if lag_12_state == 'complete':
        date_current_lag_12 += date_freq_12
        lag_12_state = 'queued'
    if date_start_00 < date_start_12:
        date_start = date_start_00
        date_end = date_end_12
        date_freq = date_start_12 - date_start_00
    else:
        date_start = date_start_12
        date_end = date_end_00
        date_freq = date_start_00 - date_start_12
    check_frequencies(date_freq_00, date_freq_12, date_freq)
    date_current_obs = min(date_current_obs_00, date_current_obs_12)
    date_current_main = min(date_current_main_00, date_current_main_12)
    date_current_lag = min(date_current_lag_00, date_current_lag_12)
    index_obs = (date_current_obs - date_start) // date_freq
    index_main = (date_current_main - date_start) // date_freq
    index_lag = (date_current_lag - date_start) // date_freq
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'index_obs': index_obs,
        'index_main': index_main,
        'index_lag': index_lag,
        'state_obs_00': encode_state(obs_00_state),
        'state_main_00': encode_state(main_00_state),
        'state_lag_00': encode_state(lag_00_state),
        'state_obs_12': encode_state(obs_12_state),
        'state_main_12': encode_state(main_12_state),
        'state_lag_12': encode_state(lag_12_state),
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
            node_obs, node_main, node_lag, kind, obs_groups[0],
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
            return get_progress_fc_experiment(experiment)
        case 'lw' | 'elda':
            return get_progress_an_experiment(experiment, kind=experiment_type)


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
        ds.to_zarr(path, append_dim='time', mode='a')
    else:
        logger.info('creating new zarr store "%s"', path)
        ds.to_zarr(path, mode='w')


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
    ds['state'].encoding['chunks'] = (chunk_size, len(ds.node))
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
        attrs={key: value for key, value in progress.items() if 'date' in key}.update({
            'name': name,
        }),
    )
    for key in progress:
        if 'date' not in key:
            ds[key].encoding['chunks'] = (chunk_size,)
    to_zarr(ds, path_progress)


def postprocess_log_files(wdir):
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
        logger.info('parsing log file %s', log_file)
        suite = parse_suite(log_file)
        if suite is None:
            logger.info('skipping log file (incomplete)')
            continue

        for name, experiment in suite['experiments'].items():
            logger.info('preprocessing experiment "%s"', name)
            save_experiment_state(wdir, name, experiment, suite['date'])
            save_experiment_progress(wdir, name, experiment, suite['date'])

        path_active = wdir / f'active/{suite["name"]}.txt'
        path_active.parent.mkdir(parents=True, exist_ok=True)
        logger.info('saving active experiment list into %s', path_active)
        with pathlib.Path(path_active).open('w', encoding=None) as f:
            for name in suite['experiments']:
                f.write(f'{name}\n')

        new_name = path_log_arxiv / log_file.name
        logger.info('renaming log file into %s', new_name)
        log_file.rename(new_name)
