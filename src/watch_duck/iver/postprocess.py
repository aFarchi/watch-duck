import glob
import logging
import shutil

import pandas as pd
import xarray as xr

stat_names = {
    'anomaly correlation': 'acc',
    'rms error': 'rmse',
    'mean error': 'me',
    'std. dev. of error': 'stde',
    'information': 'fi',
    'info error': 'ie',
    'noise error': 'ne',
    'activity of fc': 'sdaf',
    'activity of an': 'sdav',
}
logger = logging.getLogger(__name__)


def select_variables(ds, prefix):
    return xr.merge(
        (
            ds.STAT_LATLON.rename(f'{prefix}_latlon'),
            ds.STAT_ZONAL_TIMEMEAN.rename(f'{prefix}_zonal_mean'),
            ds.STAT_ZONAL_TIMESTD.rename(f'{prefix}_zonal_std'),
            ds.STAT_REGION_TIMEMEAN.rename(f'{prefix}_region_mean'),
            ds.STAT_REGION_TIMESTD.rename(f'{prefix}_region_std'),
        ),
        join='exact',
    )


def transform(ds):
    step = ds.FORECAST_TIME.to_numpy() * pd.Timedelta('1h')
    variable = [p.decode().lower() for p in ds.PARAM_NAME.to_numpy()]
    pressure = ds.PRESSURE.to_numpy() / 100
    stat_indicator = [stat_names[p.decode().lower()] for p in ds.STAT_NAME.to_numpy()]
    region = [p.decode().lower() for p in ds.REGION_NAME.to_numpy()]
    if len(pressure) == 1:
        prefix = 'surface'
        ds = select_variables(ds, prefix)
        ds = ds.isel(PRESSURE=0, drop=True)
    else:
        prefix = 'level'
        ds = select_variables(ds, prefix)
        ds = ds.rename(PRESSURE='pressure').assign_coords(pressure=pressure)
    return (
        ds
        .rename(
            LATITUDE='latitude',
            LONGITUDE='longitude',
            FORECAST_TIME='step',
            STAT_INDEX='stat_indicator',
            PARAM_INDEX='variable',
            REGION='region',
        )
        .assign_coords(
            step=step,
            stat_indicator=stat_indicator,
            variable=variable,
            region=region,
        )
        .rename(variable=f'{prefix}_variable')
        .drop_attrs(deep=True)
    )


def read_scores(filename):
    logger.info('reading %s', filename)
    with xr.open_dataset(filename, engine='h5netcdf') as ds:
        return transform(ds).load()


def merge_level_surface(filename_level, filename_surface):
    ds_level = read_scores(filename_level)
    ds_surface = read_scores(filename_surface)
    return xr.merge((ds_level, ds_surface), join='exact')


def stats_files(iver_path, experiment_id, profile):
    return (
        iver_path / f'stats/verify_{experiment_id}_0001_{profile}.nc',
        iver_path / f'stats/verify_{experiment_id}_0001_{profile}_sfc.nc',
    )


def extract_iver_scores(iver_path, experiment_id, profile):
    filename_level, filename_surface = stats_files(iver_path, experiment_id, profile)
    return (
        merge_level_surface(
            filename_level,
            filename_surface,
        )
        .load()
        .expand_dims(experiment=[experiment_id])
        .chunk(
            experiment=1,
        )
    )


def all_experiments(iver_path, profile):
    prefix = 'verify_'
    suffix = f'_0001_{profile}.nc'
    pattern = f'{prefix}*{glob.escape(suffix)}'
    return {
        filename.name[len(prefix) : -len(suffix)]
        for filename in (iver_path / 'stats').glob(pattern)
    }


def complete_experiments(iver_path, profile):
    experiments = set()
    for experiment_id in sorted(all_experiments(iver_path, profile)):
        _, filename_surface = stats_files(iver_path, experiment_id, profile)
        if filename_surface.exists():
            experiments.add(experiment_id)
        else:
            logger.warning(
                'skipping %s (missing surface stats file %s)',
                experiment_id,
                filename_surface,
            )
    return experiments


def postprocessed_experiments(zarr_store):
    if not zarr_store.exists():
        return set()
    with xr.open_zarr(zarr_store, consolidated=False) as ds:
        return {str(experiment_id) for experiment_id in ds.experiment.to_numpy()}


def first_difference(reference, ds):
    if set(reference.data_vars) != set(ds.data_vars):
        return 'data variables'
    for name in sorted(reference.data_vars):
        if reference[name].dims != ds[name].dims:
            return f'dimensions of {name}'
    for name in sorted((set(reference.coords) | set(ds.coords)) - {'experiment'}):
        if (
            name not in reference.coords
            or name not in ds.coords
            or not reference[name].variable.equals(ds[name].variable)
        ):
            return f'coordinate {name}'
    return None


def write_experiments(zarr_store, iver_path, profile, experiments):
    reference = None
    try:
        for experiment_id in experiments:
            ds = extract_iver_scores(iver_path, experiment_id, profile)
            kwargs = {'consolidated': False}
            if zarr_store.exists():
                if reference is None:
                    reference = xr.open_zarr(zarr_store, consolidated=False)
                difference = first_difference(reference, ds)
                if difference is not None:
                    logger.warning(
                        'skipping %s (%s differs from %s)',
                        experiment_id,
                        difference,
                        zarr_store,
                    )
                    continue
                kwargs['append_dim'] = 'experiment'
            ds.to_zarr(zarr_store, **kwargs)
            logger.info('wrote %s to %s', experiment_id, zarr_store)
    finally:
        if reference is not None:
            reference.close()


def replace_store(zarr_store, new_store):
    old_store = zarr_store.with_name(f'{zarr_store.stem}.old{zarr_store.suffix}')
    if old_store.exists():
        shutil.rmtree(old_store)
    if zarr_store.exists():
        zarr_store.rename(old_store)
    try:
        new_store.rename(zarr_store)
    except OSError:
        if old_store.exists():
            old_store.rename(zarr_store)
        raise
    if old_store.exists():
        shutil.rmtree(old_store)


def rebuild_scores(zarr_store, iver_path, profile, experiments):
    new_store = zarr_store.with_name(f'{zarr_store.stem}.rebuild{zarr_store.suffix}')
    if new_store.exists():
        logger.info('removing leftover %s', new_store)
        shutil.rmtree(new_store)
    dropped = postprocessed_experiments(zarr_store) - set(experiments)
    if dropped:
        logger.warning(
            'rebuilding %s will drop experiments without complete stats files: %s',
            zarr_store,
            ', '.join(sorted(dropped)),
        )
    write_experiments(new_store, iver_path, profile, experiments)
    replace_store(zarr_store, new_store)
    logger.info('rebuilt %s', zarr_store)


def postprocess_scores(iver_path, profile, *, rebuild=False):
    zarr_store = iver_path / 'estats/scores.zarr'
    experiments = sorted(complete_experiments(iver_path, profile))
    if not experiments:
        logger.info('no complete stats files found in %s/stats', iver_path)
        return
    zarr_store.parent.mkdir(parents=True, exist_ok=True)
    if rebuild:
        rebuild_scores(zarr_store, iver_path, profile, experiments)
        return
    missing = sorted(set(experiments) - postprocessed_experiments(zarr_store))
    if not missing:
        logger.info('%s is up to date', zarr_store)
        return
    write_experiments(zarr_store, iver_path, profile, missing)
    logger.info('updated %s', zarr_store)
