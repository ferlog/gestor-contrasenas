"""Acceso biométrico (huella/rostro/PIN) mediante Windows Hello.

La contraseña maestra se guarda cifrada con DPAPI. Cuando se desbloquea con
huella, Windows Hello confirma la identidad y luego se recupera la contraseña
maestra protegida, que se usa para descifrar el almacén.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading

from . import dpapi
from .storage import data_file_path

_CRED_FILE = os.path.join(os.path.dirname(data_file_path()), "biometric.dat")

# Módulos winrt (sólo disponibles en Windows 10+).
try:
    from winrt.windows.security.credentials.ui import (
        UserConsentVerifier,
        UserConsentVerifierAvailability,
        UserConsentVerificationResult,
    )

    _WINRT_OK = True
except Exception:  # noqa: BLE001
    UserConsentVerifier = None  # type: ignore[assignment]
    _WINRT_OK = False


def _run(coro) -> object:
    """Ejecuta una corrutina winrt en un hilo con su propio event loop."""
    result: dict = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def is_supported() -> bool:
    """Indica si el módulo biométrico de Windows está disponible."""
    return _WINRT_OK


def device_available() -> bool:
    """Indica si hay un dispositivo biométrico (huella/rostro) configurado."""
    if not _WINRT_OK:
        return False
    try:
        async def _check() -> object:
            return await UserConsentVerifier.check_availability_async()
        availability = _run(_check())
        return availability == UserConsentVerifierAvailability.AVAILABLE
    except Exception:  # noqa: BLE001
        return False


def request_verification(message: str = "Confirma tu identidad para desbloquear el gestor") -> bool:
    """Pide confirmación biométrica al usuario. Devuelve True si fue verificada."""
    if not _WINRT_OK:
        return False
    try:
        async def _request() -> object:
            return await UserConsentVerifier.request_verification_async(message)
        result = _run(_request())
        return result == UserConsentVerificationResult.VERIFIED
    except Exception:  # noqa: BLE001
        return False


def _read_blob() -> bytes | None:
    if not os.path.isfile(_CRED_FILE):
        return None
    try:
        with open(_CRED_FILE, "rb") as fh:
            return bytes.fromhex(fh.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _write_blob(blob: bytes) -> None:
    os.makedirs(os.path.dirname(_CRED_FILE), exist_ok=True)
    with open(_CRED_FILE, "w", encoding="utf-8") as fh:
        fh.write(blob.hex())


def credential_available() -> bool:
    """Indica si existe una credencial biométrica guardada (ya habilitada)."""
    return _read_blob() is not None


def enable(master_password: str) -> None:
    """Guarda la contraseña maestra protegida con DPAPI para acceso por huella."""
    payload = json.dumps({"p": master_password}).encode("utf-8")
    _write_blob(dpapi.protect(payload))


def disable() -> None:
    """Elimina la credencial biométrica guardada."""
    try:
        os.remove(_CRED_FILE)
    except FileNotFoundError:
        pass


def retrieve_password() -> str | None:
    """Recupera la contraseña maestra desde la credencial biométrica."""
    blob = _read_blob()
    if blob is None:
        return None
    try:
        payload = dpapi.unprotect(blob)
        return json.loads(payload.decode("utf-8")).get("p")
    except Exception:  # noqa: BLE001
        return None
