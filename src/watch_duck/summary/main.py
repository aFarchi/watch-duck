import numpy as np
import pandas as pd
import xarray as xr
from rich.console import Console
from rich.table import Table

from watch_duck.common.state import encode_state
from watch_duck.common.wdir import WorkingDirectory
from watch_duck.summary.format_summary import (
    format_finished_line,
    format_finished_title,
    format_summary_line,
    format_title,
)


def get_summary(ds, delta_t, exclude_aborted, exclude_suspended):
    ds['total'] = 1 + (ds.date_end - ds.date_start) // (
        pd.Timedelta('1h') * ds.date_freq
    )
    ds['date_current'] = ds.date_start + pd.Timedelta('1h') * ds.date_freq * np.maximum(
        ds.index.isel(time=-1, drop=True),
        0,
    )
    ds['index'] = xr.where(ds.index >= 0, ds.index, np.nan)
    delta_index = ds.index.diff(dim='time', label='lower')
    hours_valid = xr.where(ds.state.isel(time=slice(0, -1)) != -1, 1, 0)
    hours_non_aborted = xr.where(
        ds.state.isel(time=slice(0, -1)) != encode_state('aborted'),
        1,
        0,
    )
    hours_non_suspended = xr.where(
        ds.state.isel(time=slice(0, -1)) != encode_state('suspended'),
        1,
        0,
    )
    if exclude_aborted:
        hours_valid *= hours_non_aborted
    if exclude_suspended:
        hours_valid *= hours_non_suspended
    delta_t = pd.Timedelta(delta_t) / pd.Timedelta('1h')
    cum_hours = (
        hours_valid
        .isel(time=slice(None, None, -1))
        .cumsum(dim='time')
        .isel(time=slice(None, None, -1))
    )
    selected_hours = xr.where(cum_hours < delta_t + 1, 1, 0)
    delta_index = (selected_hours * delta_index).sum(dim='time')
    delta_hours = (selected_hours * hours_valid).sum(dim='time')
    ds['speed_it_day'] = xr.where(delta_hours > 0, delta_index / delta_hours * 24, 0)
    ds['speed_day_day'] = ds['speed_it_day'] * ds.date_freq / 24
    ds['remaining'] = xr.where(
        ds['speed_day_day'] > 0,
        (ds.date_end - ds.date_current) / ds['speed_day_day'],
        np.timedelta64('NaT'),
    )
    ds['eta'] = xr.where(
        ds['speed_day_day'] > 0,
        pd.Timestamp.now() + ds['remaining'],
        np.datetime64('NaT'),
    )
    ds['progress'] = ds.index.isel(time=-1) / ds.total
    return ds.isel(time=-1)


def show_summary(
    wdir,
    suite,
    experiment_type,
    family,
    delta_t,
    exclude_aborted,
    exclude_suspended,
    vref_fc,
    vref_lw,
    vref_elda,
):
    wdir = WorkingDirectory(wdir)
    report = wdir.get_report().load()
    if suite != 'all':
        report = report.where(report.suite == suite, drop=True)
    if experiment_type != 'all':
        report = report.where(report.experiment_type == experiment_type, drop=True)
    report = report.rename({f'index_{family}': 'index'})
    report = report.drop_vars(
        name
        for name in report.data_vars
        if name.endswith(('_preprocess', '_main', '_postprocess'))
    )
    summary = get_summary(report, delta_t, exclude_aborted, exclude_suspended)
    summary = summary.sortby([
        summary.experiment_type,
        summary.suite,
        -summary.progress,
    ])
    table = Table(
        title=format_title(
            family,
            delta_t,
            exclude_aborted,
            exclude_suspended,
            np.datetime64(summary.time.to_numpy()),
        ),
    )
    table.add_column('ID', style='cyan')
    table.add_column('Suite', style='cyan')
    table.add_column('Exp. type', style='cyan')
    table.add_column('State', style='green')
    table.add_column('Progress', style='yellow', justify='right')
    table.add_column('Current date', style='yellow', justify='right')
    table.add_column('Speed (it/day)', style='magenta', justify='right')
    table.add_column('Speed (day/day)', style='magenta', justify='right')
    table.add_column('Time remaining', style='magenta', justify='right')
    table.add_column('ETA', style='magenta', justify='right')
    for i in range(len(summary.exp)):
        table.add_row(
            *format_summary_line(summary.isel(exp=i), vref_fc, vref_lw, vref_elda),
        )
    console = Console()
    console.print(table)


def show_finished(wdir):
    wdir = WorkingDirectory(wdir)
    report = wdir.get_report().isel(time=-1).load()
    table = Table(title=format_finished_title(np.datetime64(report.time.to_numpy())))
    table.add_column('ID', style='cyan')
    table.add_column('Suite', style='cyan')
    table.add_column('Exp. type', style='cyan')
    table.add_column('Last active at', style='green')
    for i in range(len(report.finished_exp)):
        table.add_row(*format_finished_line(report.isel(finished_exp=i)))
    console = Console()
    console.print(table)
