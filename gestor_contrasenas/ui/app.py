"""Aplicación de escritorio del gestor de contraseñas (neumórfica)."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..core import biometric, clipboard, faceauth, settings, storage
from ..core.password_gen import generate_password, strength

APP_TITLE = "Gestor de Contraseñas"


def _theme_path() -> str:
    """Devuelve la ruta al tema, tanto en desarrollo como en el exe congelado."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(
            sys._MEIPASS, "gestor_contrasenas", "ui", "neumorphic_theme.json"
        )
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "neumorphic_theme.json")


THEME_PATH = _theme_path()

ACCENT = "#6f9bf2"
DANGER = "#e06c75"
MUTED = "#8a94a8"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme(THEME_PATH)


class PasswordEntry(ctk.CTkFrame):
    """Tarjeta visual para una credencial guardada."""

    def __init__(
        self,
        master,
        service: str,
        username: str,
        password: str,
        notes: str,
        on_delete,
    ) -> None:
        super().__init__(master, corner_radius=16)
        self.password = password

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text=service, font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))

        info = ctk.CTkLabel(self, text=username, font=ctk.CTkFont(size=13), text_color=MUTED)
        info.grid(row=1, column=0, sticky="w", padx=16)

        row = 2
        if notes:
            ctk.CTkLabel(
                self, text=notes, font=ctk.CTkFont(size=12), text_color=MUTED
            ).grid(row=row, column=0, sticky="w", padx=16, pady=(2, 0))
            row += 1

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.grid(row=0, column=1, rowspan=max(row, 2), padx=12, pady=8)
        ctk.CTkButton(
            btn,
            text="Copiar",
            width=90,
            corner_radius=12,
            command=lambda: self._copy(),
        ).pack(pady=2, fill="x")
        ctk.CTkButton(
            btn,
            text="Eliminar",
            width=90,
            corner_radius=12,
            fg_color=DANGER,
            hover_color="#c95660",
            command=on_delete,
        ).pack(pady=2, fill="x")

    def _copy(self) -> None:
        clipboard.copy_to_clipboard(self.password, self.winfo_toplevel())
        self.winfo_toplevel().flash_message("Contraseña copiada al portapapeles")


