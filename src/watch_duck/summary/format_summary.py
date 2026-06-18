import numpy as np
import pandas as pd

from watch_duck.common.state import decode_state, encode_state

cmap_red_green_names = [
    'red1',
    'orange_red1',
    'dark_orange',
    'orange1',
    'gold1',
    'yellow1',
    'yellow2',
    'green_yellow',
    'chartreuse1',
    'color(82)',
    'green1',
]

cmap_red_green_rgb = [
    (255, 0, 0),
    (255, 95, 0),
    (255, 135, 0),
    (255, 175, 0),
    (255, 215, 0),
    (255, 255, 0),
    (215, 255, 0),
    (175, 255, 0),
    (135, 255, 0),
    (95, 255, 0),
    (0, 255, 0),
]


def format_title(family, delta_t, exclude_aborted, exclude_suspended, last_update):
    excluding = ''
    if exclude_aborted and exclude_suspended:
        excluding = ', excluding aborted and suspended'
    elif exclude_aborted:
        excluding = ', excluding aborted'
    elif exclude_suspended:
        excluding = ', excluding suspended'
    return f"""[green]Progress of the "{family}" stage (last valid {delta_t}{excluding})
last update: {format_date(last_update)} UTC ({format_recent_past(last_update)})[/]"""


def format_finished_title(last_update):
    return f"""[green]Recently finished experiments
last update: {format_date(last_update)} UTC ({format_recent_past(last_update)})[/]"""


def format_state(state):
    state = decode_state(state)
    color = {
        'unknown': 'red',
        'complete': 'bright_yellow',
        'queued': 'bright_cyan',
        'active': 'green',
        'aborted': 'red',
        'suspended': 'yellow',
        'submitted': 'bright_cyan',
    }
    return f'[{color[state]}]{state}[/]'


def format_date(date):
    date = pd.Timestamp(date).ceil('h')
    return date.strftime('%Y-%m-%d %H:%M')


def format_date_color(color, date):
    return f'[{color}]{format_date(date)}[/]'


def format_recent_past(date):
    date = pd.Timestamp(date).tz_localize('UTC').ceil('min')
    now = pd.Timestamp.now('UTC').ceil('min')
    delta = now - date
    if delta < pd.Timedelta('1h'):
        return f'{delta.components.minutes} mins ago'
    if delta < pd.Timedelta('1d'):
        delta = delta.total_seconds() / 3600
        return f'{delta:.1f} hours ago'
    delta = delta.total_seconds() / (3600 * 24)
    return f'{delta:.1f} days ago'


def format_progress(color, index, total, progress):
    return f'[{color}]{index} / {total} ({progress:.2f}%)[/]'


def format_speed(color, speed):
    return f'[{color}]{speed:.2f}[/]'


def format_remaining(color, remaining):
    remaining = pd.Timedelta(remaining).total_seconds() / (3600 * 24)
    return f'[{color}]{remaining:.1f} days[/]'


def format_eta(color, eta):
    eta = pd.Timestamp(eta).ceil('d')
    eta = eta.strftime('%Y-%m-%d')
    return f'[{color}]{eta}[/]'


def format_summary_line(summary, vref_fc, vref_lw, vref_elda):
    exp = str(summary.exp.to_numpy())
    suite = str(summary.suite.to_numpy())
    experiment_type = str(summary.experiment_type.to_numpy())
    state = int(summary.state.to_numpy())
    state = format_state(state)
    index = int(summary.index.to_numpy())
    total = int(summary.total.to_numpy())
    progress = float(summary.progress.to_numpy())
    progress_color = int(progress * (len(cmap_red_green_names) - 2))
    progress_color = max(0, min(progress_color, len(cmap_red_green_names) - 1))
    progress_color = cmap_red_green_names[progress_color]
    progress = format_progress(progress_color, index, total, 100 * progress)
    date = np.datetime64(summary.date_current.to_numpy())
    date = format_date_color(progress_color, date)
    speed_it_day = float(summary.speed_it_day.to_numpy())
    vref = {'fc': vref_fc, 'lw': vref_lw, 'elda': vref_elda}[experiment_type]
    speed_color = int(speed_it_day / vref * (len(cmap_red_green_names) - 1))
    speed_color = max(0, min(speed_color, len(cmap_red_green_names) - 1))
    speed_color = cmap_red_green_names[speed_color]
    speed_day_day = float(summary.speed_day_day.to_numpy())
    if speed_it_day > 0:
        remaining = np.timedelta64(summary.remaining.to_numpy())
        remaining = format_remaining(speed_color, remaining)
        eta = np.datetime64(summary.eta.to_numpy())
        eta = format_eta(speed_color, eta)
    else:
        remaining = ''
        eta = ''
    speed_it_day = format_speed(speed_color, speed_it_day)
    speed_day_day = format_speed(speed_color, speed_day_day)
    if index == total:
        state = format_state(encode_state('complete'))
        speed_it_day = ''
        speed_day_day = ''
        remaining = ''
        eta = ''
    return (
        exp,
        suite,
        experiment_type,
        state,
        progress,
        date,
        speed_it_day,
        speed_day_day,
        remaining,
        eta,
    )


def format_finished_line(finished):
    exp = str(finished.finished_exp.to_numpy())
    suite = str(finished.finished_suite.to_numpy())
    experiment_type = str(finished.finished_experiment_type.to_numpy())
    finished_date = np.datetime64(finished.finished_date.to_numpy())
    last_update = np.datetime64(finished.time.to_numpy())
    delta = pd.Timestamp(last_update) - pd.Timestamp(finished_date)
    delta = 1 - delta / pd.Timedelta('240h')
    delta_color = int(delta * (len(cmap_red_green_names) - 1))
    delta_color = max(0, min(delta_color, len(cmap_red_green_names) - 1))
    delta_color = cmap_red_green_names[delta_color]
    finished_date = format_date_color(delta_color, finished_date)
    return exp, suite, experiment_type, finished_date
