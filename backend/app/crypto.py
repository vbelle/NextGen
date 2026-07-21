"""Fernet credential encryption (research.md §9). This is the ONLY place a raw
credential value should ever be decrypted — see tasks.md T087 security pass."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class CredentialKeyMissingError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.environ.get("NEXTGEN_CREDENTIAL_KEY")
    if not key:
        raise CredentialKeyMissingError(
            "NEXTGEN_CREDENTIAL_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode()
    except InvalidToken as exc:
        raise CredentialKeyMissingError(
            "Could not decrypt credential — NEXTGEN_CREDENTIAL_KEY may be wrong "
            "or has changed since this credential was stored."
        ) from exc
