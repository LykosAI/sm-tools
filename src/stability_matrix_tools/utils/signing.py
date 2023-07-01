import keyring

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def private_key_to_ssh(private_key: Ed25519PrivateKey) -> str:
    key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return key_bytes.decode("utf-8")


def public_key_to_ssh(public_key: Ed25519PublicKey) -> str:
    key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return key_bytes.decode("utf-8")


def ssh_to_key(key: str) -> Ed25519PrivateKey:
    key_bytes = key.encode("utf-8")
    return serialization.load_ssh_private_key(key_bytes, None)


def get_private_key_keyring() -> Ed25519PrivateKey | None:
    """Get the private key from the keyring."""
    key_bytes = keyring.get_password("sm-tools", "private-key")
    if key_bytes is None:
        return None
    key = serialization.load_ssh_private_key(key_bytes.encode("utf-8"), None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Key is not an Ed25519PrivateKey")
    return key


def save_private_key_keyring(private_key: Ed25519PrivateKey) -> None:
    """Save the private key to the keyring."""
    key = private_key_to_ssh(private_key)
    keyring.set_password("sm-tools", "private-key", key)


def get_public_key_keyring() -> Ed25519PublicKey | None:
    """Get the public key from the keyring."""
    private_key = get_private_key_keyring()
    if private_key is None:
        return None
    return private_key.public_key()


def verify_signature(public_key, signature):
    ...
