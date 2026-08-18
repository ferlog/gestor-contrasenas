"""Utilidades para copiar texto al portapapeles."""

from __future__ import annotations

import tkinter as tk

_TIMEOUT_MS = 30_000


def copy_to_clipboard(text: str, root: tk.Misc | None = None) -> None:
    """Copia `text` al portapapeles.

    Usa la ventana raíz si se pasa; en caso contrario crea una temporal
    que se autodestruye tras unos segundos para no dejar datos sensibles.
    """
    if root is not None and root.winfo_exists():
        root.clipboard_clear()
        root.clipboard_append(text)
        return

    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text)
    root.after(_TIMEOUT_MS, root.destroy)
    root.update()
