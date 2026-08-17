import pandas as pd

from watch_duck.common.live_progress import sub_task_progress_bar


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
    with sub_task_progress_bar() as sp:  # ruff:ignore[multiple-with-statements]
        with sp.open(log_file, mode='r', encoding=None, description='reading') as f:
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
                        line.replace('# edit ECF_TIME', '').replace("'", '').strip()
                        + ':00'
                    )
                elif line.startswith('family'):
                    name, state = parse_family_line(line)
                    if name in {'experiment_launcher', 'qsuite'}:
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
