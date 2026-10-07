"""Efectos de sonido del Short: detecta los MOMENTOS CLAVE del guion y construye la pista de SFX.

Tres capas, en este orden para cada tipo de efecto:
  1) archivo ya cacheado en cache_dir
  2) descarga de fuentes libres (Openverse, solo CC0 / Dominio Público)
  3) síntesis con numpy  ← fallback obligatorio: sin red, sin ffmpeg, sin excusas
La detección de momentos es determinista (léxico + puntuación + campos del guion), sin LLM y sin red.
La pista se suma sobre la mezcla existente en make_short.py, que después normaliza."""
import json, random, re, subprocess, time, zlib
from pathlib import Path
import numpy as np

SR = 24000                     # mismo sample rate interno que extras.py y musica.py
MIN_GAP = 0.35                 # separación mínima entre dos SFX
MAX_DENSIDAD = 3.5             # como mucho ~1 SFX cada 3.5 s. Estaba en 2.5 y el render real
                               # salió con 26 efectos en 66 s (uno cada 2.5 s): en un relato
                               # dramático suena a videojuego y compite con la voz (auditoría).
GAP_WHOOSH = 4.5               # los whoosh de cambio de plano llevan su PROPIO tope, porque en
                               # la 1ª pasada se saltaban el cupo global y se acumulaban.
PICO = 0.5                     # pico de cada SFX ya sintetizado/decodificado; el volumen final lo pone `vol`

# volumen por defecto de cada tipo (multiplicado por el campo `vol` del evento)
VOL = {
    "whoosh": 0.12,
    "impacto": 0.30,
    "latido": 0.22,
    "riser": 0.16,
    "notificacion": 0.20,
    "campana": 0.24,
    "pop": 0.18,
}
# orden de importancia para cuando hay exceso de eventos
IMPORTANCIA = ["campana", "impacto", "riser", "latido", "notificacion", "pop", "whoosh"]
# duración máxima aceptada de cada efecto (los archivos descargados se recortan)
DUR_MAX = {"whoosh": 0.9, "impacto": 0.8, "latido": 1.2, "riser": 1.8,
           "notificacion": 0.8, "campana": 2.0, "pop": 0.4}

# ------------------------------------------------------------------ léxico determinista
GIRO = ("pero", "sin embargo", "hasta que", "de repente", "entonces", "lo peor", "resulta que",
        "y ahora", "no obstante", "aunque", "al final", "por fin", "y ahí", "justo cuando")
IMPACTO = ("acusó", "acusó a", "culpó", "gritó", "exigió", "ultimátum", "insinuó", "traicionó",
           "mintió", "fingió", "abandonó", "echó", "denunció", "amenazó", "reventó", "explotó",
           "se hartó", "no pienso", "jamás", "nunca más", "mentira", "inaceptable", "indignante")
TENSION = ("cáncer", "murió", "muerte", "enfermedad", "enfermó", "hospital", "diagnóstico",
           "ansiedad", "depresión", "pánico", "miedo", "terror", "sangre", "dolor", "crisis",
           "duelo", "luto", "grave", "tumor", "infarto", "derrumbe", "sola", "solo")
NOTI = ("mensaje", "mensajes", "whatsapp", "llamada", "llamó", "notificación", "notificaciones",
        "correo", "email", "escribió", "respondió", "chat", "voz", "audio", "me envió", "recibí")
RESOL = ("finalmente", "al final", "por fin", "moraleja", "conclusión", "aprendí", "lección",
         "desde entonces", "colorín", "y así", "nunca volvió", "todo terminó")
DINERO = re.compile(r"(\d+\s*%|\d+\s*(€|\$|dólares|euros|pesos|mil|millones)|\b\d{2,}\b)", re.I)


def _consola(s):
    """Los .bat del proyecto corren en consolas cp1252/cp850: nada de reventar por un acento."""
    s = str(s)
    try:
        s.encode("cp1252")
    except UnicodeEncodeError:
        s = s.encode("ascii", "replace").decode("ascii")
    return s


