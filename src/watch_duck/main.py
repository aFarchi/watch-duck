import logging

import rich.logging
import rich_click as click

import watch_duck.parse
import watch_duck.show

logger = logging.getLogger(__name__)


@click.group(context_settings={'help_option_names': ['-h', '--help']})
def cli():
    logging.basicConfig(
        level='INFO',
        format='%(message)s',
        datefmt='[%X]',
        handlers=[rich.logging.RichHandler()],
    )


@cli.command(name='parse')
@click.argument('wdir', type=click.Path(exists=True, file_okay=False))
def parse_log_files(wdir):
    """Parse log files in the specified directory."""
    logger.info('Parsing log files in directory: "%s"', wdir)
    watch_duck.parse.parse_log_files(wdir)


@cli.command(name='show')
@click.argument('wdir', type=click.Path(exists=True, file_okay=False))
@click.option(
    '--experiment-type',
    '-t',
    type=click.Choice(['fc', 'lw', 'elda']),
    default='fc',
    help='Experiment type to show (default: "fc")',
)
@click.option(
    '--wrt',
    '-w',
    type=click.Choice(['ini', 'obs', 'fc', 'main', 'lag']),
    default='lag',
    help='Node to show progress with respect to (default: "lag")',
)
def show_progress(wdir, experiment_type, wrt):
    """Show progress of the active experiments."""
    logger.info('Showing progress of the active experiments in directory: "%s"', wdir)
    watch_duck.show.show_progress(wdir, experiment_type, wrt)


if __name__ == '__main__':
    cli()
