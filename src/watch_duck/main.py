import logging
import pathlib
import tomllib

import rich.logging
import rich_click as click

import watch_duck.parse
import watch_duck.report

logger = logging.getLogger(__name__)


def get_config():
    config_file = pathlib.Path('~').expanduser() / '.config/watch-duck.toml'
    with pathlib.Path(config_file).open('rb') as f:
        return tomllib.load(f)


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def cli():
    logging.basicConfig(
        level='INFO',
        format='%(message)s',
        datefmt='[%X]',
        handlers=[rich.logging.RichHandler()],
    )


@cli.command(name='parse')
def parse_log_files():
    """Parse log files in the specified directory."""
    config = get_config()
    watch_duck.parse.parse_log_files(
        **config['main'],
        **config['parse'],
    )


@cli.group(name='summary')
def summary():
    pass


@summary.command(name='show')
@click.option(
    '--suite',
    '-s',
    type=str,
    default='daaf',
    help='Suite to show (default: "daaf")',
)
@click.option(
    '--experiment-type',
    '-t',
    type=click.Choice(['fc', 'lw', 'elda']),
    default='fc',
    help='Experiment type to show (default: "fc")',
)
@click.option(
    '--family',
    '-f',
    type=click.Choice(['ini', 'obs', 'fc', 'main', 'lag']),
    default='lag',
    help='Node to show progress with respect to (default: "lag")',
)
def show_summary(suite, experiment_type, family):
    """Show progress of the active experiments."""
    config = get_config()
    watch_duck.report.show_summary(
        suite=suite,
        experiment_type=experiment_type,
        family=family,
        **config['main'],
        **config['summary'],
    )


@summary.command(name='save')
def save_summary():
    """Save progress of the active experiments."""
    config = get_config()
    watch_duck.report.save_summary(
        **config['main'],
        **config['summary'],
    )


if __name__ == '__main__':
    cli()