def _plano(cfg, k):
    """Índice de imagen de la escena k, si el guion lo trae como número."""
    e = cfg["escenas"][k]
    v = e.get("imagen")
    return int(v) if isinstance(v, (int, float)) else None


def _candidatos(cfg, subs, spans, seg_times, poll_start):
    """Todos los momentos clave propuestos, sin filtrar todavía. Determinista."""
    esc = cfg.get("escenas") or []
    out = []

    def add(t, tipo, vol, motivo):
        out.append({"t": float(max(t, 0.0)), "tipo": tipo, "vol": float(vol), "motivo": motivo})

    # 1) cambios de plano/escena → whoosh (en cada cambio de plano, sin límite de densidad)
    prev = None
    for k in range(1, len(seg_times)):
        t = seg_times[k][0]
        plano = _plano(cfg, k)
        cambio = plano is not None and prev is not None and plano != prev
        if plano is not None:
            prev = plano
        if not cambio and k < len(spans) and spans[k][0] != spans[k - 1][0]:
            cambio = True
        add(t, "whoosh", VOL["whoosh"] + (0.03 if cambio else 0.0),
            "cambio de plano" if cambio else "cambio de escena")

    # 2) escenas: giro, opinión, tensión, notificación, resolución, cifras y signos
    for k, s in enumerate(esc):
        texto = (s.get("texto") or "").replace("*", "")
        bajo = texto.lower()
        a = seg_times[k][0] if k < len(seg_times) else 0.0
        if s.get("tipo") == "opinion":
            add(a + 0.35, "impacto", VOL["impacto"], "escena de opinión")
        m = re.search("|".join(re.escape(g) for g in GIRO), bajo)
        if m:
            add(a + m.start() * 0.03, "riser", VOL["riser"], f"giro: «{m.group(0)}»")
        m = re.search("|".join(re.escape(g) for g in IMPACTO), bajo)
        if m:
            add(a + 0.4, "impacto", VOL["impacto"], f"golpe narrativo: «{m.group(0)}»")
        n = sum(1 for w in TENSION if re.search(r"\b" + re.escape(w), bajo))
        if n:
            add(a + 0.5, "latido", min(0.35, VOL["latido"] + 0.04 * (n - 1)), f"tensión ({n} marcas)")
        m = re.search("|".join(re.escape(g) for g in NOTI), bajo)
        if m:
            add(a + 0.6, "notificacion", VOL["notificacion"], f"mensaje/llamada: «{m.group(0)}»")
        m = re.search("|".join(re.escape(g) for g in RESOL), bajo)
        if m:
            add(a + 0.4, "campana", VOL["campana"], f"resolución: «{m.group(0)}»")
        if "?" in texto or "¿" in texto:
            add(a + 0.7, "latido", VOL["latido"], "pregunta")
        if "!" in texto or "¡" in texto:
            add(a + 0.45, "impacto", VOL["impacto"], "exclamación")
        d = DINERO.search(texto)
        if d:
            add(a + 0.55, "notificacion", VOL["notificacion"], f"cifra/dinero: «{d.group(0)}»")

    # 3) remate: última escena con pregunta o resolución → campana
    if esc:
        ult = esc[-1]
        bajo_u = (ult.get("texto") or "").lower()
        if "?" in bajo_u or any(g in bajo_u for g in RESOL):
            add(seg_times[-1][0] + 0.4, "campana", VOL["campana"], "remate final")

    # 4) encuesta final → pop (y campana un poco antes si el cierre no la puso)
    if poll_start is not None:
        add(poll_start, "pop", VOL["pop"], "aparición de la encuesta")

    # 5) bloques de subtítulo con palabras resaltadas → golpe de apoyo (pocos: 1 cada 8 s)
    resaltadas = [sub[0] for sub in subs if any(hl for l in sub[2] for _, hl in l)]
    last = -9.0
    for t in sorted(resaltadas):
        if t - last >= 8.0 and t > 1.0:
            add(t, "impacto", VOL["impacto"] * 0.85, "palabra resaltada")
            last = t
    return out


