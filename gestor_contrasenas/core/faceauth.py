"""Reconocimiento facial independiente (webcam) con InsightFace buffalo_l.

Incluye detección de vida (liveness) para dificultar el engaño con fotos:
1. Detecta parpadeos (Eye Aspect Ratio) durante un vídeo corto.
2. Detecta movimiento de la cabeza (cambio de posición/escala del rostro).
3. Compara el rostro con el embedding guardado (similitud de coseno).

La credencial guarda el embedding facial + la contraseña maestra, ambos
protegidos con DPAPI, de modo que el rostro permite desbloquear aunque se
olvide la contraseña. Es un método adicional y algo menos seguro que
Windows Hello (webcam normal, más fácil de engañar).
"""

from __future__ import annotations

import json
import os
import threading
import time

import numpy as np

from . import dpapi
from .storage import app_dir_path

_CRED_FILE = os.path.join(app_dir_path(), "faceauth.dat")

# Umbrales (ajustables).
SIM_THRESHOLD = 0.40  # similitud de coseno mínima para considerar mismo rostro
EAR_BLINK = 0.22  # por debajo de este EAR se considera un parpadeo
MOVE_PX = 14  # desplazamiento mínimo del centro del rostro para contar "movimiento"
CAPTURE_SECONDS = 4
MIN_FRAMES = 5
MIN_BLINKS = 1
MIN_MOVES = 1
_DET_SIZE = (320, 320)
_SAMPLE_INTERVAL = 0.2  # segundos entre inferencias
_MAX_INFERENCES = 16

# Detección de disponibilidad de librerías.
try:
    import cv2

    _CV2_OK = True
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    _CV2_OK = False

try:
    from insightface.app import FaceAnalysis

    _INSIGHTFACE_OK = True
except Exception:  # noqa: BLE001
    FaceAnalysis = None  # type: ignore[assignment,misc]
    _INSIGHTFACE_OK = False

_lock = threading.Lock()
_app = None


def is_supported() -> bool:
    """Indica si las librerías de visión están disponibles."""
    return _CV2_OK and _INSIGHTFACE_OK


def _get_app():
    """Devuelve la instancia única de FaceAnalysis (carga los modelos)."""
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=0, det_size=_DET_SIZE)
                _app = app
    return _app


def device_available() -> bool:
    """Indica si se puede abrir la webcam."""
    if not _CV2_OK:
        return False
    try:
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened()
        cap.release()
        return ok
    except Exception:  # noqa: BLE001
        return False


# ---- Eye Aspect Ratio sobre landmarks 68 ----
_LEFT_EYE = list(range(36, 42))
_RIGHT_EYE = list(range(42, 48))


def _ear(landmarks2d: np.ndarray) -> float:
    """Calcula el Eye Aspect Ratio promedio a partir de landmarks 68 2D."""
    def _one(eye: list[int]) -> float:
        p = landmarks2d[eye]
        v = np.array(p)
        a = np.linalg.norm(v[1] - v[5])
        b = np.linalg.norm(v[2] - v[4])
        c = np.linalg.norm(v[0] - v[3])
        return (a + b) / (2.0 * c) if c > 0 else 1.0

    return (_one(_LEFT_EYE) + _one(_RIGHT_EYE)) / 2.0


def _landmarks2d(face) -> np.ndarray | None:
    """Extrae landmarks 68 2D desde el objeto de InsightFace."""
    if getattr(face, "landmark_3d_68", None) is not None:
        pts = np.array(face.landmark_3d_68, dtype=np.float32)
        if pts.shape[0] >= 48:
            # Se usan las coordenadas x,y (3D posee también z).
            return pts[:, :2]
    if getattr(face, "landmark_2d_106", None) is not None:
        # Los 106 incluyen los 68 estándar al inicio en InsightFace.
        pts = np.array(face.landmark_2d_106, dtype=np.float32)
        if pts.shape[0] >= 68:
            return pts[:68]
    return None


