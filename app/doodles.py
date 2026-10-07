"""Doodles de portada dibujados con PIL: 12 arquetipos emocionales, sin assets externos.

Por qué se dibuja así
---------------------
`extras.trazo_recoloreado` calcula el alfa del trazo como `255 - gris`: el PNG TIENE que ser
BLANCO PURO OPACO con líneas NEGRAS. Con fondo transparente (RGBA) el alfa se saca del canal
alfa ya perdido y el dibujo entero acaba siendo una mancha opaca. Por eso aquí todo se dibuja
en modo RGB, fondo (255, 255, 255), trazo (0, 0, 0) de grosor 7.

`extras.portada_sprite` lo pega a 700 px de ancho en la parte baja de un lienzo 1080x1920 con
el título encima, así que las formas tienen que leerse EN PEQUEÑO. De ahí tres decisiones:
  - la cabeza es un óvalo grande y limpio, sin relleno, en la mitad izquierda;
  - el símbolo vive sólo en la franja derecha (x 524-780) y nunca toca la cabeza;
  - el cuerpo son dos curvas que nacen en el contorno de la cabeza y salen cortadas por el
    borde inferior, como en el `assets/pensativo.jpg` original.

Motor paramétrico, no doce dibujos copiados a mano:
  1) helpers geométricos: `_linea`, `_arco`, `_circulo` (dibujan y añaden puntas redondeadas);
  2) helpers de anatomía: `_cabeza`, `_ojo`, `_ceja`, `_boca`, `_brazo`, `_simbolo`;
  3) la tabla declarativa `_ARQUETIPOS` (datos, no funciones) y `_dibujar_arquetipo(cfg)`.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# ------------------------------------------------------------------ constantes
W, H = 800, 660                # lienzo: 800x660 en RGB opaco
TRAZO = 7                      # grosor de línea, como el dibujo original
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)

CARPETA = Path(__file__).resolve().parent / "assets" / "doodles"
DEFECTO = "pensativo"

# Geometría de la cara (todo el motor se apoya en estas cinco referencias).
CABEZA = (108, 82, 492, 474)            # óvalo: centro (300, 278), rx 192, ry 196
OJO_IZQ, OJO_DER, OJO_Y = 238, 362, 268
CEJA_Y = 220
BOCA = (300, 372)                       # centro de la boca
SYM_X0 = 524                            # nada del símbolo baja de aquí: la cabeza acaba en 492

# Cuándo usar cada arquetipo (mismo texto que `doodle_reglas.ARQUETIPOS`).
CATALOGO = {
    "pensativo":  "Dilema o duda sin resolver: hay que decidir y no está claro.",
    "dolido":     "Traición, engaño o desamor: alguien de confianza falló.",
    "indignado":  "Injusticia o falta de respeto: acusación, grosería, abuso.",
    "triste":     "Pérdida, enfermedad o duelo: algo grave y doloroso.",
    "aliviado":   "Resolución: remisión, disculpa aceptada, reconciliación.",
    "tenso":      "Confrontación o ultimátum: el conflicto está al límite.",
    "culpable":   "Remordimiento: quien narra reconoce su error o pide perdón.",
    "nostalgico": "Recuerdos y pasado: fotos, años atrás, tradiciones.",
    "ansioso":    "Ansiedad, miedo o angustia sostenida.",
    "confundido": "Contradicción o algo que no encaja ni se entiende.",
    "curioso":    "Descubrimiento o dato revelador: «resulta que...».",
    "analitico":  "Comparación, cifras, sesgos y toma de decisiones.",
}


# ------------------------------------------------------------------ 1) helpers geométricos
def _punta(d, x, y, r=TRAZO / 2.0, color=NEGRO):
    """Círculo relleno del mismo color: simula la punta redondeada del rotulador."""
    d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _linea(d, pts, ancho=TRAZO, color=NEGRO, puntas=True):
    """Polilínea a mano: `joint="curve"` para las uniones y una punta redonda en cada extremo."""
    pts = [(float(x), float(y)) for x, y in pts]
    if len(pts) > 1:
        d.line(pts, fill=color, width=ancho, joint="curve")
    if puntas:
        _punta(d, pts[0][0], pts[0][1], ancho / 2.0, color)
        _punta(d, pts[-1][0], pts[-1][1], ancho / 2.0, color)


def _arco(d, caja, a0, a1, ancho=TRAZO, color=NEGRO, puntas=True):
    """Arco de elipse (grados PIL: 0 = las 3 en punto, creciente en sentido horario)."""
    d.arc(caja, a0, a1, fill=color, width=ancho)
    if puntas:
        cx, cy = (caja[0] + caja[2]) / 2.0, (caja[1] + caja[3]) / 2.0
        rx, ry = (caja[2] - caja[0]) / 2.0, (caja[3] - caja[1]) / 2.0
        for a in (a0, a1):
            _punta(d, cx + rx * math.cos(math.radians(a)),
                   cy + ry * math.sin(math.radians(a)), ancho / 2.0, color)


def _circulo(d, cx, cy, rx, ry=None, relleno=False, ancho=TRAZO, color=NEGRO):
    """Elipse: contorno de grosor `ancho` o relleno macizo (pupilas, puntos, puños)."""
    ry = rx if ry is None else ry
    caja = (cx - rx, cy - ry, cx + rx, cy + ry)
    if relleno:
        d.ellipse(caja, fill=color)
    else:
        d.ellipse(caja, outline=color, width=ancho)


def _bezier(p0, p1, p2, n=24):
    """Cuadrática muestreada: el cuerpo y los brazos son curvas, no rectas."""
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _pts_arco(cx, cy, rx, ry, a0, a1, n=18):
    """Arco muestreado como polilínea (se puede girar; `d.arc` no)."""
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1))))
            for i in range(n)]


def _onda(cx, cy, ancho, amp, ciclos, n=17):
    """Línea ondulada: boca de duda o de nervios."""
    return [(cx - ancho / 2.0 + ancho * i / (n - 1),
             cy + amp * math.sin(2 * math.pi * ciclos * i / (n - 1))) for i in range(n)]


def _giro(pts, cx, cy, grados):
    """Rota una lista de puntos alrededor de (cx, cy)."""
    a = math.radians(grados)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)
            for x, y in pts]


def _punto(d, x, y, r):
    _circulo(d, x, y, r, relleno=True)


# ------------------------------------------------------------------ 2) helpers de anatomía
def _cabeza(d):
    """Óvalo grande a la izquierda-centro, SIN relleno."""
    _circulo(d, CABEZA[0] + 192, CABEZA[1] + 196, 192, 196)


def _cuerpo(d):
    """Hombros: dos curvas que nacen EN el contorno de la cabeza (x=162 y x=438, y=414)
    y salen cortadas por el borde inferior. Sin línea de cierre: el busto queda cortado
    por el marco, igual que en el dibujo original."""
    _linea(d, _bezier((162, 414), (118, 498), (88, 672), 26))
    _linea(d, _bezier((438, 414), (482, 498), (512, 672), 26))


def _brazo(d, tipo):
    """Brazos/manos: trazos simples, como la mano en la barbilla del original."""
    if tipo == "barbilla":
        # Mano ABIERTA apoyada en la barbilla: cuatro dedos, el dorso y el antebrazo saliendo
        # hacia abajo-derecha. Probado dibujando cinco versiones: el puño cerrado (elipse o
        # rectángulo redondeado) no se lee como mano por mucho que se retoque; los dedos sí.
        for x0, y0, x1, y1 in ((296, 545, 302, 477), (321, 555, 324, 476),
                               (346, 565, 346, 475), (371, 574, 368, 473)):
            _linea(d, [(x0, y0), (x1, y1)])                          # dedos
        _linea(d, _bezier((296, 545), (330, 578), (371, 574), 10))   # dorso
        _linea(d, _bezier((371, 574), (430, 630), (470, 672), 22))   # antebrazo
    elif tipo == "pecho":
        _linea(d, _bezier((108, 606), (280, 560), (420, 552), 22))   # brazo cruzado
        _circulo(d, 440, 546, 32, 24)                                # puño
        _linea(d, [(428, 530), (424, 562)])                          # nudillos


def _ojo(d, lado, estilo):
    """Ojos: óvalos con pupila rellena, o líneas/curvas según la expresión."""
    x = OJO_IZQ if lado < 0 else OJO_DER
    y = OJO_Y
    if estilo == "desigual":                     # confundido: cada ojo distinto
        estilo = "oval" if lado < 0 else "squint"
    if estilo == "punto":
        _punto(d, x, y, 10)
    elif estilo == "punto_abajo":                # mirada baja: párpado + pupila caída
        _linea(d, [(x - 19, y - 9), (x + 19, y - 9)], ancho=6)
        _punto(d, x, y + 7, 9)
    elif estilo == "oval":
        _circulo(d, x, y, 22, 18)
        _punto(d, x, y + 2, 8)
    elif estilo == "oval_bajo":
        _circulo(d, x, y, 22, 18)
        _punto(d, x, y + 6, 8)
    elif estilo == "oval_abierto":
        _circulo(d, x, y, 24, 21)
        _punto(d, x, y, 7)
    elif estilo == "cerrado_triste":             # arco hacia abajo: ojos apretados
        _arco(d, (x - 24, y - 12, x + 24, y + 16), 15, 165)
    elif estilo == "cerrado_feliz":              # arco hacia arriba: ojos sonriendo
        _arco(d, (x - 24, y - 16, x + 24, y + 12), 195, 345)
    elif estilo == "squint":                     # entrecerrados
        _linea(d, _pts_arco(x, y - 6, 22, 9, 20, 160))
    else:                                        # "linea" y cualquier nombre raro
        _linea(d, [(x - 20, y), (x + 20, y)])


# Cejas en coordenadas locales (u, v): u > 0 va HACIA el centro de la cara, v > 0 baja.
_CEJAS = {
    "recta":      [(-26, 0), (-8, -2), (10, -2), (26, 0)],
    "esceptica":  [(-26, -6), (-8, -5), (10, 1), (26, 6)],
    "suave":      [(-26, 2), (-9, -5), (9, -5), (26, 2)],
    "arriba":     [(-27, 6), (-10, -6), (10, -6), (27, 6)],
    "triste":     [(-26, 8), (-8, 2), (10, -3), (26, -8)],
    "preocupada": [(-27, 11), (-9, 1), (9, -6), (27, -12)],
    "enfadada":   [(-26, -8), (-8, -2), (10, 5), (26, 11)],
    "fruncida":   [(-25, -5), (0, -9), (25, -5)],
}


def _ceja(d, lado, estilo):
    """Cejas: son las que más cambian la emoción (arriba contento, abajo triste/enfadado)."""
    x = OJO_IZQ if lado < 0 else OJO_DER
    s = 1.0 if lado < 0 else -1.0                # espejo: u positivo siempre hacia el centro
    if estilo == "una_arriba":                   # confundido: una ceja subida
        estilo = "recta" if lado < 0 else "arriba"
    elif estilo == "pensativa":                  # pensativo: una recta y otra escéptica,
        estilo = "recta" if lado < 0 else "esceptica"   # como en el dibujo original
    base = _CEJAS.get(estilo, _CEJAS["recta"])
    _linea(d, [(x + s * u, CEJA_Y + v) for u, v in base])


def _boca(d, estilo):
    """Bocas: curva con el centro abajo = contento, centro arriba = triste/tenso,
    recta = tenso, abierta = sorpresa."""
    cx, cy = BOCA
    if estilo == "sonrisa":
        _arco(d, (cx - 44, cy - 30, cx + 44, cy + 30), 25, 155)
    elif estilo == "sonrisa_amplia":
        _arco(d, (cx - 50, cy - 36, cx + 50, cy + 36), 20, 160)
    elif estilo == "sonrisa_suave":
        _arco(d, (cx - 38, cy - 24, cx + 38, cy + 24), 30, 150)
    elif estilo == "triste":
        _arco(d, (cx - 44, cy - 30, cx + 44, cy + 30), 205, 335)
    elif estilo == "triste_pequena":
        _arco(d, (cx - 32, cy - 22, cx + 32, cy + 22), 210, 330)
    elif estilo == "apretada":                   # ceño: el centro sube, los extremos caen
        _linea(d, [(cx - 42, cy + 6), (cx, cy - 5), (cx + 42, cy + 6)])
    elif estilo == "recta":
        _linea(d, [(cx - 42, cy), (cx + 42, cy)])
    elif estilo == "recta_corta":
        _linea(d, [(cx - 30, cy + 2), (cx + 30, cy + 2)])
    elif estilo == "media_sonrisa":
        _linea(d, [(cx - 40, cy + 8), (cx, cy), (cx + 40, cy - 8)])
    elif estilo == "abierta":
        _circulo(d, cx, cy + 6, 24, 30)
    elif estilo == "abierta_pequena":
        _circulo(d, cx, cy + 4, 16, 20)
    elif estilo == "ondulada":
        _linea(d, _onda(cx, cy, 84, 9, 3))
    elif estilo == "ondulada_pequena":
        _linea(d, _onda(cx, cy, 60, 6, 2))
    else:
        _linea(d, [(cx - 42, cy), (cx + 42, cy)])


def _nariz(d):
    """Nariz mínima: el ganchito del dibujo original, entre ojos y boca."""
    _linea(d, _pts_arco(302, 314, 9, 11, 25, 155, 12))


def _cara(d, cfg):
    for lado in (-1, 1):
        _ojo(d, lado, cfg.get("ojos", "punto"))
    for lado in (-1, 1):
        _ceja(d, lado, cfg.get("cejas", "recta"))
    _nariz(d)
    _boca(d, cfg.get("boca", "recta"))


# ------------------------------------------------------------------ símbolos
def _pregunta_trazos(cx, y0, r):
    """Un «?» a mano: gancho por arriba, cola hacia el centro y punto.

    El gancho va de 190° a 355° (NO cierra más): probado en pantalla, cerrándolo hasta 35°
    el glifo se lee como un bastón de pastor. La cola mide 0,85r para que el punto caiga
    justo debajo. Devuelve (polilínea, centro del punto, radio del punto) para poder girarlo."""
    cy = y0 + r
    pts = _pts_arco(cx, cy, r, r, 190, 355, 26)
    cola = _bezier(pts[-1], (cx + 0.28 * r, y0 + 2.40 * r), (cx, y0 + 2.85 * r), 8)
    return pts + cola[1:], (cx, y0 + 3.50 * r), max(6.0, 0.30 * r)


def _sim_preguntas(d):
    """pensativo (el original): tres «?» en fila, a la altura de la cabeza."""
    for cx in (580, 662, 744):
        pts, punto, r = _pregunta_trazos(cx, 140, 30)
        _linea(d, pts)
        _punto(d, punto[0], punto[1], r)


def _sim_pregunta_girada(d):
    """confundido: un «?» grande y torcido, como la duda que no se resuelve.

    El giro tiene que ser POSITIVO (hacia la derecha): en negativo el gancho apunta a la
    izquierda y el glifo se lee como un bastón. Comprobado dibujando ±20° y ±28°."""
    r = 46.0
    # y0 = -1.9r deja el «?» (3,8r de alto contando el punto) centrado en el origen.
    pts, punto, rp = _pregunta_trazos(0.0, -1.9 * r, r)
    angi = 26.0
    cx, cy = 662.0, 290.0
    pts = [(x + cx, y + cy) for x, y in _giro(pts, 0, 0, angi)]
    punto = _giro([punto], 0, 0, angi)[0]
    _linea(d, pts)
    _punto(d, punto[0] + cx, punto[1] + cy, rp)


def _gota(d, cx, cy, r, incl=0.0, alto=None):
    """Gota de sudor: medio círculo abajo y dos rectas que suben a la punta."""
    alto = (1.15 * r) if alto is None else alto
    punta = (cx + incl, cy - r - alto)
    _arco(d, (cx - r, cy - r, cx + r, cy + r), 0, 180)
    _linea(d, [(cx - r, cy), punta])
    _linea(d, [(cx + r, cy), punta])


def _sim_gota(d):
    """tenso: una gota grande y torcida."""
    _gota(d, 650, 306, 66, incl=-24, alto=38)


def _sim_gotas(d):
    """culpable: dos gotas pequeñas (la mirada baja la pone la cara)."""
    _gota(d, 604, 252, 42, incl=-14, alto=32)
    _gota(d, 724, 330, 30, incl=14, alto=28)


def _sim_exclamaciones(d):
    """indignado: dos «!» inclinados hacia fuera."""
    for x, y, alto, incl in ((580, 150, 140, -16), (702, 168, 150, 18)):
        _linea(d, [(x, y), (x + incl, y + alto)])
        _punto(d, x + incl, y + alto + 34, 9)


def _sim_corazon_partido(d):
    """dolido: corazón con dos lóbulos y una grieta en zigzag."""
    _arco(d, (560, 210, 660, 310), 180, 360)     # lóbulo izquierdo
    _arco(d, (660, 210, 760, 310), 180, 360)     # lóbulo derecho
    _linea(d, [(560, 260), (660, 412)])          # costado izquierdo a la punta
    _linea(d, [(760, 260), (660, 412)])          # costado derecho a la punta
    # La grieta se queda DENTRO del corazón: acabando en y=404 tocaba el costado izquierdo.
    _linea(d, [(660, 250), (646, 288), (668, 318), (652, 350), (664, 386)])


def _sim_lagrima(d):
    """triste: una lágrima grande y limpia."""
    _arco(d, (585, 240, 725, 380), 0, 180)
    _linea(d, [(585, 310), (655, 200)])
    _linea(d, [(725, 310), (655, 200)])


def _sim_sol(d):
    """aliviado: sol con ocho rayos (girados 22,5° para que no queden en cruz)."""
    cx, cy, r = 655, 290, 58
    _circulo(d, cx, cy, r)
    for k in range(8):
        a = math.radians(22.5 + 45.0 * k)
        _linea(d, [(cx + 84 * math.cos(a), cy + 84 * math.sin(a)),
                   (cx + 112 * math.cos(a), cy + 112 * math.sin(a))])


def _sim_remolino(d):
    """ansioso: espiral de 2,7 vueltas que se cierra hacia dentro."""
    cx, cy, n = 658, 300, 96
    pts = []
    for i in range(n + 1):
        t = i / n
        a = math.radians(t * 2.7 * 360.0 - 90.0)
        r = 8 + t * 104
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    _linea(d, pts)


def _sim_lupa(d):
    """curioso: lente redonda y mango a 45°."""
    cx, cy, r = 636, 262, 74
    _circulo(d, cx, cy, r)
    a = math.radians(45)
    _linea(d, [(cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r + 46, cy + r + 46)])


def _sim_balanza(d):
    """analitico: balanza nivelada (dos platos colgando del brazo)."""
    cx = 648
    _linea(d, [(cx, 172), (cx, 390)])            # poste
    _punto(d, cx, 168, 10)                       # fulcro
    _linea(d, [(554, 206), (742, 206)])          # brazo nivelado
    _linea(d, [(608, 390), (688, 390)])          # base
    for x in (554, 742):
        _linea(d, [(x, 206), (x, 252)])          # tirante
        _arco(d, (x - 30, 252, x + 30, 302), 0, 180)   # plato


def _sim_marco_nube(d):
    """nostalgico: marco de foto con paisaje dentro y una nube encima."""
    _linea(d, [(562, 186), (758, 186), (758, 400), (562, 400), (562, 186)])  # marco
    _linea(d, [(578, 370), (642, 286), (694, 352), (722, 316), (744, 370)])  # montañas
    _circulo(d, 616, 236, 15)                                                # sol dentro
    # Cúpulas parecidas y pegadas a la base: con radios 26/34/26 y mucho desnivel la nube
    # salía aplastada o con forma de seta.
    for bx, by, br in ((630, 150, 24), (674, 144, 28), (718, 150, 24)):
        _arco(d, (bx - br, by - br, bx + br, by + br), 180, 360)
    _linea(d, [(606, 150), (742, 150)])


_SIMBOLOS = {
    "preguntas": _sim_preguntas,
    "pregunta_girada": _sim_pregunta_girada,
    "corazon_partido": _sim_corazon_partido,
    "exclamaciones": _sim_exclamaciones,
    "lagrima": _sim_lagrima,
    "sol": _sim_sol,
    "gota": _sim_gota,
    "gotas": _sim_gotas,
    "remolino": _sim_remolino,
    "lupa": _sim_lupa,
    "balanza": _sim_balanza,
    "marco_nube": _sim_marco_nube,
}


def _simbolo(d, nombre):
    """Símbolos a la derecha, en el hueco libre: siempre a mano, con líneas y arcos."""
    _SIMBOLOS.get(nombre, _sim_preguntas)(d)


# ------------------------------------------------------------------ 3) tabla declarativa
# Cada arquetipo es DATO: qué ojos, qué cejas, qué boca, qué brazo y qué símbolo.
_ARQUETIPOS = {
    "pensativo": dict(ojos="punto", cejas="pensativa", boca="ondulada",
                      brazo="barbilla", simbolo="preguntas"),
    "dolido": dict(ojos="cerrado_triste", cejas="triste", boca="triste",
                   brazo="pecho", simbolo="corazon_partido"),
    "indignado": dict(ojos="oval", cejas="enfadada", boca="apretada",
                      brazo="pecho", simbolo="exclamaciones"),
    "triste": dict(ojos="oval_bajo", cejas="triste", boca="triste",
                   brazo="ninguno", simbolo="lagrima"),
    "aliviado": dict(ojos="cerrado_feliz", cejas="arriba", boca="sonrisa",
                     brazo="ninguno", simbolo="sol"),
    "tenso": dict(ojos="squint", cejas="fruncida", boca="recta",
                  brazo="pecho", simbolo="gota"),
    "culpable": dict(ojos="punto_abajo", cejas="preocupada", boca="triste_pequena",
                     brazo="pecho", simbolo="gotas"),
    "nostalgico": dict(ojos="cerrado_feliz", cejas="suave", boca="sonrisa_suave",
                       brazo="ninguno", simbolo="marco_nube"),
    "ansioso": dict(ojos="oval_abierto", cejas="preocupada", boca="ondulada",
                    brazo="barbilla", simbolo="remolino"),
    "confundido": dict(ojos="desigual", cejas="una_arriba", boca="ondulada_pequena",
                       brazo="ninguno", simbolo="pregunta_girada"),
    "curioso": dict(ojos="oval_abierto", cejas="arriba", boca="abierta_pequena",
                    brazo="ninguno", simbolo="lupa"),
    "analitico": dict(ojos="oval", cejas="recta", boca="media_sonrisa",
                      brazo="pecho", simbolo="balanza"),
}


def _dibujar_arquetipo(cfg):
    """Interpreta una fila de `_ARQUETIPOS` y devuelve el lienzo RGB (blanco opaco)."""
    img = Image.new("RGB", (W, H), BLANCO)
    d = ImageDraw.Draw(img)
    _cuerpo(d)                                   # hombros
    _brazo(d, cfg.get("brazo", "ninguno"))
    _cabeza(d)
    _cara(d, cfg)                                # ojos, cejas, nariz y boca
    _simbolo(d, cfg.get("simbolo", "preguntas"))
    return img


# ------------------------------------------------------------------ API
def dibujar(nombre, ruta=None, lado=800):
    """Dibuja un arquetipo y lo guarda en PNG (RGB, fondo blanco puro).

    Si `nombre` no existe cae a `pensativo` SIN lanzar. `ruta` es el archivo de destino
    (por defecto `assets/doodles/<nombre>.png`). `lado` es el ancho en píxeles; con 800 no
    se redimensiona, que es como debe guardarse para que el blanco quede blanco puro."""
    clave = nombre if isinstance(nombre, str) and nombre in _ARQUETIPOS else DEFECTO
    img = _dibujar_arquetipo(_ARQUETIPOS[clave])
    lado = int(lado)
    if lado != W:
        img = img.resize((lado, max(1, round(H * lado / W))), Image.LANCZOS)
    destino = Path(ruta) if ruta else (CARPETA / f"{clave}.png")
    if destino.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        destino = destino.with_suffix(".png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def dibujar_todos(carpeta=None):
    """Genera los 12 arquetipos y devuelve {nombre: Path}."""
    destino = Path(carpeta) if carpeta else CARPETA
    destino.mkdir(parents=True, exist_ok=True)
    return {nombre: dibujar(nombre, destino / f"{nombre}.png") for nombre in _ARQUETIPOS}


if __name__ == "__main__":
    base = Path(tempfile.gettempdir()) / "doodles_test"
    rutas = dibujar_todos(base)
    print(f"{len(rutas)} doodles generados en {base}")
    for nombre, ruta in rutas.items():
        print(f"  {nombre:11s} -> {ruta}")
