import logging

import pandas as pd
import xarray as xr

from watch_duck.common.state import encode_state

logger = logging.getLogger(__name__)


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
        key.replace('current_', 'index_'): value
        if not key.startswith('current_')
        else (value - date_start) // date_freq
        for key, value in progress.items()
    }


def encode_state_nodes(nodes, groups):
    return {f'state_{node}': encode_state(nodes[node]['state']) for node in nodes} | {
        f'state_{node}_{group}': encode_state(nodes[node]['children'][group]['state'])
        for node in nodes
        for group in groups
    }


def merge_progress(progress_00, progress_12, nodes, kind):
    if progress_00['date_start'] < progress_12['date_start']:
        date_start = progress_00['date_start']
        date_end = progress_12['date_end']
        date_freq = progress_12['date_start'] - progress_00['date_start']
    else:
        date_start = progress_12['date_start']
        date_end = progress_00['date_end']
        date_freq = progress_00['date_start'] - progress_12['date_start']
    check_frequencies(progress_00['date_freq'], progress_12['date_freq'], date_freq)
    return (
        progress_00
        | progress_12
        | {
            'date_start': date_start,
            'date_end': date_end,
            'date_freq': date_freq,
        }
        | {
            f'current_{key}': min(
                progress_00[f'current_{key}_{kind}00'],
                progress_12[f'current_{key}_{kind}12'],
            )
            for key in nodes
        }
    )


def get_progress_fc_1_experiment(nodes, group):
    step = int(group) * pd.Timedelta('1h')
    date_start = (
        pd.Timestamp(nodes['preprocess']['children'][group]['ymd_start']) + step
    )
    date_end = pd.Timestamp(nodes['preprocess']['children'][group]['ymd_end']) + step
    date_freq = int(nodes['preprocess']['children'][group]['ymd_freq']) * pd.Timedelta(
        '1D',
    )
    date_ini = (
        pd.Timestamp(nodes['preprocess']['children'][group]['ymd_current']) + step
    )
    date_fc = pd.Timestamp(nodes['main']['children'][group]['ymd_current']) + step
    date_lag = (
        pd.Timestamp(nodes['postprocess']['children'][group]['ymd_current']) + step
    )
    if (
        nodes['preprocess']['children'][group]['state'] == 'complete'
        and date_ini < date_end
    ):
        date_ini += date_freq
        nodes['preprocess']['children'][group]['state'] = 'queued'
    if nodes['main']['children'][group]['state'] == 'complete' and date_fc < date_end:
        date_fc += date_freq
        nodes['main']['children'][group]['state'] = 'queued'
    if (
        nodes['postprocess']['children'][group]['state'] == 'complete'
        and date_lag < date_end
    ):
        date_lag += date_freq
        nodes['postprocess']['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_preprocess': date_ini,
        'current_main': date_fc,
        'current_postprocess': date_lag,
        f'current_preprocess_{group}': date_ini,
        f'current_main_{group}': date_fc,
        f'current_postprocess_{group}': date_lag,
    } | encode_state_nodes(nodes, groups=[group])


def get_progress_fc_2_experiment(nodes):
    progress_00 = get_progress_fc_1_experiment(nodes, '00')
    progress_12 = get_progress_fc_1_experiment(nodes, '12')
    progress = merge_progress(
        progress_00,
        progress_12,
        nodes=('preprocess', 'main', 'postprocess'),
        kind='',
    )
    return progress | encode_state_nodes(nodes, groups=('00', '12'))


def get_progress_fc_experiment(experiment):
    nodes = {
        'preprocess': experiment['children']['fc']['children']['main']['children'][
            'inigroup'
        ],
        'main': experiment['children']['fc']['children']['main']['children']['fcgroup'],
        'postprocess': experiment['children']['fc']['children']['lag'],
    }
    groups = list(nodes['preprocess']['children'].keys())
    if len(groups) == 1:
        progress = get_progress_fc_1_experiment(nodes, groups[0])
    else:
        progress = get_progress_fc_2_experiment(nodes)
    progress['state'] = encode_state(experiment['state'])
    progress['experiment_type'] = 'fc'
    return progress