def momentos(cfg, subs, spans, seg_times, poll_start=None):
    """Momentos clave del guion → [{"t", "tipo", "vol", "motivo"}], ordenado por t.

    Determinista: léxico de giro en español, signos ¿? ¡!, cifras y dinero, campo tipo="opinion",
    escena final de pregunta y el momento poll_start. Respeta 0.35 s de separación mínima y
    ~1 evento cada 2.5 s (los whoosh de cambio de plano pueden ir más seguidos). Si hay exceso,
    se prioriza por importancia (campana > impacto > riser > latido > notificacion > pop > whoosh)."""
    seg_times = list(seg_times or [])
    if not seg_times:
        return []
    final = seg_times[-1][1]
    cand = _candidatos(cfg, subs or [], spans or [], seg_times, poll_start)

    # deduplicación: mismo tipo en el mismo instante (redondeado a 50 ms) se queda con el mejor motivo
    unicos = {}
    for c in cand:
        k = (c["tipo"], round(c["t"], 2))
        if k not in unicos or c["vol"] > unicos[k]["vol"]:
            unicos[k] = c
    cand = sorted(unicos.values(), key=lambda c: (c["t"], c["tipo"]))

    aceptados, puestos = [], set()

    def hueco(t, min_gap):
        return all(abs(t - a["t"]) >= min_gap for a in aceptados)

    # 1ª pasada: los whoosh de cambio de plano acompañan al corte, pero con TOPE PROPIO.
    # Antes se saltaban el cupo global ("son baratos, van casi siempre") y se acumulaban: el
    # render real sacó 26 efectos en 66 s. GAP_WHOOSH evita que se solapen entre cortes seguidos.
    for c in cand:
        if c["tipo"] == "whoosh" and c["motivo"] == "cambio de plano" \
                and hueco(c["t"], MIN_GAP) and hueco(c["t"], GAP_WHOOSH):
            aceptados.append(c); puestos.add(id(c))

    # 2ª pasada: el resto por importancia, respetando separación y presupuesto global
    cupo = max(1, int(final / MAX_DENSIDAD))
    for tipo in IMPORTANCIA:
        for c in cand:
            if c["tipo"] != tipo or id(c) in puestos:
                continue
            if len(aceptados) >= cupo:
                break
            if hueco(c["t"], MIN_GAP) and c["t"] <= final:
                aceptados.append(c); puestos.add(id(c))

    aceptados.sort(key=lambda c: (c["t"], c["tipo"]))
    return aceptados


# ------------------------------------------------------------------ síntesis (fallback obligatorio)
def _rng(tipo, semilla):
    # crc32 y no hash(): el hash de las cadenas cambia en cada proceso y la síntesis no sería reproducible
    return np.random.default_rng(zlib.crc32(f"{tipo}:{int(semilla)}".encode()) % (2 ** 32))


