# build.ps1
# Compila el gestor de contraseñas en un .exe de Windows (una sola carpeta, con icono).

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# 1) Generar el icono
python tools\make_icon.py

# 2) Instalar dependencias si falta alguna
pip install -r requirements.txt

# 3) Compilar con PyInstaller
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "GestorContrasenas" `
    --icon "assets\icon.ico" `
    --add-data "gestor_contrasenas\ui\neumorphic_theme.json;gestor_contrasenas\ui" `
    --collect-all customtkinter `
    --collect-all winrt `
    --collect-all insightface `
    --collect-all onnxruntime `
    --hidden-import cv2 `
    --hidden-import winrt.runtime `
    --hidden-import winrt.windows.security.credentials.ui `
    --hidden-import winrt.windows.foundation `
    main.py

Write-Host ""
Write-Host "Compilacion completa: dist\GestorContrasenas.exe"
