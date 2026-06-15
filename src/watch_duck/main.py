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


@cli.command(name='report')
def write_report():
    """Write progress report of the active experiments."""
    config = get_config()
    watch_duck.report.write_report(
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


@cli.command(name='iver')
@click.argument('iver_config', type=str)
@click.option(
    '--partial',
    '-p',
    is_flag=True,
    default=False,
    help='Run partial IVER on unfinished experiments (default: False)',
)
def run_iver(iver_config, partial):
    """Run IVER with a given config on compatible experiments."""  # noqa: DOC501
    config = get_config()
    if iver_config not in config.get('iver', {}):
        message = (
            f'Invalid IVER config "{iver_config}". '
            f'Available configs: {config.get("iver", {}).keys()}'
        )
        raise click.BadParameter(message)
    watch_duck.iver.run_iver(
        **config['main'],
        **config['iver'][iver_config],
        profile=iver_config,
        partial=partial,
    )


if __name__ == '__main__':
    cli()
