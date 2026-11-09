
"""Phoenix command-line interface."""

import typer

app = typer.Typer(
    name="phoenix",
    help="Automated PostgreSQL recovery testing.",
    no_args_is_help=True,
)


@app.callback()
def main():
    """Phoenix CLI entry point."""
    pass


@app.command()
def version():
    """Display Phoenix version."""
    from phoenix import __version__

    typer.echo(f"Phoenix v{__version__}")


if __name__ == "__main__":
    app()