class LoginFrame(ctk.CTkFrame):
    """Pantalla de contraseña maestra (creación o acceso)."""

    def __init__(self, master, app) -> None:
        super().__init__(master, corner_radius=24, width=380, height=420)
        self.app = app
        self.creating = not storage.vault_exists()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="🔐",
            font=ctk.CTkFont(size=48),
            text_color=ACCENT,
        ).grid(row=0, column=0, pady=(30, 6))
        ctk.CTkLabel(
            self,
            text=APP_TITLE,
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=1, column=0)
        ctk.CTkLabel(
            self,
            text="Contraseña maestra",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).grid(row=2, column=0, pady=(4, 18))

        self.entry = ctk.CTkEntry(self, show="●", placeholder_text="Escribe tu contraseña")
        self.entry.grid(row=3, column=0, padx=30, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self.submit())

        next_row = 4
        if self.creating:
            self.confirm_entry = ctk.CTkEntry(
                self, show="●", placeholder_text="Repite la contraseña"
            )
            self.confirm_entry.grid(row=next_row, column=0, padx=30, sticky="ew")
            self.confirm_entry.bind("<Return>", lambda _e: self.submit())
            next_row += 1

            self.strength_bar = ctk.CTkProgressBar(self)
            self.strength_bar.grid(row=next_row, column=0, padx=30, pady=(10, 2), sticky="ew")
            self.strength_label = ctk.CTkLabel(
                self, text="", font=ctk.CTkFont(size=11), text_color=MUTED
            )
            self.strength_label.grid(row=next_row, column=0, pady=(2, 0), sticky="e", padx=30)
            next_row += 1
            self.entry.bind("<KeyRelease>", self._update_strength)

        self.msg = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color=DANGER)
        self.msg.grid(row=next_row, column=0, pady=(8, 2))
        next_row += 1

        hint = (
            "Crea tu contraseña maestra.\n"
            "La usarás para cifrar tus datos.\n"
            "Si la pierdes, no podrás recuperarlos."
            if self.creating
            else "Ingresa tu contraseña maestra para desbloquear."
        )
        ctk.CTkLabel(self, text=hint, font=ctk.CTkFont(size=12), text_color=MUTED).grid(
            row=next_row, column=0, pady=(4, 18)
        )
        next_row += 1

        ctk.CTkButton(
            self,
            text="Desbloquear" if not self.creating else "Crear almacén",
            corner_radius=16,
            command=self.submit,
        ).grid(row=next_row, column=0, padx=30, pady=(0, 10), sticky="ew")
        next_row += 1

        if not self.creating:
            ctk.CTkButton(
                self,
                text="¿Olvidaste tu contraseña? Restablecer almacén",
                corner_radius=12,
                fg_color="transparent",
                hover_color="#cfd6e2",
                text_color=MUTED,
                command=self._request_reset,
            ).grid(row=next_row, column=0, padx=30, pady=(0, 24), sticky="ew")
            next_row += 1

        self._biometric_row = next_row
        self.entry.focus_set()
        self._setup_biometric()

    def _update_strength(self, _event=None) -> None:
        if not self.creating:
            return
        score, label = strength(self.entry.get())
        self.strength_bar.set(score / 100)
        color = {"Muy fuerte": "#3f8f5f", "Fuerte": "#8fb39b", "Media": "#d4a84b",
                 "Débil": "#e06c75", "Muy débil": DANGER}.get(label, DANGER)
        self.strength_label.configure(text=f"Fortaleza: {label}", text_color=color)

    def _request_reset(self) -> None:
        """Pide confirmación y restablece el almacén (borra todo)."""
        confirm = messagebox.askyesno(
            APP_TITLE,
            "Esto BORRA todas las contraseñas guardadas y la credencial de huella.\n\n"
            "¿Estás seguro de que quieres restablecer el almacén?",
            parent=self,
        )
        if not confirm:
            return
        try:
            storage.reset_vault()
            biometric.disable()
            faceauth.disable()
        except Exception as exc:  # noqa: BLE001
            self.msg.configure(text=f"Error al restablecer: {exc}")
            return
        self.app.lock()  # recarga la pantalla en modo "crear"

    def _setup_biometric(self) -> None:
        """Prepara las opciones biométricas (huella/rostro) según el equipo."""
        self.biometric_btn: ctk.CTkButton | None = None
        self.biometric_check: ctk.CTkCheckBox | None = None

        if not biometric.is_supported():
            return

        def _ready() -> None:
            if not self.winfo_exists():
                return
            if not biometric.device_available():
                return

            row = self._biometric_row
            # Si ya hay credencial y no estamos creando: botón para desbloquear.
            # Si no hay credencial (o estamos creando): casilla para activar.
            if biometric.credential_available() and not self.creating:
                self.biometric_btn = ctk.CTkButton(
                    self,
                    text="🔏  Desbloquear con huella / rostro",
                    corner_radius=16,
                    fg_color="#8fb39b",
                    hover_color="#7ba389",
                    command=self._fingerprint_unlock,
                )
                self.biometric_btn.grid(row=row, column=0, padx=30, pady=(0, 8), sticky="ew")
                row += 1
            else:
                self.biometric_check = ctk.CTkCheckBox(
                    self,
                    text="Activar desbloqueo con huella / rostro",
                    font=ctk.CTkFont(size=12),
                )
                self.biometric_check.grid(row=row, column=0, padx=30, pady=(0, 6), sticky="ew")
                row += 1
                ctk.CTkLabel(
                    self,
                    text=(
                        "Útil si olvidas la contraseña: la biometría te deja entrar."
                        if self.creating
                        else ""
                    ),
                    font=ctk.CTkFont(size=10),
                    text_color=MUTED,
                ).grid(row=row, column=0, padx=30, pady=(0, 8), sticky="ew")
                row += 1

            # Reconocimiento facial independiente (webcam).
            if not self.creating and faceauth.is_supported() and faceauth.credential_available():
                self.face_btn = ctk.CTkButton(
                    self,
                    text="🙂  Desbloquear con rostro (webcam)",
                    corner_radius=16,
                    fg_color="#a3b8cc",
                    hover_color="#8fa8bf",
                    command=self._face_unlock,
                )
                self.face_btn.grid(row=row, column=0, padx=30, pady=(0, 30), sticky="ew")

        self.after(200, _ready)

    def _face_unlock(self) -> None:
        if not faceauth.is_supported():
            self.msg.configure(text="Reconocimiento facial no disponible.")
            return
        self.msg.configure(text="Mírate a la cámara, parpadea y mueve la cabeza…")
        ok, password = faceauth.verify()
        if not ok:
            self.msg.configure(text=password or "No verificado.")
            return
        try:
            vault = storage.load_vault(password)
        except Exception:  # noqa: BLE001
            self.msg.configure(text="Error al desbloquear con el rostro.")
            return
        self.app.unlock(password, vault)

    def _fingerprint_unlock(self) -> None:
        if not biometric.request_verification():
            self.msg.configure(text="Biometría no verificada. Intenta de nuevo.")
            return
        password = biometric.retrieve_password()
        if not password:
            self.msg.configure(text="No se pudo recuperar la credencial biométrica.")
            return
        try:
            vault = storage.load_vault(password)
        except Exception:  # noqa: BLE001
            self.msg.configure(text="Error al desbloquear con biometría.")
            return
        self.app.unlock(password, vault)

    def _maybe_enable_biometric(self, password: str) -> None:
        """Activa el acceso por huella si el usuario marcó la casilla."""
        if self.biometric_check is None or not self.biometric_check.get():
            return
        try:
            biometric.enable(password)
        except Exception:  # noqa: BLE001
            self.msg.configure(text="No se pudo activar la huella.")

    def submit(self) -> None:
        password = self.entry.get()
        if not password:
            self.msg.configure(text="La contraseña no puede estar vacía.")
            return
        if self.creating:
            confirm = self.confirm_entry.get()
            if password != confirm:
                self.msg.configure(text="Las contraseñas no coinciden.")
                return
            if len(password) < 8:
                self.msg.configure(text="Usa al menos 8 caracteres.")
                return
        try:
            if self.creating:
                vault = storage.Vault([])
                storage.save_vault(password, vault)
                self._maybe_enable_biometric(password)
                self.app.unlock(password)
            else:
                vault = storage.load_vault(password)
                self._maybe_enable_biometric(password)
                self.app.unlock(password, vault)
        except Exception:  # contraseña incorrecta o datos corruptos
            self.msg.configure(text="Contraseña incorrecta. Inténtalo de nuevo.")
            self.entry.delete(0, tk.END)
            self.entry.focus_set()


