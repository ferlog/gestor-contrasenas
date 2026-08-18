"""Preferencias no secretas de la aplicación (tema, auto-bloqueo, biometría)."""

from __future__ import annotations

import json
import os

from .storage import app_dir_path

_SETTINGS_FILE = os.path.join(app_dir_path(), "settings.json")

DEFAULTS: dict = {
    "theme": "light",  # light | dark | system
    "auto_lock_minutes": 0,  # 0 = nunca
    "biometric": {"fingerprint": True, "face": True},
}


def _path() -> str:
    return _SETTINGS_FILE


def load() -> dict:
    """Carga las preferencias, fusionándolas con los valores por defecto."""
    settings = dict(DEFAULTS)
    try:
        with open(_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for key, value in data.items():
            if key in settings and isinstance(value, type(settings[key])):
                settings[key] = value
        settings["biometric"] = {**DEFAULTS["biometric"], **settings.get("biometric", {})}
    except Exception:  # noqa: BLE001
        pass
    return settings


def save(settings: dict) -> None:
    """Guarda las preferencias en el archivo de configuración."""
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)