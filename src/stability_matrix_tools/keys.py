"""Keys and signing."""
import base64
from typing import Annotated

from stability_matrix_tools.utils import signing

import typer
import pyperclip
from typer import Option
from rich import print as cp

app = typer.Typer(no_args_is_help=True)


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
def get_public(key_format: Annotated[str, Option("--format")] = "openssh"):
    """Loads current public key to clipboard."""
    public_key = signing.get_public_key_keyring()
    if not public_key:
        cp("❌  Private key not found.")
        raise SystemExit(1)

    if key_format == "openssh":
        pub_key = signing.public_key_to_ssh(public_key)
    elif key_format == "b64":
        pub_key_bytes = signing.public_key_to_bytes(public_key)
        pub_key = base64.b64encode(pub_key_bytes).decode("utf-8")
    else:
        cp("❌  Invalid key format.")
        raise SystemExit(1)
    pyperclip.copy(pub_key)
    cp(pub_key)
    cp("✅  Public key copied to clipboard.")


@app.command()
def sign(message: str):
    """Sign a message with the current private key. Produces base64 signature."""
    private_key = signing.get_private_key_keyring()
    if not private_key:
        cp("❌  Private key not found.")
        raise SystemExit(1)

    signature = private_key.sign(message.encode("utf-8"))
    b64_signature = base64.b64encode(signature).decode("utf-8")

    cp(b64_signature)
    pyperclip.copy(b64_signature)
    cp("✅  Signature copied to clipboard.")


@app.command()
def verify(
    message: str, signature: str, public_key: Annotated[str, Option("--key")] = None
):
    """
    Verify a message with the current public key. Expects base64 signature.
    Optionally supply a different public key to use.
    """
    public_key = public_key or signing.get_public_key_keyring()
    if not public_key:
        cp("❌  Public key not found.")
        raise SystemExit(1)

    try:
        signature = base64.b64decode(signature)
    except Exception as e:
        cp(f"❌  Signature is not valid base64: {e}")
        raise SystemExit(1)

    try:
        public_key.verify(signature, message.encode("utf-8"))
    except Exception as e:
        cp(f"❌  Signature verification failed.")
        raise SystemExit(1)
    else:
        cp("✅  Signature verified.")
