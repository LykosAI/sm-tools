"""Keys and signing."""
from stability_matrix_tools.utils import signing

import typer
import pyperclip
from rich import print as cp

app = typer.Typer()


@app.command()
def new_private():
    """Generate a new private key. Saves to keyring."""
    # check exists
    if signing.get_private_key_keyring():
        cp("❌  Private key already exists.")
        raise SystemExit(1)

    # generate
    cp("Generating new private Ed25519 key...")
    private_key = signing.generate_private_key()
    signing.save_private_key_keyring(private_key)
    cp("✅  Private key saved to keyring.")


@app.command()
def set_private():
    """Set private key from clipboard."""
    ssh_key = pyperclip.paste()
    private_key = signing.ssh_to_key(ssh_key)
    signing.save_private_key_keyring(private_key)
    cp("✅  Private key saved to keyring.")


@app.command()
def get_private():
    """Loads current private key to clipboard."""
    private_key = signing.get_private_key_keyring()
    if not private_key:
        cp("❌  Private key does not exist.")
        raise SystemExit(1)

    ssh_key = signing.private_key_to_ssh(private_key)
    pyperclip.copy(ssh_key)
    cp("✅  Private key copied to clipboard.")


@app.command()
def get_public():
    """Loads current public key to clipboard."""
    public_key = signing.get_public_key_keyring()
    if not public_key:
        cp("❌  Private key not found.")
        raise SystemExit(1)

    ssh_pub_key = signing.public_key_to_ssh(public_key)
    pyperclip.copy(ssh_pub_key)
    cp(ssh_pub_key)
    cp("✅  Public key copied to clipboard.")
