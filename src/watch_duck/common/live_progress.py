import rich.console
import rich.live
import rich.panel
import rich.progress


def overall_progres_bar():
    return rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn('[green]{task.description}'),
        rich.progress.BarColumn(),
        rich.progress.MofNCompleteColumn(),
        rich.progress.TextColumn('•'),
        rich.progress.TaskProgressColumn(),
        rich.progress.TextColumn('• Elapsed:'),
        rich.progress.TimeElapsedColumn(),
        rich.progress.TextColumn('• Remaining:'),
        rich.progress.TimeRemainingColumn(),
    )


def main_task_progress_bar():
    return rich.progress.Progress(
        rich.progress.TextColumn('    [cyan]{task.description}'),
        rich.progress.BarColumn(),
        rich.progress.MofNCompleteColumn(),
        rich.progress.TextColumn('•'),
        rich.progress.TaskProgressColumn(),
    )


def sub_task_progress_bar():
    return rich.progress.Progress(
        rich.progress.TextColumn('        [red]{task.description}'),
        rich.progress.SpinnerColumn('simpleDots'),
        rich.progress.BarColumn(),
        rich.progress.TaskProgressColumn(),
        rich.progress.TextColumn('• Elapsed:'),
        rich.progress.TimeElapsedColumn(),
        transient=True,
    )


class OverallProgress:
    def __init__(self, log_files):
        total = len(log_files)
        self.overall_progress = overall_progres_bar()
        self.main_tasks = main_task_progress_bar()
        self.progress_group = rich.panel.Panel(
            rich.console.Group(
                self.overall_progress,
                self.main_tasks,
            ),
        )
        self.id_overall = self.overall_progress.add_task(
            'Parsing log files',
            total=total,
        )
        self.id_read = self.main_tasks.add_task('├─ Reading', total=total)
        self.id_save = self.main_tasks.add_task('├─ Saving', total=total)
        self.id_cleanup = self.main_tasks.add_task('└─ Clean-up', total=total)

    def read_one(self):
        self.main_tasks.update(self.id_read, advance=1)

    def save_one(self):
        self.main_tasks.update(self.id_save, advance=1)

    def cleanup_one(self):
        self.main_tasks.update(self.id_cleanup, advance=1)

    def overall_one(self):
        self.overall_progress.update(self.id_overall, advance=1)

    def all_one(self):
        self.read_one()
        self.save_one()
        self.cleanup_one()
        self.overall_one()

    def open_live(self):
        return rich.live.Live(self.progress_group)
