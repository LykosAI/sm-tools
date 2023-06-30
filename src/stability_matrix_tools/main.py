from stability_matrix_tools import updates, b2
import typer

app = typer.Typer()
app.add_typer(updates.app, name="updates")
app.add_typer(b2.app, name="b2")
