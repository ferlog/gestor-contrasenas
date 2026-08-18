"""Almacenamiento cifrado de contraseñas en un archivo local.

El archivo guarda: la sal, los datos cifrados (un token Fernet) y metadatos.
Los datos en texto plano sólo existen en memoria mientras la app está abierta.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import InvalidToken

from . import crypto

APP_DIR_NAME = ".gestor-contrasenas"
DATA_FILE_NAME = "vault.dat"
_FORMAT_VERSION = 1


@dataclass
class Vault:
    """Un registro de credenciales almacenado en memoria (no cifrado)."""

    entries: list[dict[str, str]]

    def __post_init__(self) -> None:
        self.entries = self.entries or []

    def add(self, service: str, username: str, password: str, notes: str = "") -> None:
        """Añade una nueva entrada."""
        self.entries.append(
            {
                "service": service.strip(),
                "username": username.strip(),
                "password": password,
                "notes": notes.strip(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"version": _FORMAT_VERSION, "entries": self.entries}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Vault":
        entries = raw.get("entries", []) if raw else []
        return cls(entries=[dict(e) for e in entries])


def app_dir_path() -> str:
    """Devuelve la ruta de la carpeta de datos de la aplicación."""
    home = os.path.expanduser("~")
    return os.path.join(home, APP_DIR_NAME)


def data_file_path() -> str:
    """Devuelve la ruta completa al archivo del almacén."""
    return os.path.join(app_dir_path(), DATA_FILE_NAME)


def vault_exists() -> bool:
    return os.path.isfile(data_file_path())


def load_vault(password: str) -> Vault:
    """Carga y descifra el almacén.

    Lanza InvalidToken si la contraseña maestra es incorrecta.
    Lanza FileNotFoundError si aún no existe el archivo.
    """
    path = data_file_path()
    with open(path, "rb") as fh:
        blob = json.load(fh)

    salt = bytes.fromhex(blob["salt"])
    token = bytes.fromhex(blob["data"])
    plain = crypto.decrypt_data(password, salt, token)
    return Vault.from_dict(json.loads(plain.decode("utf-8")))


def save_vault(password: str, vault: Vault) -> None:
    """Cifra y guarda el almacén en el archivo local."""
    salt = crypto.generate_salt()
    plain = json.dumps(vault.to_dict(), ensure_ascii=False).encode("utf-8")
    token = crypto.encrypt_data(password, salt, plain)
    blob = {"format": _FORMAT_VERSION, "salt": salt.hex(), "data": token.hex()}

    path = data_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)


def reset_vault() -> None:
    """Elimina el almacén. Usar sólo para restablecer la contraseña maestra."""
    try:
        os.remove(data_file_path())
    except FileNotFoundError:
        pass


def export_vault(dest_path: str) -> None:
    """Copia el archivo cifrado del almacén a `dest_path` (copia de seguridad)."""
    src = data_file_path()
    if not os.path.isfile(src):
        raise FileNotFoundError("No existe ningún almacén para exportar.")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(src, "rb") as fh_in, open(dest_path, "wb") as fh_out:
        fh_out.write(fh_in.read())


def import_vault(src_path: str) -> None:
    """Sustituye el almacén actual por el archivo cifrado de `src_path`.

    Tras importar, deberás desbloquear con la contraseña maestra del respaldo.
    """
    if not os.path.isfile(src_path):
        raise FileNotFoundError("No se encontró el archivo de respaldo.")
    os.makedirs(os.path.dirname(data_file_path()), exist_ok=True)
    with open(src_path, "rb") as fh_in, open(data_file_path(), "wb") as fh_out:
        fh_out.write(fh_in.read())
