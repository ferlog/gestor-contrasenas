"""Genera el icono de la aplicación (candado estilizado) en varios tamaños."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")


def _draw(size: int) -> Image.Image:
    bg = (224, 229, 236)  # neumorphic light
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = size * 0.10
    r = (size * 0.32, size * 0.40, size * 0.68, size * 0.80)
    # cuerpo del candado
    d.rounded_rectangle(r, radius=size * 0.06, fill=(111, 155, 242))
    # el arco
    arc_box = (size * 0.36, size * 0.16, size * 0.64, size * 0.46)
    d.arc(arc_box, start=180, end=360, fill=(111, 155, 242), width=int(size * 0.09))
    # ojo de la llave
    key_hole = (size * 0.46, size * 0.52, size * 0.54, size * 0.64)
    d.ellipse(key_hole, fill=bg)
    d.rounded_rectangle(
        (size * 0.49, size * 0.58, size * 0.51, size * 0.70),
        radius=size * 0.01,
        fill=bg,
    )
    return img


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    icon = Image.new("RGBA", (256, 256))
    icon.paste(_draw(256), (0, 0))
    icon.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon saved: {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
