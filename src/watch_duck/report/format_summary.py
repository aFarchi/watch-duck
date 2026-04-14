def format_state(state):
    color = {
        'complete': 'bright_yellow',
        'queued': 'bright_cyan',
        'active': 'green',
        'aborted': 'red',
        'suspended': 'yellow',
        'submitted': 'bright_cyan',
    }
    return f'[{color[state]}]{state}[/]'


def format_progress(index, total):
    return f'{index} / {total} ({100 * index / total:.2f}%)'


def format_speed(speed):
    if speed > 0:
        return f'[green]{speed:.2f}[/]'
    return f'[red]{speed:.2f}[/]'


def format_remaining(speed, remaining):
    remaining = remaining.ceil('h')
    if speed > 0:
        return f'[green]{remaining}[/]'
    return f'[red]{remaining}[/]'


def format_eta(speed, eta):
    eta = eta.ceil('h')
    if speed > 0:
        return f'[green]{eta}[/]'
    return f'[red]{eta}[/]'