def _normaliza(x):
    x = np.nan_to_num(np.asarray(x, np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    return (x / (np.abs(x).max() + 1e-9) * PICO).astype(np.float32)


def _fundido(x, ms=6):
    k = min(int(SR * ms / 1000), max(len(x) // 4, 1))
    if k > 1:
        x[:k] *= np.linspace(0, 1, k)
        x[-k:] *= np.linspace(1, 0, k)
    return x


def _ascendente(n):
    """Tamaño de paso creciente (integrado = x**2/2), para un barrido suave."""
    return np.arange(n) / n


def _ema(x, k):
    """Filtro y[i] = (1-k)y[i-1] + k·x[i] con k variable (un coeficiente por muestra).
    Se hace muestra a muestra y en float64: vectorizarlo con exponenciales acumuladas desborda,
    y con scipy.signal.lfilter los coeficientes variables hacen divergir el filtro (inf/NaN).
    Son ~40.000 muestras por efecto: el bucle cuesta milisegundos y siempre da el mismo resultado."""
    x = np.asarray(x, np.float64); k = np.asarray(k, np.float64)
    y = np.empty(len(x))
    acc = 0.0
    for i in range(len(x)):
        acc += k[i] * (x[i] - acc)
        y[i] = acc
    return y


def _whoosh(dur=0.45, semilla=0):
    """Ruido filtrado con barrido: el corte sube y el ruido se apaga."""
    n = int(dur * SR); rng = _rng("whoosh", semilla)
    noise = rng.standard_normal(n)
    u = np.arange(n) / n
    k = 0.015 + 0.35 * u ** 2                      # coeficiente del filtro: de grave a agudo
    x = np.empty(n); x[0] = 0.0
    x[1:] = noise[1:]
    y = _ema(x, k)                                 # y[i] = (1-k)y[i-1] + k·x[i]
    env = np.sin(np.pi * np.clip(np.arange(n) / SR / dur, 0, 1)) ** 2
    return _normaliza(_fundido(y * env))


def _pop(f=1320, dur=0.22, semilla=0):
    """Seno con decaimiento exponencial rápido (dos parciales para que suene a «pop»)."""
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.01 * t)
    return _normaliza(_fundido(s * np.exp(-t * 22) / 1.35))


def _latido(f=62, dur=1.1, semilla=0):
    """Dos pulsos graves (55-70 Hz) separados ~0.32 s, como un corazón."""
    n = int(dur * SR); t = np.arange(n) / SR
    out = np.zeros(n)
    for i, (at, amp) in enumerate(((0.0, 1.0), (0.32, 0.72))):
        j = int(at * SR)
        seg = np.arange(n - j) / SR
        f0 = f * (1 + 0.06 * i)
        golpe = np.sin(2 * np.pi * (f0 + 30 * np.exp(-seg * 25)) * seg) * np.exp(-seg * 9) * amp
        out[j:] += golpe
    return _normaliza(_fundido(out))


def _riser(dur=1.6, semilla=0):
    """Barrido de ruido ascendente con crescendo: anuncia el giro."""
    n = int(dur * SR); rng = _rng("riser", semilla)
    noise = rng.standard_normal(n)
    k = 0.01 + 0.5 * _ascendente(n) ** 2
    x = np.empty(n); x[0] = 0.0; x[1:] = noise[1:]
    y = _ema(x, k)
    t = np.arange(n) / SR
    silbido = np.sin(2 * np.pi * (300 + 1400 * _ascendente(n) ** 2) * t) * 0.25
    env = (_ascendente(n) ** 1.6) * np.minimum(1, (dur - t) / 0.15)   # crescendo y corte final
    return _normaliza(_fundido((y * 0.9 + silbido) * env))


def _notificacion(dur=0.55, semilla=0):
    """Dos tonos cortos tipo aviso de móvil."""
    n = int(dur * SR); out = np.zeros(n)
    for at, f in ((0.0, 988), (0.17, 1319)):
        j = int(at * SR); seg = np.arange(n - j) / SR
        out[j:] += (np.sin(2 * np.pi * f * seg) + 0.3 * np.sin(2 * np.pi * 2 * f * seg)) * np.exp(-seg * 16)
    return _normaliza(_fundido(out))


def _campana(f=660, dur=1.8, semilla=0):
    """Seno con decaimiento largo y armónicos inarmónicos: resolución."""
    n = int(dur * SR); t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.55 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 1.6)
         + 0.30 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 3.0))
    return _normaliza(_fundido(s * np.exp(-t * 1.8)))


def _impacto(f=48, dur=0.7, semilla=0):
    """Seno grave corto + golpe de ruido: acusación o golpe narrativo."""
    n = int(dur * SR); t = np.arange(n) / SR; rng = _rng("impacto", semilla)
    boom = np.sin(2 * np.pi * (f + 70 * np.exp(-t * 18)) * t) * np.exp(-t * 5.5)
    ruido = rng.standard_normal(n) * np.exp(-t * 30) * 0.55
    return _normaliza(_fundido(boom + ruido))


SINTETIZADORES = {"whoosh": _whoosh, "pop": _pop, "latido": _latido, "riser": _riser,
                  "notificacion": _notificacion, "campana": _campana, "impacto": _impacto}

