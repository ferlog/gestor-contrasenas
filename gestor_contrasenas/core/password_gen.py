"""Generador de contraseñas aleatorias y seguras."""

from __future__ import annotations

import secrets
import string

_LOWER = string.ascii_lowercase
_UPPER = string.ascii_uppercase
_DIGITS = string.digits
_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/"


def generate_password(
    length: int = 16,
    use_upper: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
) -> str:
    """Genera una contraseña aleatoria con los conjuntos solicitados.

    Asegura al menos un carácter de cada conjunto activo.
    """
    if not 8 <= length <= 128:
        raise ValueError("La longitud debe estar entre 8 y 128.")

    pools: list[tuple[str, bool]] = [
        (_LOWER, True),
        (_UPPER, use_upper),
        (_DIGITS, use_digits),
        (_SYMBOLS, use_symbols),
    ]
    active = [chars for chars, enabled in pools if enabled]
    if not active:
        raise ValueError("Debes activar al menos un conjunto de caracteres.")

    # Garantizar al menos uno de cada conjunto activo.
    chars = [secrets.choice(pool) for pool in active]
    # Rellenar el resto de forma uniforme.
    all_chars = "".join(active)
    chars += [secrets.choice(all_chars) for _ in range(length - len(chars))]
    # Mezclar para no dejar el patrón predecible.
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def strength(password: str) -> tuple[int, str]:
    """Devuelve una puntuación 0-100 y una etiqueta de fortaleza.

    Puntuación basada en longitud y variedad de conjuntos de caracteres.
    """
    if not password:
        return 0, "Vacía"

    score = 0.0
    length = len(password)

    if length >= 8:
        score += 20
    if length >= 12:
        score += 15
    if length >= 16:
        score += 15
    if length >= 24:
        score += 10

    pools = [set(_LOWER), set(_UPPER), set(_DIGITS), set(_SYMBOLS)]
    matched = sum(1 for pool in pools if any(ch in password for ch in pool))
    score += matched * 10

    if matched == 1:
        score -= 15
    elif matched == 2:
        score -= 5

    score = max(0, min(100, round(score)))

    if score >= 80:
        label = "Muy fuerte"
    elif score >= 60:
        label = "Fuerte"
    elif score >= 40:
        label = "Media"
    elif score >= 20:
        label = "Débil"
    else:
        label = "Muy débil"
    return score, label
