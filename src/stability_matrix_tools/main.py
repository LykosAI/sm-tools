from stability_matrix_tools import updates, b2, cf, keys
import typer

app = typer.Typer(no_args_is_help=True)
app.add_typer(updates.app, name="updates")
app.add_typer(b2.app, name="b2")
app.add_typer(cf.app, name="cf")
app.add_typer(keys.app, name="keys")