# ------------------------------------------------------------------ internet (CC0 / Dominio Público)
# Openverse agrega Freesound, ccMixter, Wikimedia…: filtrando a CC0/pdm no hay derechos ni atribución.
UA = {"User-Agent": "ShortsLocal/1.0 (uso personal)"}
BUSQUEDAS = {
    "whoosh": ["whoosh transition", "swoosh", "whoosh"],
    "pop": ["bubble pop", "pop short", "ui pop"],
    "latido": ["heartbeat", "heart beat slow", "heartbeat single"],
    "riser": ["riser", "tension riser", "build up whoosh"],
    "notificacion": ["notification ding", "message alert", "phone notification"],
    "campana": ["bell ding", "small bell", "chime"],
    "impacto": ["impact hit", "cinematic impact", "deep impact boom"],
}
NO_UTIL = re.compile(r"music|song|loop|beat\b|melod|ambien|album|vocal|sing|speech|podcast|"
                     r"rain|wind|thunder|bird|car|dog|cat|footstep|applause|cheer|crowd", re.I)
EXT = (".mp3", ".wav", ".ogg", ".flac", ".m4a")
_AVISO_WEB = False          # para no repetir el mismo aviso en cada tipo


def _get(url, params=None, timeout=25, binario=False):
    """GET con requests si está, y si no con urllib (el módulo no puede depender de requests)."""
    try:
        import requests
        r = requests.get(url, headers=UA, timeout=timeout, params=params)
        return r.content if binario else r.json()
    except ImportError:
        import urllib.parse, urllib.request
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as f:
            datos = f.read()
        return datos if binario else json.loads(datos.decode("utf-8", "replace"))


def _decodifica(path):
    """Lee cualquier audio con ffmpeg → mono float32 a SR. Devuelve None si ffmpeg falla."""
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "pipe:1"], capture_output=True)
    if p.returncode != 0 or not p.stdout:
        return None
    a = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    if len(a) < SR * 0.05:
        return None
    return _normaliza(_fundido(a))


def _recorta(a, dur_max):
    """Recorta al tramo con más energía y limita la duración (los archivos web vienen largos)."""
    a = np.asarray(a, np.float64)
    lim = int(dur_max * SR)
    if len(a) > lim:
        k = int(0.05 * SR)
        e = np.convolve(np.abs(a), np.ones(k) / k, mode="same")
        i = int(np.argmax(e[:max(len(e) - lim, 1)]))
        a = a[i:i + lim]
    return _normaliza(_fundido(a))