def get_progress_an_1_experiment(nodes, kind, group):
    step = int(group[len(kind) :]) * pd.Timedelta('1h')
    date_start = (
        pd.Timestamp(nodes['preprocess']['children'][group]['ymd_start']) + step
    )
    date_end = pd.Timestamp(nodes['preprocess']['children'][group]['ymd_end']) + step
    date_freq = int(nodes['preprocess']['children'][group]['ymd_freq']) * pd.Timedelta(
        '1D',
    )
    date_obs = (
        pd.Timestamp(nodes['preprocess']['children'][group]['ymd_current']) + step
    )
    date_main = pd.Timestamp(nodes['main']['children'][group]['ymd_current']) + step
    date_lag = (
        pd.Timestamp(nodes['postprocess']['children'][group]['ymd_current']) + step
    )
    if (
        nodes['preprocess']['children'][group]['state'] == 'complete'
        and date_obs < date_end
    ):
        date_obs += date_freq
        nodes['preprocess']['children'][group]['state'] = 'queued'
    if nodes['main']['children'][group]['state'] == 'complete' and date_main < date_end:
        date_main += date_freq
        nodes['main']['children'][group]['state'] = 'queued'
    if (
        nodes['postprocess']['children'][group]['state'] == 'complete'
        and date_lag < date_end
    ):
        date_lag += date_freq
        nodes['postprocess']['children'][group]['state'] = 'queued'
    return {
        'date_start': date_start,
        'date_end': date_end,
        'date_freq': date_freq,
        'current_preprocess': date_obs,
        'current_main': date_main,
        'current_postprocess': date_lag,
        f'current_preprocess_{group}': date_obs,
        f'current_main_{group}': date_main,
        f'current_postprocess_{group}': date_lag,
    } | encode_state_nodes(nodes, groups=[group])


def get_progress_an_2_experiment(nodes, kind):
    progress_00 = get_progress_an_1_experiment(nodes, kind, f'{kind}00')
    progress_12 = get_progress_an_1_experiment(nodes, kind, f'{kind}12')
    progress = merge_progress(
        progress_00,
        progress_12,
        nodes=('preprocess', 'main', 'postprocess'),
        kind=kind,
    )
    return progress | encode_state_nodes(nodes, groups=(f'{kind}00', f'{kind}12'))


def get_progress_an_experiment(experiment, kind):
    nodes = {
        'preprocess': experiment['children']['an']['children']['obs'],
        'main': experiment['children']['an']['children']['main'],
        'postprocess': experiment['children']['an']['children']['lag'],
    }
    groups = list(nodes['preprocess']['children'].keys())
    if len(groups) == 1:
        progress = get_progress_an_1_experiment(nodes, kind, groups[0])
    else:
        progress = get_progress_an_2_experiment(nodes, kind)
    progress = {
        key.replace(f'_{kind}00', '_00').replace(f'_{kind}12', '_12'): value
        for key, value in progress.items()
    }
    progress['state'] = encode_state(experiment['state'])
    progress['experiment_type'] = kind
    return progress


def check_fc_experiment(experiment):
    children = list(experiment['children'].keys())
    if children != ['fc', 'cancel']:
        logger.debug('unexpected experiment children: "%s"', children)
        return False
    children = list(experiment['children']['fc']['children'].keys())
    if children != ['make', 'main', 'lag']:
        logger.debug('unexpected experiment/fc children: "%s"', children)
        return False
    children = list(experiment['children']['fc']['children']['main']['children'].keys())
    if children != ['inigroup', 'fcgroup']:
        logger.debug('unexpected experiment/fc/main children: "%s"', children)
        return False
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
        logger.debug(
            """ini, fc, and lag groups should have the same children:
    ini_groups=%s,
    fc_groups=%s,
    lag_groups=%s
""",
            ini_groups,
            fc_groups,
            lag_groups,
        )
        return False
    if ini_groups not in [['00'], ['12'], ['00', '12']]:
        logger.debug('unexpected groups: "%s"', ini_groups)
        return False
    return True


