import logging

from watch_duck.common.live_progress import OverallProgress, sub_task_progress_bar
from watch_duck.common.wdir import WorkingDirectory
from watch_duck.parse.exp_progress import get_experiment_type, save_experiment_progress
from watch_duck.parse.exp_state import save_experiment_state
from watch_duck.parse.parse import parse_suite

logger = logging.getLogger(__name__)


def save_experiment(
    wdir,
    suite,
    exclude_experiments,
    exclude_experiment_types,
    chunk_size_state,
    chunk_size_progress,
):
    active_experiments = {}
    with sub_task_progress_bar() as sp:
        for name, experiment in sp.track(
            suite['experiments'].items(),
            description='saving',
        ):
            if name in exclude_experiments:
                continue
            logger.debug('scanning experiment %s/%s', suite['name'], name)
            experiment_type = get_experiment_type(experiment)
            if experiment_type in exclude_experiment_types:
                continue
            save_experiment_state(
                wdir,
                name,
                experiment,
                suite['date'],
                chunk_size_state,
            )
            save_experiment_progress(
                wdir,
                name,
                experiment_type,
                experiment,
                suite['date'],
                suite['name'],
                chunk_size_progress,
            )
            active_experiments[name] = experiment_type
    return active_experiments


def parse_log_files(
    wdir,
    suites,
    exclude_experiments,
    exclude_experiment_types,
    chunk_size_state,
    chunk_size_progress,
):
    wdir = WorkingDirectory(wdir)
    log_files = wdir.get_log_files(suites)
    overall_progress = OverallProgress(log_files)
    with overall_progress.open_live():
        for log_file in log_files:
            suite = parse_suite(log_file)
            if suite is None:
                logger.warning('skipping log file (incomplete)')
                overall_progress.all_one()
                continue
            overall_progress.read_one()
            active_experiments = save_experiment(
                wdir,
                suite,
                exclude_experiments,
                exclude_experiment_types,
                chunk_size_state,
                chunk_size_progress,
            )
            overall_progress.save_one()
            wdir.save_active_experiments(suite['name'], active_experiments)
            wdir.archive_log_file(log_file)
            overall_progress.cleanup_one()
            overall_progress.overall_one()