class AddDialog(ctk.CTkToplevel):
    """Diálogo para añadir una nueva credencial."""

    def __init__(self, app, service: str = "") -> None:
        super().__init__(app)
        self.app = app
        self.title("Añadir credencial")
        self.resizable(False, False)
        self.grab_set()
        self.after(50, lambda: self.focus_set())

        frame = ctk.CTkFrame(self, corner_radius=20)
        frame.pack(padx=20, pady=20, fill="both", expand=True)
        frame.grid_columnconfigure(1, weight=1)

        def field(row, label, default="", show=None):
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=13)).grid(
                row=row, column=0, sticky="w", pady=8, padx=(14, 8)
            )
            e = ctk.CTkEntry(frame, show=show)
            e.insert(0, default)
            e.grid(row=row, column=1, sticky="ew", pady=8, padx=(0, 14))
            return e

        self.svc = field(0, "Servicio", default=service)
        self.usr = field(1, "Usuario")
        self.pwd = field(2, "Contraseña", show="●")
        self.notes = field(3, "Notas")

        self.svc.focus_set()

        row = 4
        ctk.CTkButton(
            frame,
            text="Generar",
            corner_radius=12,
            width=100,
            command=self._generate,
        ).grid(row=row, column=1, sticky="e", padx=(0, 14), pady=(4, 0))
        row += 1

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=row, column=0, columnspan=2, pady=16)
        ctk.CTkButton(
            actions, text="Cancelar", corner_radius=14, width=110, command=self.destroy
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Guardar",
            corner_radius=14,
            width=110,
            command=self._save,
        ).pack(side="left", padx=6)

    def _generate(self) -> None:
        self.pwd.delete(0, tk.END)
        self.pwd.insert(0, generate_password())

    def _save(self) -> None:
        service = self.svc.get().strip()
        if not service:
            self.app.flash_message("El servicio es obligatorio")
            return
        self.app.vault.add(
            service=service,
            username=self.usr.get(),
            password=self.pwd.get(),
            notes=self.notes.get(),
        )
        self.app.persist()
        self.destroy()


