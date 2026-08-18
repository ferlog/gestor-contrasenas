"""Cifrado de datos mediante contraseña maestra.

Usa PBKDF2-HMAC-SHA256 para derivar una clave a partir de la contraseña
maestra y Fernet (AES-128-CBC) para cifrar/descifrar.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

_ITERATIONS = 600_000
_KEY_LEN = 32
SALT_SIZE = 16


def _derive_key(password: str, salt: bytes) -> bytes:
    """Deriva una clave Fernet de 32 bytes desde la contraseña maestra."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_LEN,
    )
    return base64.urlsafe_b64encode(key)


def generate_salt() -> bytes:
    """Genera una sal criptográficamente aleatoria."""
    return os.urandom(SALT_SIZE)


def encrypt_data(password: str, salt: bytes, data: bytes) -> bytes:
    """Cifra `data` y devuelve el token Fernet."""
    fernet = Fernet(_derive_key(password, salt))
    return fernet.encrypt(data)


def decrypt_data(password: str, salt: bytes, token: bytes) -> bytes:
    """Descifra `token` con la contraseña maestra.

    Lanza InvalidToken si la contraseña es incorrecta.
    """
    fernet = Fernet(_derive_key(password, salt))
    return fernet.decrypt(token)
