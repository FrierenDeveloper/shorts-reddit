"""Plantillas visuales. Cada video usa una (elegida en el JSON con "plantilla", o al azar).
Cambian tipografía, colores, ritmo de subtítulos, posición, tarjeta, barra, paleta y estilo musical."""

PLANTILLAS = {
    # 1) La original: cálida y limpia
    "clasica": dict(
        fuente="Poppins-Bold.ttf", tam=76, mayus=False, lh=104, y=0.50, maxw=900, max_palabras=0,
        texto=(255, 255, 255), resalte=(255, 206, 84), activa=(92, 255, 140), borde=(20, 8, 20), grosor=7,
        caja=None, entrada=dict(dur=0.28, escala=0.86, sube=34),
        tarjeta="clara", barra=dict(pos="arriba", color=(255, 206, 84)),
        pal={"calido": [(110, 20, 45), (190, 80, 30), (55, 20, 70)],
             "frio": [(40, 25, 80), (30, 60, 110), (15, 15, 45)],
             "neutro": [(80, 30, 70), (120, 60, 70), (35, 20, 60)]},
        musica="pad", velocidad=None, encuesta_colores=((39, 174, 96), (214, 48, 49))),

    # 2) Impacto: condensada, mayúsculas, bloques cortos y rápidos
    "impacto": dict(
        fuente="Anton.ttf", tam=104, mayus=True, lh=118, y=0.47, maxw=880, max_palabras=3,
        texto=(255, 255, 255), resalte=(255, 72, 48), activa=(255, 230, 0), borde=(0, 0, 0), grosor=10,
        caja=None, entrada=dict(dur=0.16, escala=1.25, sube=0),
        tarjeta="oscura", barra=dict(pos="abajo", color=(255, 72, 48)),
        pal={"calido": [(120, 30, 10), (200, 90, 20), (60, 15, 15)],
             "frio": [(20, 20, 30), (60, 20, 30), (10, 10, 15)],
             "neutro": [(70, 30, 25), (110, 50, 30), (30, 15, 15)]},
        musica="lofi", velocidad="+10%", encuesta_colores=((0, 170, 90), (230, 30, 30))),

    # 3) Noche: neón, subtítulos más abajo
    "noche": dict(
        fuente="Montserrat-Black.ttf", tam=70, mayus=False, lh=96, y=0.60, maxw=880, max_palabras=0,
        texto=(240, 240, 255), resalte=(0, 229, 255), activa=(255, 64, 200), borde=(10, 5, 30), grosor=7,
        caja=None, entrada=dict(dur=0.35, escala=1.0, sube=60),
        tarjeta="vidrio", barra=dict(pos="arriba", color=(0, 229, 255)),
        pal={"calido": [(90, 20, 110), (170, 40, 130), (30, 10, 70)],
             "frio": [(10, 40, 90), (0, 90, 120), (5, 10, 40)],
             "neutro": [(50, 20, 90), (70, 50, 130), (15, 10, 45)]},
        musica="synth", velocidad=None, encuesta_colores=((0, 180, 200), (220, 0, 140))),

    # 4) Diario: serif, tonos sepia, calmado
    "diario": dict(
        fuente="Lora-Bold.ttf", tam=74, mayus=False, lh=100, y=0.52, maxw=880, max_palabras=0,
        texto=(255, 246, 228), resalte=(255, 190, 90), activa=(255, 130, 110), borde=(40, 22, 10), grosor=6,
        caja=None, entrada=dict(dur=0.45, escala=0.97, sube=14),
        tarjeta="papel", barra=dict(pos="abajo", color=(255, 190, 90)),
        pal={"calido": [(120, 70, 35), (170, 110, 60), (60, 35, 20)],
             "frio": [(60, 55, 60), (90, 80, 80), (30, 28, 32)],
             "neutro": [(95, 70, 50), (130, 100, 75), (45, 35, 30)]},
        musica="piano", velocidad="+0%", encuesta_colores=((110, 150, 60), (180, 60, 45))),

    # 5) Pop: texto dentro de cajas, colores vivos
    "pop": dict(
        fuente="ArchivoBlack.ttf", tam=66, mayus=False, lh=100, y=0.50, maxw=860, max_palabras=5,
        texto=(20, 20, 20), resalte=(230, 30, 110), activa=(255, 255, 255), borde=None, grosor=0,
        caja=dict(color=(255, 255, 255), activa=(230, 30, 110)), entrada=dict(dur=0.22, escala=0.6, sube=0),
        tarjeta="clara", barra=dict(pos="arriba", color=(255, 90, 140)),
        pal={"calido": [(230, 90, 120), (255, 150, 80), (150, 50, 140)],
             "frio": [(80, 90, 200), (60, 160, 200), (60, 40, 120)],
             "neutro": [(170, 90, 170), (220, 130, 130), (90, 60, 130)]},
        musica="musicbox", velocidad="+8%", encuesta_colores=((20, 180, 120), (240, 60, 90))),

    # 6) Tétrica: para historias de salud mental — subtítulos abajo, tonos fríos/oscuros, música inquietante
    "tetrica": dict(
        fuente="Montserrat-Black.ttf", tam=68, mayus=False, lh=94, y=0.72, maxw=860, max_palabras=0,
        texto=(225, 225, 235), resalte=(150, 60, 210), activa=(80, 220, 190), borde=(5, 5, 10), grosor=7,
        caja=None, entrada=dict(dur=0.4, escala=0.95, sube=20),
        tarjeta="oscura", barra=dict(pos="arriba", color=(120, 60, 170)),
        # Paleta aclarada ~1.6x. Los valores originales dejaban la luminancia media del render
        # en 31-51 sobre 255 (el fondo se perdia y el Ken Burns no se veia); a 2x las fotos
        # claras quedaban lavadas en lavanda pastel y se perdia el tono dramático de la plantilla.
        pal={"calido": [(56, 24, 72), (96, 32, 64), (20, 17, 38)],
             "frio": [(18, 27, 58), (35, 60, 80), (11, 11, 27)],
             "neutro": [(36, 27, 58), (64, 46, 76), (15, 12, 30)]},
        musica="tetrico", velocidad=None, encuesta_colores=((90, 70, 140), (140, 40, 60))),
}


def elegir(cfg, nombre_video):
    """Plantilla del JSON, o una "al azar" estable por video (el mismo video siempre usa la misma)."""
    p = cfg.get("plantilla", "aleatoria")
    if p in PLANTILLAS:
        return p
    import zlib
    claves = sorted(PLANTILLAS)
    return claves[zlib.crc32(nombre_video.encode()) % len(claves)]