class GenerateDialog(ctk.CTkToplevel):
    """Diálogo para generar contraseñas configurables."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.app = app
        self.title("Generador de contraseñas")
        self.resizable(False, False)
        self.grab_set()

        frame = ctk.CTkFrame(self, corner_radius=20)
        frame.pack(padx=20, pady=20, fill="both", expand=True)
        frame.grid_columnconfigure(0, weight=1)

        self.result = ctk.CTkEntry(frame, state="readonly")
        self.result.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 4))

        ctk.CTkLabel(
            frame, text="Longitud", font=ctk.CTkFont(size=13)
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(10, 0))
        self.length = ctk.CTkSlider(frame, from_=8, to=64, number_of_steps=56)
        self.length.set(16)
        self.length.grid(row=2, column=0, sticky="ew", padx=14)
        self.length_label = ctk.CTkLabel(frame, text="16", font=ctk.CTkFont(size=12), text_color=MUTED)
        self.length_label.grid(row=2, column=0, sticky="e", padx=14)
        self.length.configure(command=lambda v: self.length_label.configure(text=str(int(v))))

        self.upper = ctk.CTkCheckBox(frame, text="Mayúsculas")
        self.upper.select()
        self.upper.grid(row=3, column=0, sticky="w", padx=14, pady=6)
        self.digits = ctk.CTkCheckBox(frame, text="Dígitos")
        self.digits.select()
        self.digits.grid(row=4, column=0, sticky="w", padx=14)
        self.symbols = ctk.CTkCheckBox(frame, text="Símbolos")
        self.symbols.select()
        self.symbols.grid(row=5, column=0, sticky="w", padx=14, pady=6)

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=6, column=0, pady=14)
        ctk.CTkButton(
            actions,
            text="Generar",
            corner_radius=14,
            width=110,
            command=self._generate,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Copiar",
            corner_radius=14,
            width=110,
            command=self._copy,
        ).pack(side="left", padx=6)

        self._generate()

    def _generate(self) -> None:
        try:
            pwd = generate_password(
                length=int(self.length.get()),
                use_upper=self.upper.get() == 1,
                use_digits=self.digits.get() == 1,
                use_symbols=self.symbols.get() == 1,
            )
        except ValueError:
            pwd = ""
        self.result.configure(state="normal")
        self.result.delete(0, tk.END)
        self.result.insert(0, pwd)
        self.result.configure(state="readonly")

    def _copy(self) -> None:
        pwd = self.result.get()
        if pwd:
            clipboard.copy_to_clipboard(pwd, self)
            self.app.flash_message("Contraseña generada copiada")


class MainFrame(ctk.CTkFrame):
    """Pantalla principal: listado, búsqueda y acciones."""

    def __init__(self, master, app) -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self.search_term = ""

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="🔐 " + APP_TITLE, font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="+ Añadir",
            corner_radius=14,
            command=lambda: AddDialog(app),
        ).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(
            header,
            text="Generador",
            corner_radius=14,
            fg_color="#8fb39b",
            hover_color="#7ba389",
            command=lambda: GenerateDialog(app),
        ).grid(row=0, column=3, padx=(8, 0))
        ctk.CTkButton(
            header,
            text="⚙️",
            corner_radius=14,
            width=42,
            fg_color="#c7d0dd",
            hover_color="#b0bccf",
            command=lambda: SettingsDialog(app, self),
        ).grid(row=0, column=4, padx=(8, 0))
        ctk.CTkButton(
            header,
            text="Cerrar",
            corner_radius=14,
            fg_color=DANGER,
            hover_color="#c95660",
            command=app.lock,
        ).grid(row=0, column=5, padx=(8, 0))

        search_box = ctk.CTkFrame(self, fg_color="transparent")
        search_box.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        search_box.grid_columnconfigure(0, weight=1)

        self.search = ctk.CTkEntry(search_box, placeholder_text="🔍  Buscar servicio o usuario…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", self._on_search)

        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=16)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.empty = ctk.CTkLabel(
            self.list_frame,
            text="Aún no hay credenciales.\nUsa «Añadir» para guardar tu primera contraseña.",
            font=ctk.CTkFont(size=14),
            text_color=MUTED,
        )
        self.empty.grid(row=0, column=0, padx=20, pady=40)

    def _on_search(self, _event) -> None:
        self.search_term = self.search.get().strip().lower()
        self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        entries = self.app.vault.entries
        if self.search_term:
            entries = [
                e
                for e in entries
                if self.search_term in e["service"].lower()
                or self.search_term in e["username"].lower()
                or self.search_term in e["notes"].lower()
            ]

        if not entries:
            self.empty = ctk.CTkLabel(
                self.list_frame,
                text=(
                    "Sin resultados para tu búsqueda."
                    if self.search_term
                    else "Aún no hay credenciales.\nUsa «Añadir» para guardar tu primera contraseña."
                ),
                font=ctk.CTkFont(size=14),
                text_color=MUTED,
            )
            self.empty.grid(row=0, column=0, padx=20, pady=40)
            return

        for i, entry in enumerate(entries):
            card = PasswordEntry(
                self.list_frame,
                service=entry["service"],
                username=entry["username"],
                password=entry["password"],
                notes=entry["notes"],
                on_delete=lambda e=entry: self._delete(e),
            )
            card.grid(row=i, column=0, sticky="ew", padx=8, pady=6)

    def _delete(self, entry) -> None:
        self.app.vault.entries.remove(entry)
        self.app.persist()
        self.refresh()
        self.app.flash_message("Credencial eliminada")


def _section(parent, title: str) -> ctk.CTkFrame:
    """Crea una tarjeta de sección dentro de la configuración."""
    frame = ctk.CTkFrame(parent, corner_radius=16)
    frame.pack(fill="x", padx=16, pady=(10, 6))
    ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(
        anchor="w", padx=14, pady=(12, 4)
    )
    return frame


class SettingsDialog(ctk.CTkToplevel):
    """Diálogo de configuración con biometría, contraseña, respaldo y más."""

    def __init__(self, app, main_frame) -> None:
        super().__init__(app)
        self.app = app
        self.main_frame = main_frame
        self.title("Configuración")
        self.geometry("520x620")
        self.resizable(False, False)
        self.grab_set()

        container = ctk.CTkScrollableFrame(self, corner_radius=0)
        container.pack(fill="both", expand=True)

        self._build_biometric(container)
        self._build_face(container)
        self._build_password(container)
        self._build_security(container)
        self._build_appearance(container)
        self._build_backup(container)
        self._build_danger(container)

    # ---- secciones ----
    def _build_biometric(self, parent) -> None:
        sec = _section(parent, "🔏  Desbloqueo biométrico (Windows Hello)")
        prefs = self.app.prefs.get("biometric", {})
        enabled = biometric.credential_available()

        self.fp_var = tk.BooleanVar(value=enabled and prefs.get("fingerprint", True))
        self.face_var = tk.BooleanVar(value=enabled and prefs.get("face", True))

        ctk.CTkCheckBox(
            sec, text="Usar huella dactilar", variable=self.fp_var,
            command=self._on_biometric_change,
        ).pack(anchor="w", padx=14, pady=(2, 2))
        ctk.CTkCheckBox(
            sec, text="Usar reconocimiento facial", variable=self.face_var,
            command=self._on_biometric_change,
        ).pack(anchor="w", padx=14, pady=(2, 4))
        ctk.CTkLabel(
            sec,
            text=(
                "Windows Hello debe estar configurado en Windows.\n"
                "Huella y rostro comparten la misma verificación del sistema."
                if enabled and biometric.device_available()
                else "No se detecta Windows Hello configurado en este equipo."
            ),
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(2, 8))

        if biometric.device_available():
            ctk.CTkButton(
                sec, text="Probar verificación", corner_radius=12, width=160,
                command=self._test_biometric,
            ).pack(anchor="w", padx=14, pady=(0, 12))

    def _on_biometric_change(self) -> None:
        any_on = self.fp_var.get() or self.face_var.get()
        try:
            if any_on and self.app.master_password:
                biometric.enable(self.app.master_password)
            else:
                biometric.disable()
            self.app.prefs["biometric"] = {
                "fingerprint": self.fp_var.get(),
                "face": self.face_var.get(),
            }
            settings.save(self.app.prefs)
            self.app.flash_message("Preferencias biométricas guardadas")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"No se pudo guardar: {exc}", parent=self)

    def _test_biometric(self) -> None:
        ok = biometric.request_verification("Prueba de reconocimiento biométrico")
        messagebox.showinfo(
            APP_TITLE, "Verificación biométrica correcta ✓" if ok else "No verificada.", parent=self
        )

    def _build_face(self, parent) -> None:
        sec = _section(parent, "🙂  Reconocimiento facial independiente (webcam)")
        state = "Guardado ✓" if faceauth.credential_available() else "No configurado"
        ctk.CTkLabel(
            sec,
            text=(
                "Usa la webcam con InsightFace. Incluye detección de vida "
                "(parpadeo + movimiento de cabeza) para dificultar el engaño con fotos.\n"
                "Estado: " + state + "\n"
                "Nota: es algo menos seguro que Windows Hello (webcam normal)."
            ),
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(2, 8))

        if not faceauth.is_supported():
            ctk.CTkLabel(
                sec,
                text="Librerías de visión no disponibles en este equipo.",
                font=ctk.CTkFont(size=12),
                text_color=DANGER,
            ).pack(anchor="w", padx=14, pady=(0, 12))
            return
        if not faceauth.device_available():
            ctk.CTkLabel(
                sec,
                text="No se detectó una webcam.",
                font=ctk.CTkFont(size=12),
                text_color=MUTED,
            ).pack(anchor="w", padx=14, pady=(0, 12))
            return

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(0, 12))
        ctk.CTkButton(
            row, text="Guardar mi rostro", corner_radius=12, width=140, command=self._enroll_face
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="Probar", corner_radius=12, width=100, command=self._test_face
        ).pack(side="left", padx=(0, 8))
        if faceauth.credential_available():
            ctk.CTkButton(
                row, text="Borrar", corner_radius=12, width=90,
                fg_color=DANGER, hover_color="#c95660", command=self._delete_face,
            ).pack(side="left")

    def _enroll_face(self) -> None:
        if not self.app.master_password:
            messagebox.showwarning(APP_TITLE, "No hay sesión iniciada.", parent=self)
            return
        messagebox.showinfo(
            APP_TITLE,
            "Mírate a la cámara y parpadea con naturalidad.\nSe mostrará una ventana de captura durante unos segundos.",
            parent=self,
        )
        err = faceauth.enroll(self.app.master_password)
        if err:
            messagebox.showerror(APP_TITLE, err, parent=self)
            return
        messagebox.showinfo(APP_TITLE, "Rostro guardado correctamente ✓", parent=self)

    def _test_face(self) -> None:
        if not faceauth.credential_available():
            messagebox.showwarning(APP_TITLE, "Guarda primero tu rostro.", parent=self)
            return
        ok, msg = faceauth.verify()
        messagebox.showinfo(
            APP_TITLE, "Rostro verificado ✓" if ok else (msg or "No verificado."), parent=self
        )

    def _delete_face(self) -> None:
        if not messagebox.askyesno(
            APP_TITLE, "¿Borrar el rostro guardado?", parent=self
        ):
            return
        faceauth.disable()
        messagebox.showinfo(APP_TITLE, "Rostro eliminado.", parent=self)

    def _build_password(self, parent) -> None:
        sec = _section(parent, "🔑  Cambiar contraseña maestra")

        grid = ctk.CTkFrame(sec, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(2, 10))
        grid.grid_columnconfigure(1, weight=1)

        def pw_field(row, label, placeholder):
            ctk.CTkLabel(grid, text=label, font=ctk.CTkFont(size=12)).grid(
                row=row, column=0, sticky="w", pady=4, padx=(0, 8)
            )
            e = ctk.CTkEntry(grid, show="●", placeholder_text=placeholder)
            e.grid(row=row, column=1, sticky="ew", pady=4)
            return e

        self.old_pw = pw_field(0, "Actual", "Contraseña actual")
        self.new_pw = pw_field(1, "Nueva", "Nueva contraseña")
        self.conf_pw = pw_field(2, "Repetir", "Repetir nueva")

        self.strength_bar = ctk.CTkProgressBar(sec)
        self.strength_label = ctk.CTkLabel(sec, text="", font=ctk.CTkFont(size=11), text_color=MUTED)
        self.strength_bar.pack(fill="x", padx=14, pady=(6, 2))
        self.strength_label.pack(anchor="w", padx=14, pady=(0, 4))
        self.new_pw.bind("<KeyRelease>", self._update_strength)

        self.pw_msg = ctk.CTkLabel(sec, text="", font=ctk.CTkFont(size=12), text_color=DANGER)
        self.pw_msg.pack(anchor="w", padx=14)
        ctk.CTkButton(
            sec, text="Cambiar contraseña", corner_radius=12, width=180,
            command=self._change_password,
        ).pack(anchor="w", padx=14, pady=(6, 12))

    def _update_strength(self, _event=None) -> None:
        score, label = strength(self.new_pw.get())
        self.strength_bar.set(score / 100)
        color = {"Muy fuerte": "#3f8f5f", "Fuerte": "#8fb39b", "Media": "#d4a84b",
                 "Débil": "#e06c75", "Muy débil": DANGER}.get(label, DANGER)
        self.strength_label.configure(text=f"Fortaleza: {label}", text_color=color)

    def _change_password(self) -> None:
        old = self.old_pw.get()
        new = self.new_pw.get()
        conf = self.conf_pw.get()
        if not old or not new:
            self.pw_msg.configure(text="Completa todos los campos.")
            return
        if old != self.app.master_password:
            self.pw_msg.configure(text="La contraseña actual no es correcta.")
            return
        if new != conf:
            self.pw_msg.configure(text="La nueva contraseña no coincide con la confirmación.")
            return
        if len(new) < 8:
            self.pw_msg.configure(text="La nueva contraseña debe tener al menos 8 caracteres.")
            return
        self.app.change_master_password(old, new)
        self.pw_msg.configure(text="Contraseña cambiada correctamente.", text_color="#3f8f5f")
        self.old_pw.delete(0, tk.END)
        self.new_pw.delete(0, tk.END)
        self.conf_pw.delete(0, tk.END)
        self._update_strength()

    def _build_security(self, parent) -> None:
        sec = _section(parent, "⏱️  Auto-bloqueo")
        ctk.CTkLabel(
            sec,
            text="Bloquear el gestor tras un periodo de inactividad.",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(2, 6))

        current = str(self.app.prefs.get("auto_lock_minutes", 0))
        labels = {"0": "Nunca", "1": "1 minuto", "5": "5 minutos", "15": "15 minutos", "30": "30 minutos"}
        self.lock_menu = ctk.CTkOptionMenu(
            sec,
            values=list(labels.values()),
            command=self._on_lock_change,
            width=200,
        )
        self.lock_menu.set(labels.get(current, labels["0"]))
        self.lock_menu.pack(anchor="w", padx=14, pady=(0, 12))

    def _on_lock_change(self, choice: str) -> None:
        mapping = {"Nunca": 0, "1 minuto": 1, "5 minutos": 5, "15 minutos": 15, "30 minutos": 30}
        self.app.prefs["auto_lock_minutes"] = mapping[choice]
        settings.save(self.app.prefs)
        self.app.flash_message("Auto-bloqueo actualizado")

    def _build_appearance(self, parent) -> None:
        sec = _section(parent, "🎨  Apariencia")
        current = self.app.prefs.get("theme", "light")
        names = {"light": "Claro", "dark": "Oscuro", "system": "Sistema"}
        self.theme_menu = ctk.CTkOptionMenu(
            sec,
            values=list(names.values()),
            command=self._on_theme_change,
            width=200,
        )
        self.theme_menu.set(names.get(current, names["light"]))
        self.theme_menu.pack(anchor="w", padx=14, pady=(2, 12))

    def _on_theme_change(self, choice: str) -> None:
        mapping = {"Claro": "light", "Oscuro": "dark", "Sistema": "system"}
        self.app.prefs["theme"] = mapping[choice]
        settings.save(self.app.prefs)
        self.app.apply_theme(mapping[choice])

    def _build_backup(self, parent) -> None:
        sec = _section(parent, "💾  Copia de seguridad")
        ctk.CTkLabel(
            sec,
            text="Exporta tu almacén cifrado para moverlo a otra laptop o respaldarlo.",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(2, 8))

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(0, 12))
        ctk.CTkButton(row, text="Exportar…", corner_radius=12, width=120, command=self._export).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(row, text="Importar…", corner_radius=12, width=120, command=self._import).pack(
            side="left"
        )

    def _export(self) -> None:
        dest = filedialog.asksaveasfilename(
            parent=self, title="Exportar almacén", defaultextension=".gcpw",
            filetypes=[("Gestor de Contraseñas", "*.gcpw"), ("Todos los archivos", "*.*")],
        )
        if not dest:
            return
        try:
            storage.export_vault(dest)
            messagebox.showinfo(APP_TITLE, f"Almacén exportado:\n{dest}", parent=self)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Error al exportar: {exc}", parent=self)

    def _import(self) -> None:
        src = filedialog.askopenfilename(
            parent=self, title="Importar almacén",
            filetypes=[("Gestor de Contraseñas", "*.gcpw"), ("Todos los archivos", "*.*")],
        )
        if not src:
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "Importar reemplazará TU almacén actual por el del archivo.\n"
            "Deberás desbloquear con la contraseña maestra de ese respaldo.\n\n¿Continuar?",
            parent=self,
        ):
            return
        try:
            storage.import_vault(src)
            messagebox.showinfo(
                APP_TITLE, "Almacén importado. Cierra la sesión y desbloquea con la contraseña del respaldo.",
                parent=self,
            )
            self.app.lock()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Error al importar: {exc}", parent=self)

    def _build_danger(self, parent) -> None:
        sec = _section(parent, "⚠️  Zona de peligro")
        ctk.CTkLabel(
            sec,
            text="Borrar todas las contraseñas y empezar de cero.",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(anchor="w", padx=14, pady=(2, 8))
        ctk.CTkButton(
            sec, text="Restablecer almacén", corner_radius=12, width=180,
            fg_color=DANGER, hover_color="#c95660", command=self._reset,
        ).pack(anchor="w", padx=14, pady=(0, 12))

    def _reset(self) -> None:
        if not messagebox.askyesno(
            APP_TITLE,
            "Esto BORRA todas tus contraseñas y la credencial de huella.\n\n¿Seguro?",
            parent=self,
        ):
            return
        storage.reset_vault()
        biometric.disable()
        faceauth.disable()
        self.destroy()
        self.app.lock()


class PasswordManagerApp(ctk.CTk):
    """Ventana principal de la aplicación."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("860x620")
        self.minsize(640, 480)
        self.master_password: str | None = None
        self.vault: storage.Vault | None = None

        self.prefs = settings.load()
        self._idle_ms = 0

        self.container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.toast_label: ctk.CTkLabel | None = None
        self._toast_job: str | None = None

        self.bind("<Key>", self._reset_idle)
        self.bind("<Button>", self._reset_idle)
        self.after(1000, self._idle_tick)

        # Precarga el modelo de reconocimiento facial en segundo plano
        # para evitar la demora inicial al usarlo por primera vez.
        if faceauth.is_supported() and faceauth.credential_available():
            threading.Thread(target=faceauth._get_app, daemon=True).start()

        self._show_login()

    # ---- pantallas ----
    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    def _show_login(self) -> None:
        self._clear()
        self.master_password = None
        self.vault = None
        login = LoginFrame(self.container, self)
        login.place(relx=0.5, rely=0.5, anchor="center")
        self.center()

    def _show_main(self) -> None:
        self._clear()
        self.toast_label = ctk.CTkLabel(
            self.container,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#3f8f5f",
            fg_color="transparent",
        )
        self.toast_label.pack(side="bottom", pady=6)
        self._toast_job = None

        self.main = MainFrame(self.container, self)
        self.main.pack(fill="both", expand=True)
        self.main.refresh()

    # ---- ciclo de vida del almacén ----
    def unlock(self, password: str, vault: storage.Vault | None = None) -> None:
        self.master_password = password
        self.vault = vault if vault is not None else storage.Vault([])
        self._show_main()
        self.flash_message("Almacén desbloqueado")

    def lock(self) -> None:
        self.master_password = None
        self.vault = None
        self._show_login()

    def apply_theme(self, mode: str | None = None) -> None:
        """Aplica el tema claro/oscuro/sistema."""
        if mode is None:
            mode = self.prefs.get("theme", "light")
        ctk.set_appearance_mode(mode)

    def _reset_idle(self, _event=None) -> None:
        self._idle_ms = 0

    def _idle_tick(self) -> None:
        timeout = self.prefs.get("auto_lock_minutes", 0)
        if self.master_password is not None and timeout > 0:
            self._idle_ms += 1000
            if self._idle_ms >= timeout * 60 * 1000:
                self.flash_message("Bloqueado por inactividad")
                self.lock()
        self.after(1000, self._idle_tick)

    def persist(self) -> None:
        if self.master_password is None or self.vault is None:
            return
        storage.save_vault(self.master_password, self.vault)

    def change_master_password(self, old: str, new: str) -> None:
        """Re-cifra el almacén con una nueva contraseña maestra."""
        if old != self.master_password:
            raise ValueError("La contraseña actual no coincide.")
        if self.vault is None:
            raise ValueError("No hay almacén cargado.")
        storage.save_vault(new, self.vault)
        self.master_password = new
        if biometric.credential_available():
            biometric.enable(new)
        if faceauth.credential_available():
            faceauth.rotate_password(new)

    # ---- utilidades ----
    def flash_message(self, text: str) -> None:
        if self.toast_label is None:
            return
        if self._toast_job:
            self.after_cancel(self._toast_job)
        label = self.toast_label
        label.configure(text=text)
        self._toast_job = self.after(2500, lambda: self._clear_toast(label))

    def _clear_toast(self, label: ctk.CTkLabel) -> None:
        if label.winfo_exists():
            label.configure(text="")

    def center(self) -> None:
        self.update_idletasks()
        w, h = 860, 620
        x = max((self.winfo_screenwidth() - w) // 2, 0)
        y = max((self.winfo_screenheight() - h) // 2, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")


def main() -> None:
    app = PasswordManagerApp()
    app.apply_theme()
    app.mainloop()


if __name__ == "__main__":
    main()
