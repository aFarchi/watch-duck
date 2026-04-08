import logging

import rich.logging
import rich_click as click

import watch_duck.parse

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


if __name__ == '__main__':
    cli()