def _capture() -> dict | None:
    """Captura un vídeo corto y extrae parpadeos, movimiento y embeddings.

    Devuelve None si no se detecta rostro o falla la cámara.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        return None

    embeddings: list[np.ndarray] = []
    blinks = 0
    moves = 0
    prev_center: tuple[float, float] | None = None
    prev_size: float | None = None
    inferences = 0
    start = time.time()

    try:
        while time.time() - start < CAPTURE_SECONDS and inferences < _MAX_INFERENCES:
            ok, frame = cap.read()
            if not ok:
                break
            time.sleep(_SAMPLE_INTERVAL)

            faces = _get_app().get(frame)
            inferences += 1
            if not faces:
                prev_center, prev_size = None, None
                continue

            face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
            embeddings.append(np.asarray(face.embedding, dtype=np.float32))
            landmarks = _landmarks2d(face)
            if landmarks is not None:
                if _ear(landmarks) < EAR_BLINK:
                    blinks += 1

            cx = (face.bbox[0] + face.bbox[2]) / 2.0
            cy = (face.bbox[1] + face.bbox[3]) / 2.0
            size = face.bbox[2] - face.bbox[0]
            if prev_center is not None:
                dist = ((cx - prev_center[0]) ** 2 + (cy - prev_center[1]) ** 2) ** 0.5
                size_delta = abs(size - prev_size) if prev_size else 0
                if dist > MOVE_PX or size_delta > size * 0.05:
                    moves += 1
            prev_center, prev_size = (cx, cy), size

        if len(embeddings) < MIN_FRAMES:
            return None

        avg = np.mean(np.stack(embeddings), axis=0)
        norm = avg / (np.linalg.norm(avg) + 1e-9)
        return {"embedding": norm, "blinks": blinks, "moves": moves}
    finally:
        cap.release()


# ---- persistencia ----
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
    """Indica si ya hay un rostro guardado."""
    return _read_blob() is not None


def disable() -> None:
    """Elimina la credencial facial guardada."""
    try:
        os.remove(_CRED_FILE)
    except FileNotFoundError:
        pass


def rotate_password(new_password: str) -> None:
    """Re-cifra el embedding guardado con una nueva contraseña maestra."""
    saved = _load()
    if saved is None:
        return
    _save(np.asarray(saved["e"], dtype=np.float32), new_password)


def _save(embedding: np.ndarray, master_password: str) -> None:
    payload = json.dumps(
        {"e": embedding.astype(float).tolist(), "p": master_password}
    ).encode("utf-8")
    _write_blob(dpapi.protect(payload))


def _load() -> dict | None:
    blob = _read_blob()
    if blob is None:
        return None
    try:
        payload = dpapi.unprotect(blob)
        return json.loads(payload.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def enroll(master_password: str) -> str | None:
    """Captura el rostro y lo guarda. Devuelve un mensaje de error o None si OK.

    Requiere la contraseña maestra actual (para poder desbloquear luego).
    """
    result = _capture()
    if result is None:
        return "No se pudo capturar un rostro. Mejora la iluminación y prueba de nuevo."
    if result["blinks"] < MIN_BLINKS:
        return "No se detectaron parpadeos. Parpadea durante la captura."
    _save(result["embedding"], master_password)
    return None


def verify() -> tuple[bool, str | None]:
    """Captura el rostro, verifica liveness e identidad.

    Devuelve (ok, master_password). `master_password` sólo es no-None si ok.
    """
    result = _capture()
    if result is None:
        return False, "No se detectó tu rostro. Mejora la iluminación y prueba de nuevo."
    if result["blinks"] < MIN_BLINKS:
        return False, "Parpadea durante la captura para confirmar que eres una persona real."
    if result["moves"] < MIN_MOVES:
        return False, "Mueve ligeramente la cabeza de lado a lado durante la captura."

    saved = _load()
    if saved is None:
        return False, "No hay un rostro guardado. Guárdalo antes en Configuración."

    ref = np.asarray(saved["e"], dtype=np.float32)
    ref = ref / (np.linalg.norm(ref) + 1e-9)
    sim = float(np.dot(result["embedding"], ref))
    if sim < SIM_THRESHOLD:
        return False, "El rostro no coincide con el guardado."
    return True, saved.get("p")