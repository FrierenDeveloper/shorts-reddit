# -*- coding: utf-8 -*-
"""
Fuentes de imágenes y vídeo ADICIONALES para el motor de shorts.

Este módulo NO modifica make_short.py: se limita a IMPLEMENTAR SU CONTRATO.

Contrato que respeta cada buscador
----------------------------------
    fn(q, key=None, relajado=False) -> list[dict]

Cada dict devuelto tiene EXACTAMENTE estas claves (y opcionalmente `tags`):

    url, thumb, w, h, id, title, artist, license, page, fuente

Reglas aplicadas en todas las fuentes:
  * Sólo licencias libres, también para uso comercial: CC0, Dominio Público,
    CC BY, CC BY-SA, Licencia Pexels, Licencia Pixabay.
  * Resolución mínima MIN_W x MIN_H (mismo valor que make_short.py:299).
  * `id` único con prefijo propio de la fuente.
  * timeout=30, User-Agent propio (UA, igual que make_short.py:44) y try/except
    en CADA fuente: una fuente caída devuelve [] y no tumba nada.
  * Si falta la clave de API, devuelve [] SIN fallar.

Claves de API
-------------
Se leen EXACTAMENTE igual que make_short.py:_claves() (config/claves.json y
setdefault desde variables de entorno):

    pexels   <- PEXELS_API_KEY   (compartida con src_pexels / src_pexels_video)
    pixabay  <- PIXABAY_API_KEY  (compartida con src_pixabay / src_pixabay_video)
    flickr   <- FLICKR_API_KEY   (sólo la usa src_flickr_cc)

Integración con el motor
------------------------
    import fuentes_extra
    FUENTES = fuentes_extra.fuentes_todas(FUENTES)          # añade las nuevas
    FUENTES = fuentes_extra.fuentes_todas(FUENTES, ["flickr_cc", "pexels_video"])

`fuentes_todas` nunca sobrescribe una fuente que ya exista en el dict base.

Estado de verificación (comprobado con red real desde este equipo)
------------------------------------------------------------------
  flickr_cc            ... endpoint confirmado real (responde "Invalid API Key"
                           sin clave); la ruta autenticada NO se pudo verificar
                           porque no hay clave de Flickr en esta máquina.
  stocksnap            ... SIN endpoint público real: se comprobaron 6 rutas
                           candidatas y todas dan 404/HTML. Devuelve [] a
                           propósito (ver docstring de la función).
  openverse_ampliado   ... funciona sin clave (24 resultados con excluded_source
                           quitado frente a los que recorta el filtro original).
  wikimedia_categorias ... funciona sin clave (búsqueda + categorías).
  pexels_video         ... funciona con clave (sin clave devuelve []).
  pixabay_video        ... funciona con clave (sin clave devuelve []).

Ejecuta `python -c "import fuentes_extra as F; print(F.probar())"` para repetir
la comprobación en cualquier momento (se ejecuta sin claves a propósito).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

try:                       # el entorno de ejecución puede no tener requests
    import requests
except Exception:          # pragma: no cover - sólo ocurre sin dependencias
    requests = None

APP = Path(__file__).resolve().parent
ROOT = APP.parent
CONFIG = ROOT / "config"

# Igual que make_short.py:299 y make_short.py:44
MIN_W, MIN_H = 1080, 1350
UA = {"User-Agent": "ShortsRedditLocal/1.0 (uso personal)"}
TIMEOUT = 30

# Prefijos de `id`: cada fuente tiene el suyo para que nunca colisionen.
PREFIJO = {
    "flickr_cc": "flickr_",
    "openverse_ampliado": "ovx_",
    "wikimedia_categorias": "wmc_",
    "pexels_video": "pexelsvid_",
    "pixabay_video": "pixabayvid_",
}

# Licencias de uso libre (también comercial) que este módulo acepta.
RE_LIBRE = re.compile(r"CC0|Public domain|No restrictions|CC BY", re.I)
RE_ESTRICTA = re.compile(r"CC0|Public domain|No restrictions", re.I)


def _claves():
    """Mismas claves que make_short.py:_claves() más la de Flickr."""
    k = {}
    f = CONFIG / "claves.json"
    if f.exists():
        try:
            k.update(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass                      # un claves.json corrupto no debe tumbar nada
    k.setdefault("pexels", os.getenv("PEXELS_API_KEY", ""))
    k.setdefault("pixabay", os.getenv("PIXABAY_API_KEY", ""))
    k.setdefault("flickr", os.getenv("FLICKR_API_KEY", ""))
    return k


def _clave(nombre, key=None):
    """Clave explícita si viene, si no la de config/entorno; '' si no hay."""
    return key or _claves().get(nombre, "") or ""


def _grande(w, h):
    """True si la pieza alcanza la resolución mínima del motor."""
    return (w or 0) >= MIN_W and (h or 0) >= MIN_H


def _limpio(txt, n=80):
    """Quita HTML de los metadatos y recorta."""
    return re.sub(r"<[^>]+>", "", txt or "").strip()[:n]


def _trae(url, **kw):
    """GET con UA y timeout fijos; lanza si requests no está disponible."""
    if requests is None:
        raise RuntimeError("el módulo 'requests' no está instalado en este intérprete")
    kw.setdefault("headers", UA)
    kw.setdefault("timeout", TIMEOUT)
    return requests.get(url, **kw)


# La API de Wikimedia responde HTTP 429 ("You are making too many requests to
# the API") si se encadenan llamadas sin pausa: comprobado en esta máquina
# durante las pruebas. Por eso las funciones de Commons van espaciadas (0,4 s)
# y, si aun así llega un 429, se reintenta con retroceso exponencial breve.
_PAUSA_WM = 0.4
_REINTENTOS_WM = 3


def _trae_json_wm(endpoint, params):
    """GET a Commons con pausa, reintento en 429 y devolución de JSON.

    Lanza la última excepción si se agotan los reintentos: cada fuente envuelve
    la llamada en try/except para no tumbar nada.
    """
    ultimo = None
    for intento in range(_REINTENTOS_WM):
        if intento:
            time.sleep(1.5 * intento)
        else:
            time.sleep(_PAUSA_WM)
        try:
            r = _trae(endpoint, params=params)
        except Exception as e:
            ultimo = e
            continue
        if r.status_code == 429 or "too many requests" in r.text[:200].lower():
            ultimo = RuntimeError("HTTP 429: demasiadas peticiones a la API de Wikimedia")
            continue
        try:
            return r.json()
        except Exception as e:
            ultimo = e
    raise ultimo if ultimo else RuntimeError("respuesta no válida de Wikimedia")


def _trae_json_api(url, params, intentos=3, pausa=0.5):
    """GET a una API JSON con reintento y respaldo ante 429 / reto anti-bot.

    Openverse (Cloudflare) responde 429 con una página HTML "Just a moment..."
    en vez de JSON cuando se le hacen muchas peticiones seguidas: eso se detectó
    en esta máquina durante las pruebas. Aquí se reintenta con espera creciente
    y, si llega algo que no es JSON, se lanza para que la fuente devuelva [] en
    lugar de propagar un JSONDecodeError.
    """
    ultimo = None
    for intento in range(intentos):
        if intento:
            time.sleep(pausa * (2 ** intento))
        try:
            r = _trae(url, params=params)
        except Exception as e:
            ultimo = e
            continue
        if r.status_code == 429:
            ultimo = RuntimeError("HTTP 429 (límite de peticiones o reto anti-bot)")
            continue
        try:
            return r.json()
        except Exception as e:
            ultimo = e
    raise ultimo if ultimo else RuntimeError("respuesta no válida")


# ------------------------------------------------------------------ Flickr
def src_flickr_cc(q, key=None, relajado=False):
    """Flickr — sólo fotos con licencia Creative Commons.

    Endpoint real y confirmado: https://api.flickr.com/services/rest/ con
    method=flickr.photos.search y format=json&nojsoncallback=1. Comprobado sin
    clave: responde {"stat":"fail","code":100,"message":"Invalid API Key..."},
    es decir el endpoint existe y sólo rechaza la petición por falta de clave.

    Variable de entorno a usar: FLICKR_API_KEY
    (equivalente en config/claves.json: la clave "flickr").
    Sin clave -> devuelve [] sin fallar.

    Filtro de licencias: el parámetro `license` de Flickr acepta una lista de
    ids separados por comas según la tabla de "Flickr API license values":
        1  = CC BY-NC-SA      4  = CC BY           7  = No known copyright
        2  = CC BY-NC         5  = CC BY-SA        9  = CC0 / Public Domain
        3  = CC BY-NC-ND      6  = CC BY-ND       10  = Public Domain Mark
    Este módulo pide 1,2,3,4,5,6,9,10 en modo relajado y 4,5,9,10 en modo
    estricto, pero DESCARTA después cualquier resultado cuya licencia no sea
    CC0 / Dominio Público / CC BY / CC BY-SA (nunca NC ni ND, que prohíben el
    uso comercial). Así el filtro final no depende de que Flickr lo aplique bien.

    AVISO DE VERIFICACIÓN: al no haber clave de Flickr en esta máquina, la ruta
    autenticada (incluidos los extras url_l/url_k y su recorte por resolución)
    NO ha sido probada de extremo a extremo. Si la respuesta no trae los extras
    `url_l`/`url_k`, se cae a la URL `_b` (1024 px de lado mayor) SÓLO en modo
    relajado, declarando entonces sus dimensiones reales; en modo estricto la
    foto se descarta porque `_b` nunca alcanza MIN_W/MIN_H.
    """
    k = _clave("flickr", key)
    if not k:
        return []
    lic = "4,5,9,10" if not relajado else "1,2,3,4,5,6,9,10"
    try:
        r = _trae("https://api.flickr.com/services/rest/", params=dict(
            method="flickr.photos.search", api_key=k, format="json", nojsoncallback=1,
            text=q, license=lic, sort="relevance", content_type=1, media="photos",
            safe_search=1, per_page=30, page=1,
            extras="license,owner_name,url_l,url_k,url_b,url_c,url_m,url_s,"
                   "width_l,height_l,width_k,height_k,url_z,width_z,height_z")).json()
    except Exception:
        return []
    if r.get("stat") != "ok":
        return []
    out = []
    for p in (r.get("photos") or {}).get("photo", []):
        try:
            url = p.get("url_k") or p.get("url_l") or ""
            w = int(p.get("width_k") or p.get("width_l") or 0)
            h = int(p.get("height_k") or p.get("height_l") or 0)
            if not url and p.get("url_b"):
                # `_b` = 1024 px de lado mayor; nunca llega a MIN_W/MIN_H, así que
                # sólo se usa en modo relajado y declarando lo que mide de verdad.
                if not relajado:
                    continue
                url = p["url_b"]
                w = int(p.get("width_b") or 0) or 1024
                h = int(p.get("height_b") or 0) or 683
            if not url:
                continue
            if not _grande(w, h) and not relajado:
                continue
            # La licencia real, tal como Flickr la declara en el propio resultado.
            nombre = {4: "CC BY", 5: "CC BY-SA", 9: "CC0", 10: "Dominio Público"}.get(p.get("license"))
            if nombre is None:
                continue                                    # NC/ND o desconocida -> fuera
            artist = p.get("ownername") or ""
            out.append(dict(
                url=url,
                thumb=p.get("url_c") or p.get("url_m") or p.get("url_s") or url,
                w=w, h=h, id=f"flickr_{p['id']}",
                title=(p.get("title") or "").strip() or q,
                artist=artist[:80] or "desconocido",
                license=nombre,
                page=p.get("url") or f"https://www.flickr.com/photos/{p.get('owner', '')}/{p['id']}",
                fuente="Flickr CC"))
        except Exception:
            continue                                        # una foto rara no corta el bucle
    return out


# ------------------------------------------------------------------ StockSnap
def src_stocksnap(q, key=None, relajado=False):
    """StockSnap.io — devuelve [] a propósito: NO tiene API pública real.

    Comprobado con red desde este equipo (GET con UA y timeout=30):

        https://stocksnap.io/api/            -> 404 (HTML "Page not found")
        https://stocksnap.io/api/search/     -> 404 (HTML)
        https://stocksnap.io/api/search?q=.. -> 404 (HTML)
        https://stocksnap.io/api/v1/search?q=..  -> 404 (HTML)
        https://stocksnap.io/api/photos?q=..     -> 404 (HTML)
        https://stocksnap.io/api/search/<q>      -> 404 (HTML)
        https://stocksnap.io/search/<q>.json     -> 200 pero text/html (no es API)

    Su buscador es JavaScript contra un backend privado y no documentado. Por la
    regla de este módulo (prohibido inventar endpoints) esta fuente NO llama a
    ninguna URL adivinada: devuelve [] de forma honesta en lugar de romper.

    ALTERNATIVA COMPROBADA: StockSnap SÍ es utilizable a través de Openverse,
    que lo tiene indexado y sirve su licencia CC0. `src_openverse_ampliado`
    (que no lleva `excluded_source`) lo devuelve como fuente "stocksnap", por
    ejemplo "Male Nurse" y "Senior Doctor". Usa esa vía para StockSnap.

    Además: por esa vía las dimensiones declaradas (p. ej. 8688x5792) no
    coinciden con el JPEG entregado, que es una miniatura de 960 px de ancho
    (https://cdn.stocksnap.io/img-thumbs/960w/<ID>.jpg), así que la resolución
    real puede quedar por debajo de MIN_W aunque el ancho declarado sea enorme.
    """
    return []


# ------------------------------------------------------------------ Openverse
def src_openverse_ampliado(q, key=None, relajado=False):
    """Openverse SIN `excluded_source` — mismo endpoint, catálogo mucho mayor.

    Igual que make_short.py:330-340 (https://api.openverse.org/v1/images/) pero
    quitando el parámetro `excluded_source`, que recortaba el catálogo y excluía
    rawpixel, wikimedia, smithsonian, brooklynmuseum, met, clevelandmuseum,
    europeana, rijksmuseum y nappy.

    Licencias: "cc0,pdm" en estricto y "cc0,pdm,by,by-sa" en relajado (mismas
    que la fuente base). category="photograph", mature="false".
    Sin clave: la API de Openverse es abierta, así que funciona igual.

    DETALLE IMPORTANTE (comprobado con red): la API anónima limita page_size a
    20 y responde {"detail": "page_size may not exceed 20 for anonymous
    requests"} sin campo "results". make_short.py:333 pide page_size=30, así que
    hoy src_openverse devuelve [] siempre. Aquí se piden 20 por página y dos
    páginas (hasta 40 candidatos) para no quedarse corto.

    Nota de calidad (verificada): Openverse declara a veces anchos/altos muy
    superiores al archivo real, porque a veces entrega una miniatura (caso de
    las fotos de stocksnap, servidas a 960 px). El filtro de resolución usa las
    dimensiones declaradas, igual que la fuente base, así que puede colarse
    alguna pieza más pequeña de lo que dice el catálogo.
    """
    params = dict(q=q, license="cc0,pdm,by,by-sa" if relajado else "cc0,pdm",
                  category="photograph", size="medium,large" if relajado else "large",
                  page_size=20, mature="false")
    # OJO, comprobado: la API anónima RECHAZA page_size > 20 con
    # {"detail": "page_size may not exceed 20 for anonymous requests"} y esa
    # respuesta no trae "results", así que la fuente devolvería []. Por eso aquí
    # se pide 20 por página y se piden dos páginas para no perder catálogo.
    # (make_short.py:333 pide page_size=30, de modo que hoy src_openverse
    #  devuelve [] en modo anónimo por este mismo motivo.)
    res = []
    try:
        for pagina in (1, 2):
            r = _trae_json_api("https://api.openverse.org/v1/images/",
                               {**params, "page": pagina})
            trozo = r.get("results") or []
            res.extend(trozo)
            if len(trozo) < params["page_size"]:
                break
    except Exception:
        if not res:
            return []
    out = []
    for p in res:
        try:
            w = int(p.get("width") or 0)
            h = int(p.get("height") or 0)
            if not _grande(w, h):
                continue
            lic = (p.get("license") or "").lower()
            if lic not in ("cc0", "pdm", "by", "by-sa"):
                continue
            if lic in ("by", "by-sa") and not relajado:
                continue
            if not p.get("url"):
                continue
            out.append(dict(
                url=p["url"], thumb=p.get("thumbnail"), w=w, h=h,
                id=f"ovx_{p['id']}", title=p.get("title") or q,
                artist=p.get("creator") or "desconocido",
                license={"cc0": "CC0", "pdm": "Dominio Público"}.get(
                    lic, f"CC {lic.upper()} {p.get('license_version', '')}".strip()),
                page=p.get("foreign_landing_url", ""),
                fuente=f"Openverse/{p.get('source', '')}",
                tags=" ".join(t.get("name", "") for t in (p.get("tags") or []))))
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ Wikimedia
def _wm_paginas(endpoint, params):
    """Llama a la API de Commons y devuelve las páginas con imageinfo.

    Sólo vale para consultas que usan `prop`/`generator` (devuelven query.pages).
    Para las consultas con `list=` hay que usar _wm_lista: la respuesta trae la
    clave con el nombre de la lista (query.categorymembers, query.allpages...),
    NO query.pages. Confundirlas devuelve siempre vacío.
    """
    return list((_trae_json_wm(endpoint, params).get("query") or {}).get("pages", {}).values())


def _wm_lista(endpoint, params, nombre):
    """Igual que _wm_paginas pero para consultas `list=<nombre>`."""
    return (_trae_json_wm(endpoint, params).get("query") or {}).get(nombre) or []


def _wm_categorias(endpoint, q, limite=3):
    """Nombres REALES de categorías de Commons relacionados con la consulta.

    Se usa list=allpages con apnamespace=14 (Categoría) y apprefix=<q>. Es la vía
    comprobada: `list=prefixsearch` con psnamespace=14 no devuelve JSON en este
    endpoint, y `list=search` con srnamespace=14 tampoco. allpages sí responde y
    encuentra "Category:Hospital corridors" partiendo de "hospital corridor",
    pese a la diferencia de mayúscula y de plural.

    Sólo se aceptan categorías cuyo título contenga TODAS las palabras de
    contenido de `q`, para no derivar a categorías genéricas no deseadas
    ("Category:Hospitals in Germany" no vale para "hospital corridor").
    """
    # Búsqueda de categorías: todas las palabras de `q`, no una cualquiera.
    palabras = [w for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 2]
    try:
        ap = _wm_lista(endpoint, dict(
            action="query", format="json", list="allpages", apnamespace=14,
            apprefix=q, aplimit=20), "allpages")
    except Exception:
        return []
    out = []
    for p in ap:
        titulo = p.get("title", "")
        bajo = titulo.lower()
        if not palabras or not all(w in bajo for w in palabras):
            continue
        out.append(titulo)
        if len(out) >= limite:
            break
    return out


def src_wikimedia_categorias(q, key=None, relajado=False):
    """Wikimedia Commons — búsqueda normal Y ADEMÁS por categorías.

    Mismo endpoint que make_short.py:342-356
    (https://commons.wikimedia.org/w/api.php) con dos vías que se unen y se
    deduplican por pageid:

      1. generator=search, gsrnamespace=6, gsrsearch="<q> filetype:bitmap"
         (idéntico al de make_short.py).
      2. Categorías: se resuelven primero los nombres reales con
         list=allpages&apnamespace=14&apprefix=<q> (la API de Commons es
         sensible a mayúsculas y plural: "Category:hospital corridor" NO existe,
         mientras que "Category:Hospital corridors" sí), se conserva sólo lo que
         contenga TODAS las palabras de la consulta (para no derivar a
         "Category:Hospitals in Germany"), y de ahí se leen los archivos con
         list=categorymembers&cmtype=file y luego sus imageinfo en una segunda
         llamada con prop=imageinfo&titles=... (obligatorio: `generator=search`
         y `list=categorymembers` no pueden combinarse en la misma petición).

    Licencias aceptadas: CC0 / Public domain / No restrictions; en modo relajado
    también CC BY y CC BY-SA (mismo criterio que make_short.py:350, que en
    realidad relaja a cualquier cosa que empiece por "CC BY", incluido NC/ND).

    Sin clave: la API de Commons es abierta, funciona igual.
    """
    endpoint = "https://commons.wikimedia.org/w/api.php"
    paginas = {}
    # Vía 1: búsqueda (idéntica a la de make_short.py)
    try:
        for p in _wm_paginas(endpoint, dict(
                action="query", format="json", generator="search", gsrnamespace=6,
                gsrlimit=20, gsrsearch=q + " filetype:bitmap", prop="imageinfo",
                iiprop="url|extmetadata|size", iiurlwidth=2000)):
            paginas[p.get("pageid")] = p
    except Exception:
        pass
    # Vía 2: categorías (nombres resueltos de verdad, no adivinados)
    for cat in _wm_categorias(endpoint, q):
        try:
            titulos = [m.get("title") for m in _wm_lista(endpoint, dict(
                action="query", format="json", list="categorymembers", cmtitle=cat,
                cmtype="file", cmlimit=50), "categorymembers") if m.get("title")]
            if not titulos:
                continue
            for i in range(0, len(titulos), 20):
                for p in _wm_paginas(endpoint, dict(
                        action="query", format="json", titles="|".join(titulos[i:i + 20]),
                        prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=2000)):
                    if p.get("pageid"):
                        paginas.setdefault(p["pageid"], p)
        except Exception:
            continue
    out = []
    for p in paginas.values():
        try:
            ii = (p.get("imageinfo") or [{}])[0]
            w, h = int(ii.get("width") or 0), int(ii.get("height") or 0)
            if not _grande(w, h):
                continue
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            if not (RE_LIBRE if relajado else RE_ESTRICTA).search(lic):
                continue
            out.append(dict(
                url=ii.get("thumburl") or ii.get("url"), thumb=ii.get("thumburl"),
                w=w, h=h, id="wmc_" + str(p["pageid"]),
                title=(p.get("title") or "").replace("File:", ""),
                artist=_limpio(md.get("Artist", {}).get("value", "desconocido")),
                license=lic, page=ii.get("descriptionurl", ""),
                fuente="Wikimedia Commons (categorías)"))
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ Pexels vídeo
def src_pexels_video(q, key=None, relajado=False):
    """Pexels — VÍDEOS verticales. Requiere clave (PEXELS_API_KEY).

    Endpoint real y verificado: https://api.pexels.com/videos/search con
    orientation=portrait. Sin clave -> [] sin fallar.

    `url` es el archivo de vídeo MP4 de calidad razonable: de los
    `video_files` se elige el de menor tamaño cuyo lado MENOR cumpla MIN_W
    (1080), que en vertical es 1080x1920; si ninguno llega, el mayor disponible
    que aún sirva para vertical. `thumb` es la primera imagen de previsualización.

    OJO: `w`/`h` son las del vídeo elegido (no las del original), para que el
    filtro de resolución de make_short.py mida el archivo que realmente se
    descarga. Los vídeos que no alcanzan MIN_W por el lado menor se descartan.
    """
    k = _clave("pexels", key)
    if not k:
        return []
    try:
        r = _trae("https://api.pexels.com/videos/search",
                  headers={"Authorization": k, **UA},
                  params=dict(query=q, per_page=30, orientation="portrait", size="large")).json()
    except Exception:
        return []
    out = []
    for v in r.get("videos", []):
        try:
            verticales = [f for f in (v.get("video_files") or [])
                          if (f.get("file_type") or "").startswith("video")
                          and (f.get("width") or 0) < (f.get("height") or 0)]
            if not verticales:
                continue
            buenos = [f for f in verticales if min(int(f.get("width") or 0),
                                                   int(f.get("height") or 0)) >= MIN_W]
            if buenos:
                f = min(buenos, key=lambda x: int(x.get("width") or 0) * int(x.get("height") or 0))
            elif relajado:
                f = max(verticales, key=lambda x: int(x.get("width") or 0) * int(x.get("height") or 0))
            else:
                continue                       # no llega al mínimo y no se pidió relajar
            w, h = int(f.get("width") or 0), int(f.get("height") or 0)
            pics = v.get("video_pictures") or []
            out.append(dict(
                url=f.get("link"), thumb=(pics[0].get("picture") if pics else v.get("image")),
                w=w, h=h, id=f"pexelsvid_{v['id']}",
                title=(v.get("url") or "").rstrip("/").split("/")[-1].replace("-", " ") or q,
                artist=((v.get("user") or {}).get("name") or "desconocido")[:80],
                license="Licencia Pexels", page=v.get("url", ""),
                fuente="Pexels Vídeo",
                tags=" ".join(v.get("tags") or []) if isinstance(v.get("tags"), list) else ""))
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ Pixabay vídeo
def src_pixabay_video(q, key=None, relajado=False):
    """Pixabay — VÍDEOS. Requiere clave (PIXABAY_API_KEY).

    Endpoint real y verificado: https://pixabay.com/api/videos/ (la API de
    imágenes es /api/ y la de vídeo /api/videos/). Sin clave -> [] sin fallar.

    Parámetros usados: q, video_type=film (descarta las animaciones generadas
    por IA que dominan la búsqueda por defecto), safesearch=true, per_page=30.

    `url` es el MP4 de calidad razonable: de la escala de Pixabay
    (tiny < small < medium < large) se prefiere el tamaño VERTICAL más pequeño
    cuyo lado menor cumpla MIN_W; si no hay vertical que sirva, se acepta el
    horizontal más pequeño que cumpla el mínimo (y sólo en modo relajado se
    acepta algo por debajo del mínimo). `thumb` es su JPEG.

    OJO: como en Pexels, `w`/`h` son los del archivo elegido, para que el filtro
    de resolución mida lo que se descarga de verdad.
    """
    k = _clave("pixabay", key)
    if not k:
        return []
    try:
        r = _trae("https://pixabay.com/api/videos/", params=dict(
            key=k, q=q, video_type="film", safesearch="true", per_page=30,
            order="popular")).json()
    except Exception:
        return []
    out = []
    for h_ in r.get("hits", []):
        try:
            vids = h_.get("videos") or {}
            cand = [(n, vids[n]) for n in ("tiny", "small", "medium", "large")
                    if n in vids and vids[n].get("url") and vids[n].get("width")
                    and vids[n].get("height")]
            if not cand:
                continue
            vids = lambda l: [(n, v) for n, v in l if int(v["width"]) < int(v["height"])]
            area = lambda nv: int(nv[1]["width"]) * int(nv[1]["height"])
            buenos = sorted([nv for nv in cand if min(int(nv[1]["width"]), int(nv[1]["height"])) >= MIN_W],
                            key=area)
            vertical = sorted(vids(cand), key=area)
            # Vertical y por encima del mínimo: es lo que necesita un short.
            elegido = next((nv for nv in buenos if nv in vertical), None)
            if elegido is None:
                if not relajado:
                    continue      # en estricto no se acepta horizontal ni baja resolución
                # En relajado sí se admite lo que haya, prefiriendo vertical.
                elegido = vertical[0] if vertical else (buenos[0] if buenos else sorted(cand, key=area)[0])
            n, v = elegido
            w, h = int(v["width"]), int(v["height"])
            out.append(dict(
                url=v["url"], thumb=v.get("thumbnail"), w=w, h=h,
                id=f"pixabayvid_{h_['id']}", title=h_.get("tags", q),
                artist=(h_.get("user") or "")[:80], license="Licencia Pixabay",
                page=h_.get("pageURL", ""), fuente="Pixabay Vídeo",
                tags=h_.get("tags", "")))
        except Exception:
            continue
    return out


def src_coverr_video(q, key=None, relajado=False):
    """VÍDEOS de Coverr. SIN CLAVE (endpoint público del sitio). Verificado en vivo.

    Dos avisos medidos: los clips `is_premium` son Coverr+ (suscripción) y el endpoint NO
    respeta los parámetros de faceta, así que el filtro se hace aquí; y su buscador hace AND
    estricto, por lo que "hospital corridor" da 0 y conviene una sola palabra. Es casi todo
    horizontal (1920x1080), pero el pipeline lo recorta a 9:16 con ffmpeg.
    """
    try:
        r = _trae_json_api("https://coverr.co/api/videos", {"query": q, "hitsPerPage": 40}, intentos=2)
    except Exception:
        return []
    out = []
    for h in (r.get("hits") or []):
        if not isinstance(h, dict) or h.get("is_premium"):
            continue
        bf = h.get("base_filename")
        if not bf:
            continue
        out.append(dict(
            url=f"https://cdn.coverr.co/videos/{bf}/1080p.mp4",
            thumb=f"https://cdn.coverr.co/videos/{bf}/thumbnail?width=640",
            w=int(h.get("max_width") or 0), h=int(h.get("max_height") or 0),
            id=f"coverr_{h.get('id')}", title=h.get("title") or q,
            artist="desconocido", license="Licencia Coverr",
            page=f"https://coverr.co/videos/{h.get('slug')}-{h.get('id')}",
            fuente="Coverr", tags=" ".join(h.get("tags") or [])))
    return out


def src_wikimedia_video(q, key=None, relajado=False):
    """VÍDEOS de Wikimedia Commons. SIN CLAVE. Verificado en vivo (búsqueda + descarga).

    Aviso: Commons NO sirve mp4 (solo .webm/.ogv y transcodes .mov) y su catálogo de vídeo es
    minúsculo: 3 resultados reales para "hospital corridor". Sirve para metraje muy concreto,
    no como fuente principal.
    """
    try:
        r = _trae_json_wm("https://commons.wikimedia.org/w/api.php", dict(
            action="query", format="json", generator="search", gsrnamespace=6, gsrlimit=30,
            gsrsearch=f"{q} filetype:video", prop="videoinfo",
            viprop="url|size|mime|derivatives|extmetadata"))
    except Exception:
        return []
    out = []
    for p in ((r.get("query") or {}).get("pages") or {}).values():
        vi = (p.get("videoinfo") or [{}])[0]
        md = vi.get("extmetadata", {}) or {}
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"CC0|Public domain|No restrictions" + (r"|CC BY" if relajado else ""), lic, re.I):
            continue
        urls = [d.get("src") for d in (vi.get("derivatives") or [])
                if isinstance(d, dict) and d.get("src") and d.get("width")]
        urls.sort(key=lambda u: 0 if "480p" in u else 1)   # el transcode ligero antes que el original
        url = (urls or [vi.get("url")])[0]
        if not url:
            continue
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "desconocido")).strip()
        out.append(dict(url=url, thumb=None, w=vi.get("width", 0), h=vi.get("height", 0),
                        id="wmv_" + str(p.get("pageid")), title=p.get("title", "").replace("File:", ""),
                        artist=artist[:80], license=lic, page=vi.get("descriptionurl", ""),
                        fuente="Wikimedia Vídeo"))
    return out


# ------------------------------------------------------------------ registro
FUENTES_EXTRA = {
    "flickr_cc": src_flickr_cc,
    "stocksnap": src_stocksnap,
    "openverse_ampliado": src_openverse_ampliado,
    "wikimedia_categorias": src_wikimedia_categorias,
    "pexels_video": src_pexels_video,
    "pixabay_video": src_pixabay_video,
    "coverr_video": src_coverr_video,
    "wikimedia_video": src_wikimedia_video,
}


def fuentes_todas(base: dict, activar: list | None = None) -> dict:
    """Fusiona las fuentes base con las nuevas SIN sobrescribir las existentes.

    base    -> dict tipo FUENTES de make_short.py (no se modifica: se copia).
    activar -> lista opcional de nombres nuevos a añadir; por defecto, todas.

    Si `base` ya trae una clave con el mismo nombre, se conserva la de `base` y
    se avisa por stdout en vez de pisarla en silencio.
    """
    todas = dict(base or {})
    nombres = list(activar) if activar else list(FUENTES_EXTRA)
    for nombre in nombres:
        fn = FUENTES_EXTRA.get(nombre)
        if fn is None:
            print(f"[fuentes_extra] aviso: '{nombre}' no es una fuente extra conocida")
            continue
        if nombre in todas:
            print(f"[fuentes_extra] aviso: '{nombre}' ya existe en las fuentes base; se conserva la base")
            continue
        todas[nombre] = fn
    return todas


def probar(nombres=None) -> dict:
    """Ejecuta cada fuente con la consulta "hospital corridor" y SIN claves.

    Devuelve {nombre: (ok, n_resultados, error_o_None)}:
      ok     -> True si la fuente devolvió una lista de dicts sin excepción.
      n      -> número real de resultados devueltos.
      error  -> None, o el texto de la excepción capturada.

    Sin claves a propósito: las fuentes que requieren clave deben devolver []
    sin fallar, y eso es justo lo que aquí se comprueba.
    """
    q = "hospital corridor"
    objetivo = list(nombres) if nombres else list(FUENTES_EXTRA)
    res = {}
    for nombre in objetivo:
        fn = FUENTES_EXTRA.get(nombre)
        if fn is None:
            res[nombre] = (False, 0, "fuente desconocida")
            continue
        try:
            r = fn(q, None)
            if not isinstance(r, list):
                res[nombre] = (False, 0, f"devolvió {type(r).__name__}, no list")
                continue
            res[nombre] = (True, len(r), None)
        except Exception as e:
            res[nombre] = (False, 0, f"{type(e).__name__}: {e}")
    return res


if __name__ == "__main__":
    print(json.dumps(probar(), ensure_ascii=False, indent=1, default=str))
