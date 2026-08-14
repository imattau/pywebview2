from __future__ import annotations

import os
import subprocess
import sys

import click

from webview.cli.config import ConfigError
from webview.cli.config import load as load_config


@click.command()
@click.option('--config', 'config_path', default=None, type=click.Path(exists=True))
def dev(config_path: str | None) -> None:
    """
    Run the app for development, with debug mode / devtools enabled.

    Phase 1: runs the entry point once with PYWEBVIEW_DEV=1 set. Frontend
    hot-reload (file watching + live reload) lands in a later phase; for now
    edit-then-Ctrl-C-and-rerun is the workflow, same as running the entry
    point directly but with debug/devtools switched on.
    """
    try:
        config = load_config(config_path)
    except ConfigError as e:
        raise click.ClickException(str(e)) from e

    project_dir = os.path.dirname(os.path.abspath(config_path)) if config_path else os.getcwd()
    entry_path = os.path.join(project_dir, config['entry'])
    if not os.path.exists(entry_path):
        raise click.ClickException(f'Entry point not found: {entry_path}')

    env = os.environ.copy()
    env['PYWEBVIEW_DEV'] = '1'

    click.echo(f'Running {entry_path} (PYWEBVIEW_DEV=1)...')
    result = subprocess.run([sys.executable, entry_path], cwd=project_dir, env=env)
    sys.exit(result.returncode)
