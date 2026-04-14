import xarray as xr

from watch_duck.common.state import encode_state


def get_state_family(prefix, family):
    state = {prefix: encode_state(family['state'])}
    if 'children' in family:
        for key, value in family['children'].items():
            state.update(get_state_family(f'{prefix}/{key}', value))
    return state


def save_experiment_state(
    wdir,
    name,
    experiment,
    date,
    chunk_size,
):
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
    wdir.save_experiment_state(name, ds)
