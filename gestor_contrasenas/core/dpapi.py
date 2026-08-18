"""Protección de secretos con DPAPI (Windows Data Protection API).

Permite cifrar datos de forma que sólo el usuario actual de Windows puede
descifrarlos, sin exponer ninguna clave en el código.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes

_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt_protect(data: bytes) -> bytes:
    p = ctypes.windll.crypt32.CryptProtectData
    p.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    p.restype = ctypes.wintypes.BOOL

    in_blob = _DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
    out_blob = _DATA_BLOB()

    if not p(ctypes.byref(in_blob), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
        raise ctypes.WinError()

    result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return result


def _crypt_unprotect(data: bytes) -> bytes:
    p = ctypes.windll.crypt32.CryptUnprotectData
    p.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    p.restype = ctypes.wintypes.BOOL

    in_blob = _DATA_BLOB(len(data), ctypes.cast(data, ctypes.POINTER(ctypes.c_char)))
    out_blob = _DATA_BLOB()

    if not p(ctypes.byref(in_blob), None, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
        raise ctypes.WinError()

    result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return result


def protect(data: bytes) -> bytes:
    """Cifra `data` con DPAPI (sólo el usuario actual podrá descifrarlo)."""
    return _crypt_protect(data)


def unprotect(data: bytes) -> bytes:
    """Descifra un blob DPAPI creado por `protect`."""
    return _crypt_unprotect(data)
