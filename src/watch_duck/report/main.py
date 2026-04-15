import pandas as pd
from rich.console import Console
from rich.table import Table

from watch_duck.common.wdir import WorkingDirectory
from watch_duck.report.format_summary import (
    format_eta,
    format_progress,
    format_remaining,
    format_speed,
    format_state,
)
from watch_duck.report.summary import get_summary


def show_summary(
    wdir,
    suite,
    experiment_type,
    family,
    delta_t,
    exclude_aborted,
    exclude_suspended,
):
    wdir = WorkingDirectory(wdir)
    summary = get_summary(
        wdir,
        suite,
        experiment_type,
        delta_t,
        exclude_aborted,
        exclude_suspended,
    )
    table = Table(
        title=f'''Active "{experiment_type}" experiments in suite "{suite}"
Progress with respect to "{family}"''',
    )
    table.add_column('ID', style='cyan')
    table.add_column('State', style='green')
    table.add_column('Progress', style='yellow', justify='right')
    table.add_column('Speed (it/day)', style='magenta', justify='right')
    table.add_column('Speed (day/day)', style='magenta', justify='right')
    table.add_column('Time remaining', style='magenta', justify='right')
    table.add_column('ETA', style='magenta', justify='right')
    for experiment, progress in summary.items():
        table.add_row(
            experiment,
            format_state(progress['state']),
            format_progress(progress[f'index_{family}'], progress['total']),
            format_speed(progress[f'speed_{family}_it_day']),
            format_speed(progress[f'speed_{family}_day_day']),
            format_remaining(
                progress[f'speed_{family}_day_day'],
                progress[f'remaining_{family}'],
            ),
            format_eta(progress[f'speed_{family}_day_day'], progress[f'eta_{family}']),
        )
    console = Console()
    console.print(table)


def save_summary(
    wdir,
    delta_t,
    exclude_aborted,
    exclude_suspended,
):
    wdir = WorkingDirectory(wdir)
    summary = get_summary(
        wdir=wdir,
        delta_t=delta_t,
        exclude_aborted=exclude_aborted,
        exclude_suspended=exclude_suspended,
        suite=None,
        experiment_type=None,
    )
    df = pd.DataFrame(summary).T
    df.to_csv(wdir.get_summary_path())