def check_fc50_experiment(experiment):
    children = list(experiment['children'].keys())
    if children != ['fc', 'cancel']:
        logger.debug('unexpected experiment children: "%s"', children)
        return False
    children = list(experiment['children']['fc']['children'].keys())
    if children != ['make', 'main', 'lag']:
        logger.debug('unexpected experiment/fc children: "%s"', children)
        return False
    children = list(experiment['children']['fc']['children']['main']['children'].keys())
    if children != ['inigroup', 'fcgroup']:
        logger.debug('unexpected experiment/fc/main children: "%s"', children)
        return False
    children = list(experiment['children']['fc']['children']['lag']['children'].keys())
    if 'logfiles' not in children:
        logger.debug('unexpected experiment/fc/lag children: "%s"', children)
        return False
    return True


def check_an_experiment(experiment, kind):
    children = list(experiment['children'].keys())
    if children != ['an', 'cancel']:
        logger.debug('unexpected experiment children: "%s"', children)
        return False
    children = list(experiment['children']['an']['children'].keys())
    if children not in (
        ['make', 'obs', 'main', 'lag', 'wsjobs'],
        ['make', 'obs', 'prepare_aux', 'main', 'lag', 'wsjobs'],
    ):
        logger.debug('unexpected experiment/an children: "%s"', children)
        return False
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
        logger.debug(
            """obs, main, and lag groups should have the same children:
    obs_groups=%s,
    main_groups=%s,
    lag_groups=%s
""",
            obs_groups,
            main_groups,
            lag_groups,
        )
        return False
    if obs_groups not in [[f'{kind}00'], [f'{kind}12'], [f'{kind}00', f'{kind}12']]:
        logger.debug('unexpected groups: "%s"', obs_groups)
        return False
    return True


def get_experiment_type(experiment):
    main_type = next(iter(experiment['children'].keys()))
    if main_type == 'fc' and check_fc_experiment(experiment):
        return 'fc'
    if main_type == 'fc' and check_fc50_experiment(experiment):
        return 'fc50'
    if main_type == 'an' and check_an_experiment(experiment, kind='lw'):
        return 'lw'
    if main_type == 'an' and check_an_experiment(experiment, kind='elda'):
        return 'elda'
    return 'unknown'


def get_progress_experiment(experiment_type, experiment):
    match experiment_type:
        case 'fc':
            progress = get_progress_fc_experiment(experiment)
        case 'lw' | 'elda':
            progress = get_progress_an_experiment(experiment, kind=experiment_type)
        case _:
            message = f'unexpected experiment type: "{experiment_type}"'
            raise ValueError(message)
    progress = current_date_to_index(progress)
    if len(progress) == 17:
        progress = {
            key: value
            for key, value in progress.items()
            if not key.endswith(('_00', '_12'))
        }
    return progress


def save_experiment_progress(
    wdir,
    name,
    experiment_type,
    experiment,
    date,
    suite,
    chunk_size,
):
    progress = get_progress_experiment(experiment_type, experiment)
    ds = xr.Dataset(
        data_vars={
            key: (('time',), [value])
            for key, value in progress.items()
            if 'index' in key or 'state' in key
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
            'suite': suite,
        },
    )
    # chunking in time
    for key in progress:
        if 'index' in key or 'state' in key:
            ds[key].encoding['chunks'] = (chunk_size,)
    # encoding for time
    ds['time'].encoding = {
        'dtype': 'int64',
        'units': 'minutes since 2026-01-01T00:00:00',
        'chunks': (chunk_size,),
    }
    wdir.save_experiment_progress(name, ds)