def _descargar(tipo, semilla, cache_dir, dur_max):
    """Busca en Openverse (solo CC0/pdm), prueba hasta 3 candidatos y cachea el primero que suene.
    Devuelve (ruta, meta) o (None, None). Nunca lanza: cualquier fallo cae a la síntesis.
    La API limita las peticiones anónimas (429/401): se espacian y se avisa una sola vez por render."""
    global _AVISO_WEB
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    rnd = random.Random(semilla)
    consultas = list(BUSQUEDAS.get(tipo, [tipo])); rnd.shuffle(consultas)
    for i, q in enumerate(consultas[:3]):
        if i:
            time.sleep(1.2)                              # sin prisa: no hay que tumbar Openverse
        r = None
        for intento in (0, 1):                           # 429/401 suelen ser transitorios: un reintento
            try:
                r = _get("https://api.openverse.org/v1/audio/", dict(
                    q=q, license="cc0,pdm", page_size=30, mature="false"), timeout=25)
                break
            except Exception as e:
                if intento == 0:
                    time.sleep(2.5); continue
                if not _AVISO_WEB:
                    _AVISO_WEB = True
                    print(_consola(f"   sfx: (Openverse no respondio: {e}; sintetizo los efectos)"))
                return None, None
        cand = [x for x in (r.get("results") or [])
                if x.get("url") and 200 <= (x.get("duration") or 0) <= 20000
                and not NO_UTIL.search(f"{x.get('title', '')} " + " ".join(t.get("name", "") for t in (x.get("tags") or [])))]
        rnd.shuffle(cand)
        for x in cand[:3]:
            ext = (x.get("filetype") or Path(x["url"]).suffix.strip(".") or "mp3")[:4].lower()
            if "." + ext not in EXT:
                ext = "mp3"
            f = Path(cache_dir) / f"sfx_{tipo}.{ext}"
            try:
                if not f.exists():
                    f.write_bytes(_get(x["url"], timeout=60, binario=True))
                a = _decodifica(f)
                if a is None:
                    raise ValueError("ffmpeg no pudo decodificar")
                _recorta(a, dur_max)                       # solo comprobamos que sirve
                meta = dict(titulo=x.get("title") or "sin título", autor=x.get("creator") or "desconocido",
                            licencia={"cc0": "CC0", "pdm": "Dominio Público"}.get(x.get("license"), x.get("license")),
                            fuente=f"Openverse/{x.get('source', '')}", url=x["url"])
                (Path(cache_dir) / f"sfx_{tipo}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                return f, meta
            except Exception:
                try:
                    f.unlink()
                except OSError:
                    pass
                continue
    return None, None


def _cacheado(tipo, cache_dir):
    """Primer archivo cacheado para ese tipo (nombre estable sfx_<tipo>.<ext>)."""
    if not cache_dir:
        return None
    d = Path(cache_dir)
    for f in sorted(d.glob(f"sfx_{tipo}.*")):
        if f.suffix.lower() in EXT and f.is_file():
            return f
    return None


def _meta(tipo, cache_dir):
    f = Path(cache_dir) / f"sfx_{tipo}.json"
    if f.is_file():
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            return f"«{m.get('titulo', '?')}» de {m.get('autor', '?')} ({m.get('licencia', '?')}, {m.get('fuente', '?')})"
        except Exception:
            pass
    return None


def _fuente(tipo, cache_dir, web, semilla):
    """Devuelve (onda float32, origen legible) para un tipo, cacheando lo que se descarga."""
    cache_dir = Path(cache_dir) if cache_dir else None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
    dur_max = DUR_MAX.get(tipo, 1.0)

    f = _cacheado(tipo, cache_dir)
    if f is not None:
        try:
            a = _decodifica(f)
            if a is not None:
                info = _meta(tipo, cache_dir)
                return _recorta(a, dur_max), f"cache {f.name}" + (f" ({info})" if info else "")
        except Exception:
            pass                                    # caché ilegible: seguimos por la vía web/síntesis

    if web and cache_dir:
        try:
            f, meta = _descargar(tipo, semilla, cache_dir, dur_max)
            if f is not None:
                a = _decodifica(f)
                if a is not None:
                    return _recorta(a, dur_max), (f"descargado de {meta['fuente']}: {meta['titulo']} "
                                                  f"de {meta['autor']} ({meta['licencia']})")
        except Exception as e:
            if not _AVISO_WEB:
                _AVISO_WEB = True
                print(_consola(f"   sfx: (descarga de {tipo} fallo: {e}; sintetizo)"))

    gen = SINTETIZADORES.get(tipo, _pop)
    return _recorta(gen(semilla=semilla), dur_max), "sintetizado con numpy"


def pista(n, eventos, cache_dir=None, web=True, semilla=0):
    """Pista de SFX de longitud n a SR. Devuelve (track float32, descripciones legibles).

    Para cada tipo: caché → descarga libre (Openverse CC0/pdm) → síntesis numpy.
    El pico de cada efecto se queda en 0.05-0.35 de amplitud tras multiplicar por `vol`."""
    n = int(max(n, 0))
    trk = np.zeros(n, np.float32)
    desc = []
    if n == 0 or not eventos:
        return trk, desc
    cache = {}
    for e in sorted(eventos, key=lambda x: x.get("t", 0.0)):
        tipo = e.get("tipo", "pop")
        if tipo not in cache:
            cache[tipo] = _fuente(tipo, cache_dir, web, semilla)
        onda, origen = cache[tipo]
        vol = float(e.get("vol", VOL.get(tipo, 0.15)))
        i = int(max(float(e.get("t", 0.0)), 0.0) * SR)
        if i >= n:
            continue
        j = min(n, i + len(onda))
        trk[i:j] += onda[: j - i] * vol
        desc.append(f"{tipo} en {e.get('t', 0.0):.2f}s (vol {vol:.2f}, {e.get('motivo', '')}) -> {origen}")
    return trk.astype(np.float32), desc


def mezclar(mix, eventos, cache_dir=None, web=True):
    """Suma la pista de SFX sobre `mix` sin salirse de su longitud. Tolerante a longitudes distintas."""
    mix = np.asarray(mix, np.float32)
    trk, desc = pista(len(mix), eventos, cache_dir=cache_dir, web=web)
    if len(trk) < len(mix):
        trk = np.pad(trk, (0, len(mix) - len(trk)))
    return (mix + trk[:len(mix)]).astype(np.float32), desc


# ------------------------------------------------------------------ prueba de humo
if __name__ == "__main__":
    import tempfile
    cfg = {"escenas": [
        {"texto": "Ella pensaba que todo iba bien en su casa.", "pausa": 0.35, "imagen": 0,
         "animo": "calido", "perfil_voz": "narradora"},
        {"texto": "Pero un mensaje de su hermana lo cambió todo.", "pausa": 0.35, "imagen": 1,
         "animo": "tenso", "perfil_voz": "narradora"},
        {"texto": "Resulta que el diagnóstico era cáncer y nadie se lo dijo.", "pausa": 0.35,
         "imagen": 2, "animo": "triste", "perfil_voz": "narradora"},
        {"texto": "Entonces ella lo acusó delante de toda la familia. ¡Fue brutal!", "pausa": 0.35,
         "imagen": 3, "animo": "enfadado", "perfil_voz": "narradora"},
        {"texto": "Yo creo que ella tuvo razón, pero se pasó de dura.", "pausa": 1.6, "imagen": 4,
         "animo": "neutro", "perfil_voz": "energetica", "tipo": "opinion"},
        {"texto": "¿Tú qué habrías hecho en su lugar?", "pausa": 0.35, "imagen": 5,
         "animo": "neutro", "perfil_voz": "narradora"},
    ]}
    dur = [3.2, 3.4, 4.0, 4.2, 4.5, 2.8]
    seg_times, t = [], 0.4
    for d in dur:
        seg_times.append((t, t + d)); t += d + 0.35
    spans = [(0, 0.0, 4.0), (1, 4.0, 8.0), (2, 8.0, 12.5), (2, 12.5, 17.2), (3, 17.2, 22.5), (4, 22.5, t + 1)]
    subs = [[a + 0.1, b - 0.2, [[("palabra", i == 0) for i in range(4)]], [a + 0.2 * i for i in range(4)]]
            for a, b in seg_times]
    poll_start = seg_times[4][0]

    ev = momentos(cfg, subs, spans, seg_times, poll_start)
    tipos = {}
    for e in ev:
        tipos[e["tipo"]] = tipos.get(e["tipo"], 0) + 1
    print(f"   sfx: {len(ev)} momentos -> " + ", ".join(f"{k}x{v}" for k, v in sorted(tipos.items())))
    for e in ev:
        print(_consola(f"   sfx:   {e['t']:6.2f}s  {e['tipo']:<13} vol {e['vol']:.2f}  {e['motivo']}"))

    n = int(t * SR)
    trk, desc = pista(n, ev, cache_dir=Path(tempfile.gettempdir()) / "sfx_cache", web=True, semilla=7)
    for d in desc:
        print(_consola(f"   sfx: {d}"))
    mix, _ = mezclar(np.zeros(n, np.float32), ev, cache_dir=Path(tempfile.gettempdir()) / "sfx_cache")
    salida = Path(tempfile.gettempdir()) / "sfx_prueba.wav"
    try:
        import soundfile as sf
        sf.write(salida, trk, SR)
    except ImportError:                                  # runtime sin soundfile: WAV a mano (stdlib)
        import wave
        pcm = (np.clip(trk, -1, 1) * 32767).astype("<i2")
        with wave.open(str(salida), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    finito = bool(np.isfinite(trk).all())
    pico = float(np.abs(trk).max()) if len(trk) else 0.0
    print(f"   sfx: pista {len(trk)} muestras ({len(trk) / SR:.2f}s), pico {pico:.3f}, "
          f"finito {finito}, mezcla finita {bool(np.isfinite(mix).all())}")
    print(f"   sfx: WAV de prueba en {salida}")
