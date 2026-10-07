"""Demo: compone SOLO el primer fotograma (portada) con el dibujo "pensativo" recoloreado.
Usa el MISMO código que el render (extras.portada_sprite), así las muestras coinciden con el video.
Genera varias paletas (color de fondo + color del trazo) para revisar antes de decidir.

Uso:  python app\\portada_demo.py
Salida: salida\\portadas_demo\\portada_<n>_<nombre>.png
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))

import make_short as M          # noqa: E402

M.set_template("noche")         # misma plantilla que el video
import extras as X              # noqa: E402

TITULO = "Me dijo que mataba el ambiente en la cabaña: ¿me pasé?"
SUBREDDIT = "r/AmItheAsshole"
DIBUJO = APP / "assets" / "pensativo.jpg"
SALIDA = ROOT / "salida" / "portadas_demo"

# (nombre, color_fondo, color_trazo, color_titulo, tema_tarjeta)
PALETAS = [
    ("negro_blanco",   "#14121f", "#ffffff", "#ffffff", "vidrio"),
    ("azul_ambar",     "#14243d", "#ffd166", "#ffffff", "vidrio"),
    ("morado_menta",   "#2a1b3d", "#7cfc9b", "#ffffff", "vidrio"),
    ("carbon_rosa",    "#0e0e10", "#ff5c8a", "#ffffff", "vidrio"),
    ("crema_tinta",    "#f2ece0", "#2b2b2b", "#1a1a1a", "clara"),
    ("verde_teal",     "#e8f0e6", "#1f6f5c", "#14342c", "clara"),
    ("vino_oro",       "#3a0d0d", "#ffd166", "#ffffff", "vidrio"),
    ("noche_cian",     "#0d1b2a", "#00e5ff", "#ffffff", "vidrio"),
    ("marron_naranja", "#201a0e", "#ffb703", "#ffffff", "vidrio"),
    ("gris_plata",     "#1a1a1a", "#b8b8b8", "#ffffff", "vidrio"),
]


def portada(fondo, trazo, color_titulo, tema_tarjeta="vidrio"):
    img = X.portada_sprite(TITULO, fondo=fondo, trazo=trazo,
                           color_titulo=color_titulo, dibujo=str(DIBUJO))
    card = X.card_sprite(SUBREDDIT, TITULO, tema_tarjeta)
    img.alpha_composite(card, ((X.W - card.width) // 2, 210))
    return img.convert("RGB")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for n, (nombre, fondo, trazo, titulo, tarjeta) in enumerate(PALETAS, 1):
        out = SALIDA / f"portada_{n:02d}_{nombre}.png"
        portada(fondo, trazo, titulo, tarjeta).save(out)
        print("guardado", out)


if __name__ == "__main__":
    main()
