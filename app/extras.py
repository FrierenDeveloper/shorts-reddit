"""Elementos de retención: tarjeta estilo post, barra de progreso, encuesta final,
subtítulos palabra por palabra (karaoke) y efectos de sonido. Todo dibujado aquí, sin assets externos."""
import threading
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, SR = 1080, 1920, 24000
ACTIVE = (92, 255, 140)         # color de la palabra que se está diciendo
PORTADA_LUM = 120               # brillo medio al que se lleva la foto de fondo de la portada
                                # (las fotos del canal vienen a 40-80 y como fondo no se veían)
_FONTS = {}
_LOCK = threading.RLock()   # FreeType no es seguro entre hilos: el texto se dibuja de a uno


def font(size):
    import make_short as M
    if size not in _FONTS:
        _FONTS[size] = ImageFont.truetype(str(M.APP / "fonts" / "Poppins-Bold.ttf"), size)
    return _FONTS[size]


def ease(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3


def back(x):  # ease-out con rebote leve (pop)
    x = min(max(x, 0), 1); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _wrap(text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        if cur and f.getlength(cur + " " + w) > maxw:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    return lines


# ------------------------------------------------------------------ tarjeta estilo post
TEMAS = {  # fondo, texto, texto secundario, alpha
    "clara": ((255, 255, 255), (20, 20, 20), (90, 90, 90), 245),
    "oscura": ((22, 22, 26), (245, 245, 245), (170, 170, 170), 240),
    "vidrio": ((30, 20, 60), (240, 240, 255), (180, 170, 220), 200),
    "papel": ((246, 236, 214), (60, 40, 25), (120, 95, 70), 250),
}

def font_tpl(size):
    import make_short as M
    k = ("tpl", size, (M.TPL or {}).get("fuente"))
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(str(M.APP / "fonts" / (M.TPL or {}).get("fuente", "Poppins-Bold.ttf")), size)
    return _FONTS[k]

def card_sprite(sub, titulo, tema="clara"):
    fondo, ctxt, csec, alfa = TEMAS.get(tema, TEMAS["clara"])
    cw, pad = W - 120, 40
    ft, fh, fs = font_tpl(50), font(34), font(30)
    tl = _wrap(titulo, ft, cw - 2 * pad)[:3]
    ch = pad + 64 + 24 + len(tl) * 64 + 28 + 50 + pad
    img = Image.new("RGBA", (cw + 40, ch + 40))
    sh = Image.new("RGBA", img.size); ImageDraw.Draw(sh).rounded_rectangle((20, 28, cw + 20, ch + 20), 34, fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((20, 20, cw + 20, ch + 20), 34, fill=fondo + (alfa,))
    x0, y = 20 + pad, 20 + pad
    # cabecera: avatar + subreddit
    d.ellipse((x0, y, x0 + 64, y + 64), fill=(255, 69, 0))
    d.text((x0 + 32, y + 32), "r/", font=font(28), fill="white", anchor="mm")
    d.text((x0 + 84, y + 2), sub, font=fh, fill=ctxt)
    d.text((x0 + 84, y + 38), "historia de la comunidad", font=font(22), fill=csec)
    y += 64 + 24
    for line in tl:
        d.text((x0, y), line, font=ft, fill=ctxt); y += 64
    y += 28
    # pie: votar / comentar / compartir (iconos dibujados)
    gy = y + 25
    d.polygon([(x0, gy + 8), (x0 + 16, gy - 12), (x0 + 32, gy + 8)], fill=(255, 69, 0))
    d.text((x0 + 44, gy), "Votar", font=fs, fill=csec, anchor="lm")
    d.polygon([(x0 + 150, gy - 8), (x0 + 166, gy + 12), (x0 + 182, gy - 8)], fill=(113, 147, 255))
    bx = x0 + 250
    d.rounded_rectangle((bx, gy - 16, bx + 38, gy + 12), 8, outline=csec, width=4)
    d.polygon([(bx + 8, gy + 10), (bx + 8, gy + 22), (bx + 20, gy + 10)], fill=csec)
    d.text((bx + 52, gy), "Comentar", font=fs, fill=csec, anchor="lm")
    sx = bx + 250
    d.line((sx, gy + 12, sx, gy - 14), fill=csec, width=4)
    d.polygon([(sx - 12, gy - 4), (sx, gy - 18), (sx + 12, gy - 4)], fill=csec)
    d.text((sx + 26, gy), "Compartir", font=fs, fill=csec, anchor="lm")
    return img


# ------------------------------------------------------------------ portada (primer fotograma)
def _hex(color, default):
    """Acepta "#rrggbb" o una tupla RGB; devuelve una tupla RGB."""
    if isinstance(color, (list, tuple)) and len(color) == 3:
        return tuple(int(v) for v in color)
    if isinstance(color, str) and color.strip().startswith("#"):
        s = color.strip().lstrip("#")
        if len(s) == 6:
            try:
                return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
    return default


def trazo_recoloreado(path, color):
    """Quita el fondo blanco de un dibujo y pinta las líneas del color pedido."""
    gris = Image.open(path).convert("L")
    a = np.asarray(gris)
    ys, xs = np.where(a < 240)
    if len(xs):
        gris = gris.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    alfa = Image.fromarray((255 - np.asarray(gris)).astype("uint8"))
    rgb = Image.new("RGB", gris.size, tuple(color))
    return Image.merge("RGBA", (*rgb.split(), alfa))


def portada_sprite(titulo, fondo="#14121f", trazo="#ffffff", color_titulo=None, dibujo=None,
                   imagen_fondo=None, texto=None):
    """Portada del primer fotograma: fondo, dibujo (opcional) abajo y el rótulo encima.

    `texto` permite poner un rótulo DISTINTO del título: en los formatos educativos
    (salud mental y psicología) la portada debe llevar el NOMBRE de la patología o del sesgo,
    no el titular completo. Si no se pasa, se usa el título.

    Si `imagen_fondo` es una foto válida, la portada la usa como FONDO (recorte 9:16,
    desenfocada y teñida con `fondo`) en vez del degradado plano: una miniatura con contexto
    visual frena mucho más el scroll que un color liso. Sin foto, se comporta como antes."""
    import make_short as M
    T = M.TPL or {}
    bg = _hex(fondo, (20, 18, 31))
    tp = _hex(trazo, (255, 255, 255))
    img = Image.new("RGBA", (W, H), bg + (255,))
    foto = None
    if imagen_fondo:
        try:
            f = Image.open(imagen_fondo).convert("RGB")
            esc = max(W / f.width, H / f.height)                 # recorte "cover" a 9:16
            f = f.resize((max(1, int(f.width * esc)), max(1, int(f.height * esc))), Image.LANCZOS)
            x0, y0 = (f.width - W) // 2, (f.height - H) // 2
            f = f.crop((x0, y0, x0 + W, y0 + H))
            # NORMALIZAR el brillo antes de teñir: las fotos de este canal son muy oscuras
            # (luminancia 40-80) y como fondo de portada quedaban en una mancha negra que no
            # aportaba nada. Llevándolas a ~120 de media la escena SÍ se lee detrás del título.
            a = np.asarray(f, np.float32)
            lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
            if lum.mean() > 1:
                a = np.clip(a * (PORTADA_LUM / lum.mean()), 0, 255)
            foto = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
        except Exception:
            foto = None
    if foto is not None:
        img = Image.blend(foto, Image.new("RGB", (W, H), bg), 0.30).convert("RGBA")
        velo = Image.new("RGBA", (W, H), (0, 0, 0, 0))           # velo negro arriba y abajo
        dv = ImageDraw.Draw(velo)                                # para que el texto se lea
        for yy in range(0, H, 2):
            k = abs(yy / H - 0.5) * 2
            dv.rectangle((0, yy, W, yy + 2), fill=(0, 0, 0, int(90 * k ** 1.5)))
        img.alpha_composite(velo)
    else:
        d0 = ImageDraw.Draw(img)
        for yy in range(0, H, 4):                                # degradado vertical suave
            k = yy / H
            col = tuple(min(255, int(v + (255 - v) * 0.10 * k)) for v in bg)
            d0.rectangle((0, yy, W, yy + 4), fill=col + (255,))
    d = ImageDraw.Draw(img)
    lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    tcol = _hex(color_titulo, (26, 26, 26) if lum > 150 else (255, 255, 255))
    dib = None
    if dibujo and Path(dibujo).is_file():
        dib = trazo_recoloreado(dibujo, tp)
    elif dibujo:
        # Antes se omitía EN SILENCIO y la portada salía sin doodle sin avisar de nada.
        print(f"   ⚠ portada: el dibujo '{dibujo}' no existe; la portada saldrá sin doodle")
        dw = 700
        dib = dib.resize((dw, int(dib.height * dw / dib.width)), Image.LANCZOS)
    f = font_tpl(92)
    # El rótulo de la portada: `texto` si viene (nombre de la patología/sesgo en educativos),
    # si no el título del vídeo.
    lines = _wrap(str(texto or titulo or ""), f, W - 180)[:6]
    lh = int(f.size * 1.2)
    if dib is not None:
        dy = H - 80 - dib.height
        y0 = max((dy - 40) - len(lines) * lh, 560)
    else:
        dy = 0
        y0 = H // 2 - len(lines) * lh // 2
    for li, line in enumerate(lines):
        tw = int(f.getlength(line))
        d.text(((W - tw) / 2, y0 + li * lh), line, font=f, fill=tcol,
               stroke_width=8, stroke_fill=(0, 0, 0))
    acc = tuple(T.get("resalte", (255, 206, 84)))[:3]
    yy = y0 + len(lines) * lh + 26
    d.rectangle((W // 2 - 110, yy, W // 2 + 110, yy + 12), fill=acc + (255,))
    out = img if img.mode == "RGBA" else img.convert("RGBA")
    if dib is not None:
        out.alpha_composite(dib, ((W - dib.width) // 2, dy))
    return out


def portada_impacto(pregunta, imagen_fondo, subreddit=None, fondo="#14121f"):
    """Portada de historias de Reddit: foto NÍTIDA a pantalla completa + pregunta tendenciosa.

    Sin doodle y sin tarjeta (la tarjeta repetía el título). La foto va sin desenfocar, con
    un poco más de contraste y color, y un degradado oscuro abajo (y un velo suave arriba) para
    que la pregunta se lea sobre cualquier imagen. La pregunta es una frase completa que
    resume lo más importante del relato; la fuente se reduce hasta que cabe en 5 líneas.
    Devuelve None si la imagen no se puede abrir (el llamador cae a la portada clásica)."""
    import make_short as M
    T = M.TPL or {}
    try:
        f = Image.open(imagen_fondo).convert("RGB")
    except Exception:
        return None
    esc = max(W / f.width, H / f.height)                          # recorte "cover" 9:16
    f = f.resize((max(1, int(f.width * esc)), max(1, int(f.height * esc))), Image.LANCZOS)
    x0, y0 = (f.width - W) // 2, int((f.height - H) * 0.40)       # encuadre algo hacia arriba
    f = f.crop((x0, y0, x0 + W, y0 + H))
    a = np.asarray(f, np.float32)
    lum = float((0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).mean())
    if 1 < lum < 100:                                             # aclara solo las muy oscuras
        a = np.clip(a * min(100 / lum, 1.8), 0, 255)
    f = Image.fromarray(a.astype(np.uint8))
    f = ImageEnhance.Contrast(f).enhance(1.12)
    f = ImageEnhance.Color(f).enhance(1.15)
    img = f.convert("RGBA")
    # degradado: oscuro abajo (texto) y velo suave arriba (insignia del subreddit)
    ys = np.arange(H, dtype=np.float32) / H
    al = np.clip((ys - 0.34) / 0.50, 0, 1) ** 1.3 * 225
    al = np.maximum(al, np.clip((0.20 - ys) / 0.20, 0, 1) * 110)
    velo = np.zeros((H, W, 4), np.uint8)
    velo[..., 3] = al[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(velo, "RGBA"))
    d = ImageDraw.Draw(img)
    # pregunta: fuente grande que se reduce hasta caber en 5 líneas
    txt = str(pregunta or "").strip()
    for size in range(124, 55, -6):
        fnt = font_tpl(size)
        lines = _wrap(txt, fnt, W - 150)
        if len(lines) <= 3:
            break
    lines = lines[:4]
    lh = int(fnt.size * 1.18)
    base = H - 250                                                # deja libre la zona de la interfaz
    ytop = base - len(lines) * lh
    acc = tuple(T.get("resalte", (255, 206, 84)))[:3]
    d.rounded_rectangle((75, ytop - 46, 75 + 190, ytop - 32), 7, fill=acc + (255,))
    for li, line in enumerate(lines):
        tw = int(fnt.getlength(line))
        d.text(((W - tw) / 2, ytop + li * lh), line, font=fnt, fill=(255, 255, 255),
               stroke_width=8, stroke_fill=(0, 0, 0))
    # insignia del subreddit, arriba
    if subreddit:
        fs = font(36)
        label = str(subreddit)
        pw = int(fs.getlength(label)) + 130
        px, py = 60, 150
        d.rounded_rectangle((px, py, px + pw, py + 78), 39, fill=(0, 0, 0, 150))
        d.ellipse((px + 12, py + 11, px + 68, py + 67), fill=(255, 69, 0, 255))
        d.text((px + 40, py + 39), "r/", font=font(26), fill="white", anchor="mm")
        d.text((px + 84, py + 39), label.replace("r/", "", 1), font=fs, fill="white", anchor="lm")
    return img


# ------------------------------------------------------------------ encuesta
def pill_sprite(text, color):
    f = font(48)
    tw = int(f.getlength(text)); w, h = tw + 110, 108
    img = Image.new("RGBA", (w + 30, h + 30))
    sh = Image.new("RGBA", img.size); ImageDraw.Draw(sh).rounded_rectangle((15, 22, w + 15, h + 15), h // 2, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((15, 15, w + 15, h + 15), h // 2, fill=color + (255,), outline=(255, 255, 255, 255), width=5)
    d.ellipse((45, 15 + h / 2 - 14, 73, 15 + h / 2 + 14), fill=(255, 255, 255, 255))
    d.text((85, 15 + h / 2), text, font=f, fill="white", anchor="lm")
    return img


def _paste_scaled(img, spr, cx, cy, sc, alpha):
    if sc <= 0.02 or alpha <= 0.01: return
    w, h = max(1, int(spr.width * sc)), max(1, int(spr.height * sc))
    s = spr.resize((w, h), Image.BILINEAR)
    if alpha < 1:
        s.putalpha(s.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(s, (int(cx - w / 2), int(cy - h / 2)))


# ------------------------------------------------------------------ dibujo por fotograma
def apply(img, t, S, cache):
    """img: RGBA 1080×1920. S: estado del render (ver make_short.main)."""
    X = S.get("extras", {})
    total = S["total"]
    # 1) barra de progreso
    import make_short as M
    T = M.TPL or {}
    # 0) portada: el primer fotograma muestra el título + el dibujo (opcional) + la tarjeta de Reddit
    if S.get("portada") and t < 0.5 / max(M.FPS, 1):
        pcfg = S.get("portada_cfg") or {}
        if "portada" not in cache:
            with _LOCK:
                cache["portada"] = None
                if pcfg.get("modo") == "impacto" and pcfg.get("imagen_fondo"):
                    cache["portada"] = portada_impacto(pcfg.get("texto") or S.get("titulo", ""),
                                                       pcfg["imagen_fondo"], S.get("subreddit"),
                                                       pcfg.get("color_fondo", "#14121f"))
                    cache["portada_impacto"] = cache["portada"] is not None
            if cache["portada"] is None:
                with _LOCK:
                    cache["portada"] = portada_sprite(
                        S.get("titulo", ""),
                        fondo=pcfg.get("color_fondo", "#14121f"),
                        trazo=pcfg.get("color_trazo", "#ffffff"),
                        color_titulo=pcfg.get("color_titulo"),
                        dibujo=pcfg.get("dibujo"),
                        texto=pcfg.get("texto"),
                        # Fondo de la portada: la imagen que el guion pida, o si no la primera
                        # foto temática del vídeo (o el primer fotograma si el fondo es de vídeo).
                        # Antes era siempre un color plano.
                        imagen_fondo=pcfg.get("imagen_fondo") or
                                     (S.get("photos") or S.get("video_bg_frames") or [None])[0])
        img.paste(cache["portada"], (0, 0))
        if X.get("tarjeta", True) and not cache.get("portada_impacto"):
            if "card" not in cache:
                with _LOCK: cache["card"] = card_sprite(S["subreddit"], S["titulo"], T.get("tarjeta", "clara"))
            spr = cache["card"]
            img.alpha_composite(spr, ((W - spr.width) // 2, 210))
    if X.get("barra", True):
        bc = T.get("barra", {"pos": "arriba", "color": (255, 206, 84)})
        y0 = 0 if bc["pos"] == "arriba" else H - 12
        # La pista va al 23 % de blanco. ImageDraw sobre una imagen RGBA ESCRIBE el pixel
        # en vez de componerlo, y el .convert("RGB") del final tira el alpha: la pista
        # salia blanca OPACA (medido 252/255 en el render final) tapando el 30 % superior.
        # Solucion: capa aparte (cacheada, es constante) + alpha_composite.
        if "barra_pista" not in cache:
            capa = Image.new("RGBA", (W, 11), (0, 0, 0, 0))
            ImageDraw.Draw(capa).rectangle((0, 0, W, 11), fill=(255, 255, 255, 60))
            cache["barra_pista"] = capa
        img.alpha_composite(cache["barra_pista"], (0, y0))
        # El relleno es opaco (alpha 255): dibujarlo directo si es correcto.
        ImageDraw.Draw(img).rectangle((0, y0, int(W * min(t / total, 1)), y0 + 11),
                                      fill=tuple(bc["color"]) + (255,))
    # 2) tarjeta estilo post durante el gancho
    if X.get("tarjeta", True) and t < S["card_end"]:
        if "card" not in cache:
            with _LOCK: cache["card"] = card_sprite(S["subreddit"], S["titulo"], T.get("tarjeta", "clara"))
        spr = cache["card"]
        pin = ease(t / 0.4); pout = ease((t - (S["card_end"] - 0.35)) / 0.35) if t > S["card_end"] - 0.35 else 0
        al = pin * (1 - pout)
        if al > 0.01:
            s = spr.copy()
            if al < 1: s.putalpha(s.getchannel("A").point(lambda v: int(v * al)))
            y = int(210 - 40 * (1 - pin) - 30 * pout)
            img.alpha_composite(s, ((W - s.width) // 2, max(y, 12)))
    # 2b) etiqueta durante la opinión del creador
    for (oa, ob) in S.get("opinion_spans", []):
        if oa - 0.1 <= t < ob + 0.3:
            if "op" not in cache:
                with _LOCK: cache["op"] = pill_sprite("MI OPINIÓN", tuple(T.get("resalte", (255, 206, 84)))[:3])
            u = (t - oa + 0.1) / 0.35; v = (ob + 0.3 - t) / 0.3
            y_sub = int(H * T.get("y", 0.5))
            _paste_scaled(img, cache["op"], W / 2, y_sub - 190, 0.8 * back(u), min(1, max(u, 0) * 2, max(v, 0)))
    # 3) encuesta final
    ps = S.get("poll_start")
    if X.get("encuesta", True) and ps is not None and t >= ps:
        if "pills" not in cache:
            a, b = S.get("encuesta", ["TIENE RAZÓN", "SE PASÓ"])
            c1, c2 = T.get("encuesta_colores", ((39, 174, 96), (214, 48, 49)))
            with _LOCK: cache["pills"] = (pill_sprite(a, tuple(c1)), pill_sprite(b, tuple(c2)))
            cache["hint"] = None
        p1, p2 = cache["pills"]
        yb = int(H * T.get("y", 0.5)) + 230            # siempre bajo los subtítulos
        gap = 28                                        # botones uno al lado del otro
        esc = min(1.0, (W - 60) / (p1.width + p2.width + gap))
        izq = (W - (p1.width + p2.width) * esc - gap) / 2
        cxs = (izq + p1.width * esc / 2, izq + p1.width * esc + gap + p2.width * esc / 2)
        for k, (spr, cx) in enumerate(((p1, cxs[0]), (p2, cxs[1]))):
            u = (t - ps - 0.15 * k) / 0.45
            wob = 1 + 0.03 * np.sin((t - ps) * 5 + k) if u > 1 else 1
            _paste_scaled(img, spr, cx, yb, esc * back(u) * wob, min(1, max(u, 0) * 2))
    return img


def karaoke(img, t, sub, lines_layout):
    """Recolorea la palabra que se está diciendo. sub = [a, b, lines, times]."""
    a, b, lines, times = sub
    import make_short as M
    T = M.TPL or {}
    if not times or t < a + T.get("entrada", {}).get("dur", 0.28) or t > b - 0.2:
        return
    past = [i for i, tt in enumerate(times) if tt <= t]
    if not past:
        return
    idx = past[-1]
    x, y, w = lines_layout[idx]
    with _LOCK:
        _karaoke_draw(img, x, y, w, T, M)


def _karaoke_draw(img, x, y, w, T, M):
    d = ImageDraw.Draw(img)
    act = T.get("activa", ACTIVE)
    if T.get("caja"):
        bb = M.FONT.getbbox(w)
        d.rounded_rectangle((x + bb[0] - 12, y + bb[1] - 10, x + bb[2] + 12, y + bb[3] + 10), 16, fill=T["caja"]["activa"] + (255,))
        d.text((x, y), w, font=M.FONT, fill=act + (255,))
    else:
        brd, gro = T.get("borde", (20, 8, 20)), T.get("grosor", 7)
        d.text((x, y), w, font=M.FONT, fill=act + (255,), **(dict(stroke_width=gro, stroke_fill=brd + (255,)) if brd and gro else {}))


def layout(lines):
    """Posición (x, y, palabra) de cada palabra del bloque, igual que make_short.sub_sprite."""
    import make_short as M
    T = M.TPL or {}
    out, lh = [], T.get("lh", 104)
    y0 = int(H * T.get("y", 0.5) - len(lines) * lh / 2)
    for li, line in enumerate(lines):
        x = (W - M.width(line)) / 2; y = y0 + li * lh
        for w, hl in line:
            out.append((x, y, w)); x += M.FONT.getlength(w + " ")
    return out


# ------------------------------------------------------------------ efectos de sonido
def _whoosh(dur=0.45):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = np.random.default_rng(1).standard_normal(n)
    # ruido filtrado con barrido (suavizado móvil variable)
    out = np.zeros(n); acc = 0.0
    for i in range(n):
        k = 0.02 + 0.25 * (i / n)
        acc += k * (noise[i] - acc); out[i] = acc
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return (out * env / (np.abs(out).max() + 1e-9)).astype(np.float32)


def _pop(f=1320, dur=0.22):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.01 * t)
    return (s * np.exp(-t * 22) / 1.35).astype(np.float32)


def sfx_track(n, transitions, pops, poll_start):
    trk = np.zeros(n, np.float32)
    def put(snd, at, vol):
        i = int(max(at, 0) * SR); j = min(n, i + len(snd))
        if i < n: trk[i:j] += snd[: j - i] * vol
    w = _whoosh()
    for at in transitions: put(w, at - 0.25, 0.10)
    p = _pop()
    last = -9
    for at in pops:
        if at - last >= 1.8: put(p, at, 0.06); last = at
    if poll_start is not None:
        put(_pop(880), poll_start, 0.10); put(_pop(1175), poll_start + 0.15, 0.10)
    return trk


# ------------------------------------------------------------------ zoom rápido ("punch-in")
GIROS = ("pero", "y ahí", "entonces", "de repente", "hasta que", "lo peor", "resulta que", "y ahora")

def punch_times(cfg, seg_times, subs):
    """Momentos de giro: inicio de escenas que empiezan con conectores de giro + bloques con palabras resaltadas."""
    ts = []
    for s, (a, _) in zip(cfg["escenas"], seg_times):
        if s["texto"].replace("*", "").lower().lstrip("¿¡ ").startswith(GIROS):
            ts.append(a)
    ts += [sub[0] + 0.06 for sub in subs if any(hl for l in sub[2] for _, hl in l)]
    out, last = [], -9
    for t in sorted(ts):
        if t - last >= 3.0 and t > 1.0:
            out.append(t); last = t
    return out

def zoom_at(t, punches, fuerza=0.07):
    z = 0.0
    for p in punches:
        dt = t - p
        if 0 <= dt < 1.6:
            z = max(z, (dt / 0.12 if dt < 0.12 else np.exp(-(dt - 0.12) / 0.45)))
    return 1 + fuerza * z
