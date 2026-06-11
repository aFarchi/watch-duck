import pandas as pd

from watch_duck.common.state import decode_state


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


def format_progress(index, total):
    return f'{int(index)} / {total} ({100 * index / total:.2f}%)'


def format_speed(speed):
    if speed > 0:
        return f'[green]{speed:.2f}[/]'
    return f'[red]{speed:.2f}[/]'


def format_remaining(speed, remaining):
    if speed > 0:
        remaining = pd.Timedelta(remaining).total_seconds() / (3600 * 24)
        return f'[green]{remaining:.1f} days[/]'
    return ''


def format_eta(speed, eta):
    eta = pd.Timestamp(eta).ceil('d')
    if speed > 0:
        eta = eta.strftime('%Y-%m-%d')
        return f'[green]{eta}[/]'
    return ''
