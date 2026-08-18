# Gestor de Contraseñas

Gestor de contraseñas de escritorio para **Windows 10/11** con interfaz neumórfica, cifrado local y varios métodos de desbloqueo biométrico.

## Características

- 🔐 **Contraseña maestra** con cifrado real (PBKDF2-SHA256 + AES/Fernet). Los datos se guardan cifrados en `~\.gestor-contrasenas\vault.dat`.
- 🔏 **Windows Hello** (huella y/o rostro) como método de desbloqueo adicional.
- 🙂 **Reconocimiento facial independiente** con la webcam (InsightFace buffalo_l) e **detección de vida** (parpadeo + movimiento de cabeza) para dificultar el engaño con fotos.
- ➕ Añadir credenciales (servicio, usuario, contraseña, notas).
- 🔍 Búsqueda en tiempo real por servicio, usuario o notas.
- 🎲 Generador de contraseñas configurable (longitud, mayúsculas, dígitos, símbolos).
- 📋 Copiar contraseñas al portapapeles sin mostrarlas.
- ⚙️ **Configuración**: cambiar contraseña maestra, auto-bloqueo por inactividad, tema claro/oscuro/sistema, exportar/importar respaldo, restablecer almacén.
- 💾 Copia de seguridad exportable para mover el almacén entre laptops.

## Requisitos

- Windows 10 u 11.
- Python 3.10+ (solo para desarrollar/compilar).
- Para biometría de Windows Hello: configúrala en *Configuración → Cuentas → Opciones de inicio de sesión*.
- Para el reconocimiento facial independiente: webcam. El modelo (~281 MB) se descarga solo la primera vez.

## Cómo ejecutar desde el código

```bash
pip install -r requirements.txt
python main.py
```

## Cómo compilar el ejecutable

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Genera `dist\GestorContrasenas.exe` (con icono). La primera ejecución extrae el ejecutable (~25 s) y descarga el modelo facial si aún no existe.

## Seguridad

- La contraseña maestra **no se puede recuperar**: si la olvidas, usa *Restablecer almacén* (perderás las contraseñas) o desbloquea por biometría si la activaste.
- Los datos biométricos (huella y rostro) se guardan cifrados con **DPAPI**, ligados a tu usuario de Windows.
- El reconocimiento con webcam es **algo menos seguro** que Windows Hello (webcam normal, más fácil de engañar), por eso incluye detección de vida.

## Estructura

```
gestor_contrasenas/
  core/        # crypto, storage, password_gen, clipboard, dpapi, biometric, faceauth, settings
  ui/          # app.py (interfaz neumórfica) + tema
main.py        # punto de entrada
build.ps1      # compilación con PyInstaller
tools/         # generador del icono
```