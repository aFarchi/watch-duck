import logging
import pathlib
import tomllib

import rich.logging
import rich_click as click

import watch_duck.iver
import watch_duck.parse
import watch_duck.report
import watch_duck.summary


def get_config():
    config_file = pathlib.Path('~').expanduser() / '.config/watch-duck.toml'
    with pathlib.Path(config_file).open('rb') as f:
        return tomllib.load(f)


@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option(
    '--debug',
    '-d',
    is_flag=True,
    default=False,
    help='Enable debug logging for all commands.',
)
def cli(debug):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
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


@cli.command(name='report')
def write_report():
    """Write progress report of the active experiments."""
    config = get_config()
    watch_duck.report.write_report(
        **config['main'],
    )


@cli.command(name='download')
def download_report():
    """Download progress report from IVER site."""
    config = get_config()
    watch_duck.report.download_report(
        **config['main'],
    )


@cli.command(name='upload')
def upload_report():
    """Upload progress report to IVER site."""
    config = get_config()
    watch_duck.report.upload_report(
        **config['main'],
    )


@cli.command(name='summary')
@click.option(
    '--suite',
    '-s',
    type=str,
    default='all',
    help='Suite to show (default: "all")',
)
@click.option(
    '--experiment-type',
    '-t',
    type=click.Choice(['fc', 'lw', 'elda', 'all']),
    default='all',
    help='Experiment type to show (default: "all")',
)
@click.option(
    '--family',
    '-f',
    type=click.Choice(['preprocess', 'main', 'postprocess']),
    default='postprocess',
    help='Family to show progress with respect to (default: "postprocess")',
)
def show_summary(suite, experiment_type, family):
    """Show progress of the active experiments."""
    config = get_config()
    watch_duck.summary.show_summary(
        suite=suite,
        experiment_type=experiment_type,
        family=family,
        **config['main'],
        **config['summary'],
    )


@cli.command(name='finished')
def show_finished():
    """Show recently finished experiments."""
    config = get_config()
    watch_duck.summary.show_finished(
        **config['main'],
    )


@cli.command(name='show')
@click.option(
    '--download',
    '-d',
    is_flag=True,
    default=False,
    help='Download before showing.',
)
def show(download):
    """Download show progress report (combination of other commands)."""
    config = get_config()
    if download:
        watch_duck.report.download_report(
            **config['main'],
        )
    for experiment_type in ['fc', 'lw', 'elda']:
        watch_duck.summary.show_summary(
            suite='all',
            experiment_type=experiment_type,
            family='postprocess',
            **config['main'],
            **config['summary'],
        )
    watch_duck.summary.show_finished(
        **config['main'],
    )


@cli.command(name='iver')
def run_iver():
    """Run IVER on compatible forecast experiments."""
    config = get_config()
    for partial in (False, True):
        watch_duck.iver.run_iver(
            **config['main'],
            profiles=config['iver'],
            partial=partial,
        )


if __name__ == '__main__':
    cli()
