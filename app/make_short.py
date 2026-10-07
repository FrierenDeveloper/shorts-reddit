"""
Genera un YouTube Short 9:16 a partir de historias/<nombre>.json

Uso:  python make_short.py historias/mi_historia.json
Salida: salida/Reddit/ o salida/Salud_Mental/ + video, créditos y descripción
"""
import asyncio, json, multiprocessing as mp, os, re, subprocess, sys, tempfile, time
from pathlib import Path
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Al ejecutarse como script este módulo es "__main__". Otros módulos (extras, gpu_render)
# hacen "import make_short": sin esto cargarían una SEGUNDA copia con su propia TPL/FONT
# vacía y el render perdería la plantilla elegida (tarjeta, colores, tipografía).
# Registramos este módulo como "make_short" para que todos compartan la misma instancia.
if __name__ in ("__main__", "__mp_main__"):
    sys.modules.setdefault("make_short", sys.modules[__name__])

# Los mensajes contienen emojis y flechas; evita que la página final del CLI falle
# al escribirlos desde una consola Windows configurada con cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).resolve().parent          # código, fuentes, modelos
ROOT = APP.parent                                # carpeta del proyecto
CONFIG = ROOT / "config"
CACHE = ROOT / "cache"
W, H, FPS, SR = 1080, 1920, 30, 24000
FONT = ImageFont.truetype(str(APP / "fonts" / "Poppins-Bold.ttf"), 76)
FONT_SMALL = ImageFont.truetype(str(APP / "fonts" / "Poppins-Bold.ttf"), 34)
HL = (255, 206, 84)
MAXW = 900
TPL = {}

def set_template(nombre):
    """Aplica una plantilla de plantillas.py (tipografía, colores, ritmo, paleta…)."""
    global FONT, HL, MAXW, PAL, TPL
    import plantillas
    TPL = dict(plantillas.PLANTILLAS[nombre], nombre=nombre)
    FONT = ImageFont.truetype(str(APP / "fonts" / TPL["fuente"]), TPL["tam"])
    HL, MAXW, PAL = TPL["resalte"], TPL["maxw"], TPL["pal"]
UA = {"User-Agent": "ShortsRedditLocal/1.0 (uso personal)"}

# ------------------------------------------------------------------ voz
async def _edge(text, voice, rate, pitch):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return bytes(audio), words

def decode(mp3_bytes):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"],
                       input=mp3_bytes, capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).copy()

def cuda_ok():
    try:
        import torch
        if os.name == "nt":  # DLLs de CUDA/cuDNN que trae PyTorch, para faster-whisper y onnxruntime
            os.add_dll_directory(str(Path(torch.__file__).parent / "lib"))
        return torch.cuda.is_available()
    except Exception:
        return False

_WHISPER = None
def whisper_words(audio):
    """Tiempos por palabra con faster-whisper (GPU si hay CUDA)."""
    global _WHISPER
    gpu = cuda_ok()
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        try:
            _WHISPER = WhisperModel("small", device="cuda" if gpu else "cpu", compute_type="float16" if gpu else "int8")
        except Exception:
            _WHISPER = WhisperModel("small", device="cpu", compute_type="int8")
    a16 = np.interp(np.arange(0, len(audio), SR / 16000), np.arange(len(audio)), audio).astype(np.float32)
    segs, _ = _WHISPER.transcribe(a16, language="es", word_timestamps=True)
    return [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]

# --- motores de voz
_EDGE = {}   # (texto, voz, velocidad, tono) -> (audio, palabras), llenado por edge_lote

def edge_lote(cfg, voz_op):
    """Genera TODAS las frases del video con edge-tts en paralelo (en vez de una por una)."""
    rate, pitch = cfg.get("velocidad", "+6%"), cfg.get("tono", "+0Hz")
    pend = []
    for s in cfg["escenas"]:
        if s.get("audio"):
            continue
        text = (s.get("hablado") or "").strip() or s["texto"].replace("*", "")
        voice = voz_op if s.get("tipo") == "opinion" else cfg.get("voz", "es-MX-DaliaNeural")
        if (text, voice, rate, pitch) not in _EDGE:
            pend.append((text, voice))
    if not pend:
        return
    async def run():
        sem = asyncio.Semaphore(6)
        async def one(t, v):
            async with sem:
                return await _edge(t, v, rate, pitch)
        return await asyncio.gather(*[one(t, v) for t, v in pend])
    for intento in range(3):
        try:
            res = asyncio.run(run())
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(6) as ex:          # decodificar mp3 también en paralelo
                auds = list(ex.map(lambda r: decode(r[0]), res))
            for (t, v), a, (_, words) in zip(pend, auds, res):
                _EDGE[(t, v, rate, pitch)] = (a, words)
            print(f"   edge-tts: {len(pend)} frases en paralelo")
            return
        except Exception as e:
            print("  edge-tts falló, reintentando:", e); time.sleep(2)
    raise SystemExit("No se pudo generar la voz con edge-tts (¿sin internet?). Prueba \"motor_voz\": \"kokoro\".")

def _voice_edge(text, cfg):
    k = (text, cfg.get("voz", "es-MX-DaliaNeural"), cfg.get("velocidad", "+6%"), cfg.get("tono", "+0Hz"))
    if k in _EDGE:
        a, w = _EDGE[k]; return a.copy(), list(w)
    for intento in range(3):
        try:
            mp3, words = asyncio.run(_edge(text, cfg.get("voz", "es-MX-DaliaNeural"),
                                           cfg.get("velocidad", "+6%"), cfg.get("tono", "+0Hz")))
            return decode(mp3), words
        except Exception as e:
            print("  edge-tts falló, reintentando:", e); time.sleep(2)
    raise SystemExit("No se pudo generar la voz con edge-tts (¿sin internet?). Prueba \"motor_voz\": \"kokoro\".")

_KOKORO = None
def _voice_kokoro(text, cfg):
    """Local (Apache 2.0, uso comercial OK). GPU con onnxruntime-gpu."""
    global _KOKORO
    from kokoro_onnx import Kokoro
    if _KOKORO is None:
        mdir = APP / "modelos"
        cuda_ok()
        try:
            import onnxruntime as ort
            prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
            sess = ort.InferenceSession(str(mdir / "kokoro-v1.0.onnx"), providers=prov)
            _KOKORO = Kokoro.from_session(sess, str(mdir / "voices-v1.0.bin"))
        except Exception:
            _KOKORO = Kokoro(str(mdir / "kokoro-v1.0.onnx"), str(mdir / "voices-v1.0.bin"))
    sp = 1 + float(str(cfg.get("velocidad", "+0%")).strip("%")) / 100
    a, sr = _KOKORO.create(text, voice=cfg.get("voz_local", "ef_dora"), speed=sp, lang="es")
    return a.astype(np.float32), []

_XTTS = None
def _voice_xtts(text, cfg):
    """Local en GPU con clonación de voz. Licencia Coqui CPML: NO permite uso comercial (canal monetizado)."""
    global _XTTS
    if _XTTS is None:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        from TTS.api import TTS
        _XTTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda" if cuda_ok() else "cpu")
    ref = cfg.get("voz_referencia")
    kw = {"speaker_wav": str(ROOT / ref)} if ref else {"speaker": cfg.get("voz_local", "Ana Florence")}
    a = np.array(_XTTS.tts(text=text, language="es", **kw), np.float32)
    return a, []   # XTTS entrega 24 kHz

_CB = {}
TEMPORALES = []   # carpetas/archivos temporales de esta corrida

class DuracionFueraDeRango(ValueError):
    def __init__(self, segundos):
        self.segundos = segundos
        super().__init__(f"El guion quedó en {segundos:.1f}s; el rango permitido es 60–70s.")

def limpiar_corrida():
    """Borra lo descargado y lo temporal de este video (buena práctica: no acumular basura)."""
    import shutil
    if os.getenv("SHORTS_MANTENER_CACHE") == "1":
        return
    n = 0
    for f in set(DESCARGAS) | set(TEMPORALES):
        try:
            if Path(f).is_dir(): shutil.rmtree(f)
            elif Path(f).exists(): Path(f).unlink()
            n += 1
        except OSError:
            pass
    DESCARGAS.clear(); TEMPORALES.clear()
    print(f"   limpieza: {n} archivos temporales borrados")
def _voice_chatterbox(text, cfg):
    """Chatterbox: el audio ya se generó en lote (ver chatterbox_lote); aquí solo se lee."""
    f = _CB.get((text, cfg.get("voz")))
    if not f or not Path(f).exists():
        raise SystemExit(f"Chatterbox no generó audio para: {text[:40]}…")
    return decode(Path(f).read_bytes()), []

_CB_PROC = None

def _cb_stop():
    global _CB_PROC
    if _CB_PROC is not None and _CB_PROC.poll() is None:
        try: _CB_PROC.stdin.close()
        except Exception: pass
        try: _CB_PROC.wait(timeout=10)
        except Exception: _CB_PROC.kill()
    _CB_PROC = None

import atexit
atexit.register(_cb_stop)

def _cb_worker():
    """Proceso persistente de Chatterbox: carga el modelo UNA vez y atiende todos los videos del lote."""
    global _CB_PROC
    if _CB_PROC is not None and _CB_PROC.poll() is None:
        return _CB_PROC
    py = ROOT / ".venv_cb" / "Scripts" / "python.exe"
    if not py.exists():
        py = ROOT / ".venv_cb" / "bin" / "python"
    if not py.exists():
        raise SystemExit("Chatterbox no está instalado: ejecuta INSTALAR_CHATTERBOX.bat")
    env = dict(os.environ, PYTHONWARNINGS="ignore", TRANSFORMERS_VERBOSITY="error", PYTHONIOENCODING="utf-8")
    _CB_PROC = subprocess.Popen([str(py), "-u", str(APP / "tts_chatterbox.py"), "--serve"], cwd=ROOT, env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    while True:
        line = _CB_PROC.stdout.readline()
        if not line:
            _CB_PROC = None
            raise SystemExit("Chatterbox no arrancó (revisa el error de arriba).")
        if line.strip() == "READY":
            return _CB_PROC
        if line.strip():
            print(" ", line.rstrip())

def chatterbox_lote(cfg, voz_op):
    """Genera TODAS las voces del video en el proceso persistente."""
    tmp = Path(tempfile.mkdtemp(prefix="cb_")); TEMPORALES.append(tmp)
    ref_n = cfg.get("voz_referencia") or ("voces/narrador.wav" if (ROOT / "voces/narrador.wav").exists() else None)
    ref_o = cfg.get("voz_referencia_opinion") or ("voces/opinion.wav" if (ROOT / "voces/opinion.wav").exists() else None)
    emo = {"calido": 0.45, "neutro": 0.5, "frio": 0.62}
    items = []
    for k, s in enumerate(cfg["escenas"]):
        if s.get("audio"):
            continue
        text = (s.get("hablado") or "").strip() or s["texto"].replace("*", "")
        op = s.get("tipo") == "opinion"
        ref = ref_o if op else ref_n
        out = tmp / f"{k:02d}.wav"
        items.append(dict(text=text, out=str(out), ref=str(ROOT / ref) if ref else None,
                          exaggeration=0.4 if op else emo.get(s.get("animo"), 0.5), cfg_weight=0.5))
        _CB[(text, voz_op if op else cfg.get("voz"))] = str(out)
    print(f"   Chatterbox: {len(items)} frases (narrador: {ref_n or 'voz por defecto'}, opinión: {ref_o or 'voz por defecto'})")
    job = json.dumps(dict(lang=cfg.get("idioma", "es"), items=items), ensure_ascii=False)
    for intento in range(2):
        proc = _cb_worker()
        try:
            proc.stdin.write(job + "\n"); proc.stdin.flush()
            while True:
                resp = proc.stdout.readline()
                if not resp:
                    break
                if resp.startswith("{"):
                    r = json.loads(resp)
                    if r.get("ok"):
                        return
                    print("   Chatterbox:", r.get("error")); break
                print(" ", resp.rstrip())        # progreso "voz 3/14"
        except Exception as e:
            print("   Chatterbox:", e)
        _cb_stop()
    raise SystemExit("Chatterbox falló al generar la voz.")

MOTORES = {"chatterbox": _voice_chatterbox, "edge": _voice_edge, "kokoro": _voice_kokoro,
           "xtts": _voice_xtts}

def motor_actual(cfg):
    return os.getenv("SHORTS_MOTOR_VOZ") or cfg.get("motor_voz", "edge")

def tts(text, cfg, palabras=True):
    motor = motor_actual(cfg)
    a, words = MOTORES[motor](text, cfg)
    idx = np.where(np.abs(a) > 0.01)[0]
    if len(idx) == 0:
        return a, words
    cut0 = max(idx[0] - 600, 0)
    a = a[cut0: idx[-1] + 1200]
    off = cut0 / SR
    words = [(s - off, e - off, w) for s, e, w in words]
    if not words and palabras:
        words = whisper_words(a)
    return a, words

# ------------------------------------------------------------------ imágenes
# Fuentes libres de derechos (sin copyright o con licencia de uso libre, también comercial):
#   pexels    → Licencia Pexels (uso libre y comercial, sin atribución obligatoria). Requiere clave gratis.
#   pixabay   → Licencia de contenido Pixabay (uso libre y comercial).          Requiere clave gratis.
#   openverse → solo CC0 y Dominio Público (sin copyright). Sin clave.
#   wikimedia → solo CC0 y Dominio Público. Sin clave.
MIN_W, MIN_H = 1080, 1350     # calidad mínima aceptada
PESO_FOTO = float(os.getenv("SHORTS_PESO_FOTO", "1.0"))
                              # peso de la FOTO en el tinte del fondo. Estaba en 0.7 (efectivo
                              # 0.294): medido sobre el render, la luminancia media del video caia
                              # a 31-51/255 y el Ken Burns no se veia. Con 1.0 sube a ~65-119.
                              # Ajustable SIN tocar codigo para calibrar el look de cada plantilla:
                              #   $env:SHORTS_PESO_FOTO="0.85"  -> mas oscuro y dramatico
                              #   $env:SHORTS_PESO_FOTO="1.15"  -> mas claro
                              # OJO: gpu_render.py:124 usa esta misma constante, asi que la ruta
                              # GPU queda sincronizada sola.
CALIDAD_LUM_MIN = float(os.getenv("SHORTS_LUM_MIN", "20"))        # luminancia media minima de una foto
CALIDAD_VERDE_MAX = float(os.getenv("SHORTS_VERDE_MAX", "0.025")) # fraccion de croma verde tolerada


def calidad_ok(im):
    """Descarta fotos inservibles ANTES de que CLIP las puntue (devuelve (bool, motivo)).

    El caso real que motivó esto: la foto elegida para el plano final tenia la pantalla de un
    movil en VERDE CROMA vacio (medido (6,60,10) ya teñido, ~(0,177,64) en el original) durante
    11.33 s del video. CLIP puntua similitud semantica texto-imagen, no calidad visual, asi que
    "hand holding phone" ganaba aunque la pantalla estuviera vacia. Aqui se filtra por:
      - croma verde de pantalla: verde muy dominante y plano (no descarta vegetacion: exige
        g > r*1.6 y g > b*1.6, que un prado normal no cumple),
      - imagenes casi negras (luminancia media por debajo de CALIDAD_LUM_MIN).
    Umbrales configurables por SHORTS_LUM_MIN y SHORTS_VERDE_MAX."""
    a = np.asarray(im.convert("RGB"), np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    verde = (g > 90) & (g > r * 1.6) & (g > b * 1.6)
    if verde.mean() > CALIDAD_VERDE_MAX:
        return False, f"croma verde en {verde.mean() * 100:.1f}% del area"
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum.mean() < CALIDAD_LUM_MIN:
        return False, f"casi negra (luminancia media {lum.mean():.0f})"
    return True, ""


def _ahash(im, lado=8):
    """Hash perceptual (aHash) de una foto: 64 bits, para detectar imágenes CASI IGUALES.

    Motivo: en el render con b-roll por tramo salieron tres mesas de comedor seguidas
    (búsquedas "dinner table ..." distintas) que se veían como un ÚNICO plano de 13 s, aunque
    el contador de cortes dijera otra cosa. El plan de broll elige por TEXTO, no por lo que ya
    se ha mostrado, así que la variedad real era menor que la nominal."""
    g = np.asarray(im.convert("L").resize((lado, lado), Image.BILINEAR), np.float32)
    return (g > g.mean()).flatten()


def _hamming(a, b):
    """Distancia de Hamming entre dos aHash (0 = idénticas, 64 = opuestas). <=6 = casi iguales."""
    return int((a != b).sum())

def _claves():
    k = {}
    f = CONFIG / "claves.json"
    if f.exists():
        k.update(json.loads(f.read_text(encoding="utf-8")))
    k.setdefault("pexels", os.getenv("PEXELS_API_KEY", ""))
    k.setdefault("pixabay", os.getenv("PIXABAY_API_KEY", ""))
    return k

def _score(w, h):
    """Prefiere fotos verticales y grandes."""
    return (2.0 if h >= w else 1.0) * min(w * h / (1080 * 1920), 3)

def src_pexels(q, key, relajado=False):
    r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key, **UA}, timeout=30,
                     params=dict(query=q, per_page=30, orientation="portrait", size="large")).json()
    return [dict(url=p["src"]["original"] + "?auto=compress&cs=tinysrgb&h=2400", thumb=p["src"].get("medium"),
                 w=p["width"], h=p["height"],
                 id=f"pexels_{p['id']}", title=p.get("alt") or q, artist=p["photographer"],
                 license="Licencia Pexels", page=p["url"], fuente="Pexels") for p in r.get("photos", [])]

def src_pixabay(q, key, relajado=False):
    r = requests.get("https://pixabay.com/api/", headers=UA, timeout=30, params=dict(
        key=key, q=q, image_type="photo", orientation="vertical", per_page=30, safesearch="true",
        min_width=MIN_W, min_height=MIN_H)).json()
    return [dict(url=p.get("largeImageURL"), thumb=p.get("webformatURL"), w=p["imageWidth"], h=p["imageHeight"], id=f"pixabay_{p['id']}",
                 title=p.get("tags", q), artist=p.get("user", ""), license="Licencia Pixabay",
                 page=p["pageURL"], fuente="Pixabay") for p in r.get("hits", [])]

def src_openverse(q, key=None, relajado=False):
    # page_size estaba en 30, y la API ANONIMA de Openverse limita a 20: respondia
    # {"detail":"page_size may not exceed 20 for anonymous requests"} SIN campo "results",
    # asi que esta fuente devolvia [] SIEMPRE (se veia como "openverse no respondio" en el
    # render). Hallazgo de la auditoria; con 20 devuelve resultados reales.
    r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=30, params=dict(
        q=q, license="cc0,pdm,by,by-sa" if relajado else "cc0,pdm", category="photograph",
        size="medium,large" if relajado else "large", page_size=20, mature="false",
        excluded_source="rawpixel,wikimedia,smithsonian_national_museum_of_natural_history,brooklynmuseum,met,clevelandmuseum,europeana,rijksmuseum,nappy_ssl_bypass")).json()
    if "results" not in r:
        print(f"    (openverse: respuesta sin resultados: {str(r.get('detail') or r)[:90]})")
        return []
    return [dict(url=p["url"], thumb=p.get("thumbnail"), w=p.get("width") or 0, h=p.get("height") or 0, id=f"ov_{p['id']}",
                 title=p.get("title") or q, artist=p.get("creator") or "desconocido",
                 license={"cc0": "CC0", "pdm": "Dominio Público"}.get(p["license"], f"CC {p['license'].upper()} {p.get('license_version', '')}".strip()),
                 page=p.get("foreign_landing_url", ""), fuente=f"Openverse/{p.get('source', '')}",
                 tags=" ".join(t.get("name", "") for t in (p.get("tags") or [])))
            for p in r.get("results", [])]

def src_wikimedia(q, key=None, relajado=False):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params=dict(
        action="query", format="json", generator="search", gsrnamespace=6, gsrlimit=20,
        gsrsearch=q + " filetype:bitmap", prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=2000)).json()
    out = []
    for p in r.get("query", {}).get("pages", {}).values():
        ii = p["imageinfo"][0]; md = ii.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not re.search(r"CC0|Public domain|No restrictions" + (r"|CC BY" if relajado else ""), lic, re.I):
            continue
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "desconocido")).strip()
        out.append(dict(url=ii.get("thumburl") or ii["url"], w=ii.get("width", 0), h=ii.get("height", 0),
                        id="wm_" + str(p["pageid"]), title=p["title"].replace("File:", ""), artist=artist[:80],
                        license=lic, page=ii.get("descriptionurl", ""), fuente="Wikimedia Commons"))
    return out

FUENTES = {"pexels": src_pexels, "pixabay": src_pixabay, "openverse": src_openverse, "wikimedia": src_wikimedia}
# Fuentes adicionales de app/fuentes_extra.py (flickr_cc, stocksnap, openverse_ampliado,
# wikimedia_categorias, pexels_video, pixabay_video). Se fusionan SIN pisar las de arriba.
# Si el modulo no importa, el motor sigue funcionando con las cuatro de siempre.
FUENTES_IMAGEN = list(FUENTES)
try:
    import fuentes_extra
    FUENTES = fuentes_extra.fuentes_todas(FUENTES)
    # Solo las de IMAGEN entran en la busqueda de fotos: pexels_video y pixabay_video
    # devuelven clips y romperian get_image (que espera una Image). Se excluyen aqui.
    FUENTES_IMAGEN = [f for f in FUENTES if f not in ("pexels_video", "pixabay_video")]
except Exception as _e:
    print(f"   ⚠ fuentes_extra no disponible ({_e}); sigo con {len(FUENTES)} fuentes")

NO_FOTO = re.compile(r"diar|page|clipping|newspaper|book|engraving|etching|lithograph|plate|map|painting|drawing|"
                     r"illustration|poster|postcard|advert|catalog|archive|dpla|museum|sketch|print|manuscript|"
                     r"magazine|vintage|antique|\b1[5-9]\d\d\b", re.I)
STOP = {"with", "from", "the", "and", "for", "into", "over", "under", "near", "photo", "image", "empty", "hand", "hands",
        "a", "an", "of", "on", "in", "to", "at", "by", "or", "and"}

def _conceptos(q):
    """Palabras de contenido para validar que una búsqueda compuesta esté representada."""
    return [w.rstrip("s") for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 2 and w not in STOP]

def relevante(x, q):
    """Filtra resultados que no representen la mayoría de los conceptos de la búsqueda."""
    txt = f"{x.get('title', '')} {x.get('tags', '')}".lower()
    if x["fuente"] not in ("Pexels", "Pixabay") and NO_FOTO.search(txt):
        return False
    claves = _conceptos(q)
    if len(claves) < 2:
        return not claves or any(w in txt for w in claves)
    # Variantes de búsqueda pueden omitir palabras funcionales, pero no deberían
    # aceptar una foto que solo mencione un fragmento del objeto compuesto.
    min_matches = 2 if len(claves) <= 3 else (len(claves) + 1) // 2
    return sum(w in txt for w in claves) >= min_matches

_BUSQ_CACHE = {}   # (q, tuple(orden), relajado) -> resultados; evita repetir la misma consulta en el lote
BUENAS_SUFICIENTES = 12   # si un banco ya trae esta cantidad de fotos buenas, no seguimos consultando los demás

def buscar_imagenes(q, orden, relajado=False):
    import seguridad_menores as SM
    q = SM.sin_rostros(SM.limpiar_consulta(q))   # sin niños/bebés/adolescentes y sin pedir caras
    ckey = (q, tuple(orden), relajado)
    if ckey in _BUSQ_CACHE:
        return _BUSQ_CACHE[ckey]
    claves = _claves()
    mw, mh = (800, 800) if relajado else (MIN_W, MIN_H * 0.75)
    fuentes = [f for f in orden if not (f in ("pexels", "pixabay") and not claves.get(f))]

    def _uno(f):
        try:
            got = [x for x in FUENTES[f](q, claves.get(f), relajado)
                   if x["url"] and x["w"] >= mw and x["h"] >= mh and relevante(x, q)
                   and not SM.resultado_con_menor(x) and not SM.resultado_con_rostro(x)]
            return f, sorted(got, key=lambda x: -_score(x["w"], x["h"]))
        except Exception as e:
            print(f"    ({f} no respondió: {e})")
            return f, []

    res = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max(1, len(fuentes))) as ex:
        futs = {ex.submit(_uno, f): f for f in fuentes}
        for fut in as_completed(futs):
            _, got = fut.result()
            res += got
            if len(res) >= BUENAS_SUFICIENTES:   # ya hay de sobra: no esperamos a los bancos restantes
                for other in futs:
                    other.cancel()
                break
    _BUSQ_CACHE[ckey] = res
    return res

def _variantes(q):
    """Mantiene primero el objeto completo; relaja solo para frases de 4+ términos."""
    w = q.split()
    # Evita degradar "bag of ice" a "ice" o "bag". Consultas largas pueden
    # probar una frase central después de la búsqueda completa.
    return [q] + ([" ".join(w[1:])] if len(w) >= 4 else [])

USADAS = set()
DESCARGAS = []   # archivos bajados en esta corrida (se borran al terminar)
CANDIDATOS = int(os.getenv("SHORTS_CANDIDATOS", "20"))   # fotos que CLIP compara por cada imagen
def get_image(item, cache, orden):
    if isinstance(item, str):
        item = {"buscar": item}
    if "archivo" in item:                      # imagen local propia
        return Image.open(ROOT / item["archivo"]).convert("RGB"), None
    fuentes = item.get("fuentes", orden)
    intentos = [(v, False) for v in _variantes(item["buscar"])] + [(v, True) for v in _variantes(item["buscar"])]
    textos = [item["buscar"]] + list(item.get("alternativas", []))
    mejor = None                       # (puntaje, imagen, meta) entre todos los intentos
    orden_busq = intentos[:1] + [(a, False) for a in textos[1:]] + intentos[1:] + [(a, True) for a in textos[1:]]
    MAX_RONDAS = int(os.getenv("SHORTS_MAX_RONDAS", "3"))
    rondas = 0
    for q, relajado in orden_busq:
        if rondas >= MAX_RONDAS:
            break
        res = [x for x in buscar_imagenes(q, fuentes, relajado) if x["id"] not in USADAS]
        # Calidad mínima por METADATOS, antes de descargar nada. Si el filtro dejase menos de
        # 3 candidatos se ignora: mejor una foto justa de resolución que quedarse sin ninguna.
        grandes = [x for x in res if (x.get("w") or 0) >= MIN_W and (x.get("h") or 0) >= MIN_H]
        if len(grandes) >= 3:
            res = grandes
        if not res:
            continue
        rondas += 1
        if (q, relajado) != intentos[0]:
            print(f"    → probando búsqueda '{q}'" + (" (calidad/licencia ampliada, con crédito)" if relajado else ""))
        tdir = cache / "miniaturas"; tdir.mkdir(exist_ok=True)
        def _bajar(pick):
            fn = tdir / (pick["id"] + ".jpg")          # CLIP compara miniaturas (rápido y liviano)
            try:
                if not fn.exists():
                    fn.write_bytes(requests.get(pick.get("thumb") or pick["url"], headers=UA, timeout=60).content)
                DESCARGAS.append(fn)
                im = Image.open(fn).convert("RGB"); im.thumbnail((448, 448))
                ok, motivo = calidad_ok(im)             # descarta croma verde y fotos casi negras
                if not ok:
                    print(f"    ✗ descartada {pick['id']}: {motivo}")
                    return None
                return im, pick
            except Exception:
                return None
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as ex:      # descarga las ~20 miniaturas en paralelo
            cands = [c for c in ex.map(_bajar, (res[item.get("opcion", 0):] or res)[:CANDIDATOS]) if c]
        if not cands:
            continue
        import clip_rank
        # SEGURIDAD: se descartan las fotos que muestren un menor aunque los metadatos no lo digan.
        _fl = clip_rank.contiene_menor([c[0] for c in cands])
        if _fl:
            _n0 = len(cands)
            cands = [c for c, f in zip(cands, _fl) if not f]
            if len(cands) < _n0:
                print(f"    seguridad: {_n0 - len(cands)} foto(s) descartadas por posibles menores")
            if not cands:
                continue
        # SIN ROSTROS: se descartan las fotos con una cara visible. Si TODAS las candidatas la
        # tienen, se queda la de menor probabilidad de rostro (mejor una foto discreta que ninguna).
        _pr = clip_rank.prob_rostro([c[0] for c in cands])
        if _pr:
            _sin = [c for c, v in zip(cands, _pr) if v < clip_rank.UMBRAL_ROSTRO]
            if len(_sin) < len(cands):
                print(f"    sin rostros: {len(cands) - len(_sin)} foto(s) con cara descartadas")
            if _sin:
                cands = _sin
            else:
                _k = min(range(len(cands)), key=lambda i: _pr[i])
                if _pr[_k] >= 0.75:          # todas son retratos claros: probar otra búsqueda
                    continue
                cands = [cands[_k]]
        # Puntuar primero el concepto completo. Las alternativas solo desempatan,
        # sin permitir que una coincidencia parcial supere una buena coincidencia.
        pts = clip_rank.puntuar([c[0] for c in cands], [item["buscar"]])
        if pts is not None and len(textos) > 1:
            alt_pts = clip_rank.puntuar([c[0] for c in cands], textos[1:])
            if alt_pts is not None:
                pts = [base * 0.8 + alt * 0.2 for base, alt in zip(pts, alt_pts)]
        if pts is None:                # sin CLIP: el primer resultado, como antes
            pts = [1.0] + [0.0] * (len(cands) - 1)
        k = max(range(len(cands)), key=lambda i: pts[i])
        if len(cands) > 1 and pts[k] < 1.0:
            print(f"    CLIP eligió 1 de {len(cands)} (similitud {pts[k]:.2f})")
        if mejor is None or pts[k] > mejor[0]:
            mejor = (pts[k], *cands[k])
        if pts[k] >= clip_rank.UMBRAL:
            break
    if mejor:
        if mejor[0] < __import__("clip_rank").UMBRAL:
            print(f"    ⚠ Ninguna foto calza del todo con '{item['buscar']}'; se usa la más parecida ({mejor[0]:.2f})")
        pick = mejor[2]
        fn = cache / (pick["id"] + ".jpg")
        try:
            if not fn.exists():
                fn.write_bytes(requests.get(pick["url"], headers=UA, timeout=90).content)
            DESCARGAS.append(fn)
            im = Image.open(fn).convert("RGB")
            # La miniatura es pequeña y puede enganar: se revalida la version grande antes
            # de marcarla como usada. Si no pasa el filtro, se devuelve None y get_image
            # reintenta con otra busqueda en vez de colar una foto inservible.
            ok, motivo = calidad_ok(im)
            if not ok:
                print(f"    ✗ descartada la versión grande de {pick['id']}: {motivo}")
                return None, None
            USADAS.add(pick["id"]); return im, pick
        except Exception as e:
            print(f"    (no se pudo bajar la versión grande: {e})")
    print(f"    ⚠ Sin imagen para '{item['buscar']}': se reutiliza otra del video")
    return None, None

# ------------------------------------------------------------------ subtítulos
def tokens(text):
    if TPL.get("mayus"):
        text = text.upper()
    out = []
    for i, part in enumerate(text.split("*")):
        for w in part.split():
            if out and re.fullmatch(r"[.,:;!?…»)\]]+", w):
                out[-1] = (out[-1][0] + w, out[-1][1])   # pega la puntuación a la palabra anterior
            else:
                out.append((w, i % 2 == 1))
    return out

def width(ws):
    return FONT.getlength(" ".join(w for w, _ in ws))

def chunks(toks):
    """Bloques de 1–2 líneas; corta en fin de frase. Devuelve listas de (líneas, índice_primer_token)."""
    res, lines, line, first, i0 = [], [], [], 0, 0
    for i, tk in enumerate(toks):
        if line and width(line + [tk]) > MAXW:
            lines.append(line); line = []
            if len(lines) == 2:
                res.append((lines, first)); lines = []; first = i
        line.append(tk)
        mx = TPL.get("max_palabras") or 0
        if mx and sum(len(l) for l in lines) + len(line) >= mx and i < len(toks) - 1:
            lines.append(line); line = []
            res.append((lines, first)); lines = []; first = i + 1
            continue
        if tk[0][-1] in "?.:!…" and i < len(toks) - 1 and (lines or width(line) > 350):
            lines.append(line); line = []
            res.append((lines, first)); lines = []; first = i + 1
    if line: lines.append(line)
    if lines: res.append((lines, first))
    return res

def sub_sprite(lines):
    T = TPL or {}
    lh = T.get("lh", 104); ypos = T.get("y", 0.5)
    col, brd, gro, caja = T.get("texto", (255, 255, 255)), T.get("borde", (20, 8, 20)), T.get("grosor", 7), T.get("caja")
    layer = Image.new("RGBA", (W, H)); sh = Image.new("RGBA", (W, H))
    d, ds = ImageDraw.Draw(layer), ImageDraw.Draw(sh)
    y0 = int(H * ypos - len(lines) * lh / 2)
    for li, line in enumerate(lines):
        x = (W - width(line)) / 2; y = y0 + li * lh
        if caja:   # texto dentro de una caja redondeada
            bb = FONT.getbbox("Ág")
            box = (x - 26, y + bb[1] - 16, x + width(line) + 26, y + bb[3] + 16)
            ds.rounded_rectangle((box[0] + 6, box[1] + 10, box[2] + 6, box[3] + 10), 22, fill=(0, 0, 0, 120))
            d.rounded_rectangle(box, 22, fill=caja["color"] + (240,))
        for w, hl in line:
            if not caja:
                ds.text((x + 4, y + 8), w, font=FONT, fill=(0, 0, 0, 200))
            kw = dict(stroke_width=gro, stroke_fill=brd + (255,)) if brd and gro else {}
            d.text((x, y), w, font=FONT, fill=(HL if hl else col) + (255,), **kw)
            x += FONT.getlength(w + " ")
    comp = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), layer)
    bb = comp.getbbox()
    return comp.crop(bb), bb

def entrada(t, a, b):
    """Animación de entrada/salida del bloque según la plantilla → (alpha, escala, desplazamiento_y)."""
    E = (TPL or {}).get("entrada", dict(dur=0.28, escala=0.86, sube=34))
    pin = ease((t - a) / E["dur"]); pout = ease((t - (b - 0.2)) / 0.2) if t > b - 0.2 else 0
    sc = E["escala"] + (1 - E["escala"]) * pin + 0.03 * pout
    return pin * (1 - pout), sc, E["sube"] * (1 - pin) - 26 * pout, pin, pout

def ease(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3

# ------------------------------------------------------------------ fondo
PAL = {
    "calido": [(110, 20, 45), (190, 80, 30), (55, 20, 70)],
    "frio":   [(40, 25, 80), (30, 60, 110), (15, 15, 45)],
    "neutro": [(80, 30, 70), (120, 60, 70), (35, 20, 60)],
}
def palette(m):
    return [np.array(c, np.float32) for c in PAL.get(m, PAL["calido"])]

class Background:
    def __init__(self, sw=216, sh=384):
        yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
        self.xx, self.yy, self.sw, self.sh = xx / sw, yy / sh, sw, sh
        self.P = np.random.default_rng(3).random((40, 4)).astype(np.float32)
    def __call__(self, t, cur):
        self.cur = cur
        xx, yy, s = self.xx, self.yy, t * 0.06
        f = np.stack([0.5 + 0.5 * np.sin(2.2 * xx + 1.3 * yy + s * 2.0),
                      0.45 + 0.45 * np.sin(-1.7 * xx + 2.6 * yy - s * 1.5 + 1.0),
                      0.4 + 0.4 * np.sin(3.0 * yy - 0.8 * xx + s * 1.1 + 2.0)]) ** 2
        f /= f.sum(0)
        img = sum(f[i][..., None] * self.cur[i] for i in range(3))
        vig = 1 - 0.55 * ((xx - 0.5) ** 2 * 1.4 + (yy - 0.5) ** 2)
        wave = 0.04 * np.exp(-((yy - 0.78 - 0.02 * np.sin(xx * 6 + t * 0.4)) ** 2) / 0.0015)
        img = img * ((0.9 + 0.1 * np.sin(t * 0.5)) * vig)[..., None] + wave[..., None] * 255
        for px, py, pv, ph in self.P:
            y = (py - t * 0.006 * (0.5 + pv)) % 1
            if 0.36 < y < 0.64: continue
            x = px + 0.015 * np.sin(t * 0.3 + ph * 6)
            img += (18 * np.exp(-(((xx - x) * self.sw) ** 2 + ((yy - y) * self.sh) ** 2) / 6))[..., None]
        return img

TAU = 1.6  # segundos que tarda la paleta en acomodarse (transición gradual)
def palette_fn(moods):
    """Paleta en función del tiempo (determinista → permite render en paralelo)."""
    starts, vals = [], []
    cur = np.array(palette(moods[0][1]))
    for i, (a, m) in enumerate(moods):
        starts.append(a); vals.append(cur.copy())
        tgt = np.array(palette(m))
        if i + 1 < len(moods):
            dt = moods[i + 1][0] - a
            cur = tgt + (cur - tgt) * np.exp(-dt / TAU)
    def at(t):
        i = max(0, np.searchsorted(starts, t, side="right") - 1)
        tgt = np.array(palette(moods[i][1]))
        c = tgt + (vals[i] - tgt) * np.exp(-max(t - starts[i], 0) / TAU)
        return list(c.astype(np.float32))
    return at

PW, PH = 1080, 1920   # fotos a resolución completa (antes 540×960)
def prep_photo(im, dinamico=False):
    factor = 1.30 if dinamico else 1.18
    sc = max(PW * factor / im.width, PH * factor / im.height)
    return im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))

def _camera_crop(iw, ih, p, a, b, t, seed=0):
    """Encuadre suave distinto por escena: push, pull, paneo horizontal o vertical."""
    pr = min(max((t - a) / max(b - a, 1e-6), 0), 1)
    u = 0.5 - 0.5 * np.cos(np.pi * pr)
    mode = (p + seed) % 4
    if mode == 0:       # push-in diagonal
        z, px, py = 1.0 + 0.18 * u, -0.48 + 0.96 * u, 0.16 * np.sin(np.pi * u)
    elif mode == 1:     # pull-out
        z, px, py = 1.18 - 0.16 * u, 0.48 - 0.96 * u, -0.14 * np.sin(np.pi * u)
    elif mode == 2:     # paneo lateral
        z, px, py = 1.06 + 0.08 * u, -0.48 + 0.96 * u, -0.24 + 0.48 * u
    else:               # desplazamiento vertical lento
        z, px, py = 1.10 + 0.07 * u, 0.24 * np.sin(np.pi * u), 0.48 - 0.96 * u
    cw, ch = PW * 1.18 / z, PH * 1.18 / z
    mx, my = max(0, iw - cw), max(0, ih - ch)
    cx, cy = iw / 2 + px * mx, ih / 2 + py * my
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)

# ------------------------------------------------------------------ música
def ambient(n):
    tt = np.arange(n) / SR
    chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7], [164.8, 207.7, 246.9]]
    m, seg = np.zeros(n), 8.0
    for i in range(int(n / SR / seg) + 1):
        env = np.clip(1 - np.abs((tt - i * seg - seg / 2) / (seg * 0.75)), 0, 1) ** 1.5
        for f in chords[i % 4]:
            for det in (0.997, 1.003):
                m += env * (0.5 * np.sin(2 * np.pi * f * det * tt) + 0.3 * np.sin(np.pi * f * det * tt))
    m *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.1 * tt)
    m = m / np.abs(m).max() * 0.07
    return m * np.minimum(1, np.minimum(tt / 2, (tt[-1] - tt) / 2.5))

def _nombre_tema(cfg):
    """Nombre CORTO del tema para la portada educativa.

    'Síndrome de Cotard: creer que ya estás muerto' -> 'Síndrome de Cotard'.
    Se corta por ':' '—' '-' o '|' y se recorta a 60 caracteres: en la portada manda el nombre
    de la patología o del sesgo, no el titular entero."""
    t = str(cfg.get("titulo") or "").strip()
    for sep in (":", " — ", " – ", " - ", "|"):
        if sep in t:
            t = t.split(sep)[0].strip()
            break
    return t[:60]


# Los formatos EDUCATIVOS llevan portada SIEMPRE, con el nombre de la patología o el sesgo.
CATEGORIAS_EDUCATIVAS = ("salud_mental", "psicologia_diaria")


# ------------------------------------------------------------------ render (procesos)
def loudnorm_params(wav, I=-14.0, TP=-1.5):
    """Cadena de audio final: compresor moderado + loudnorm de DOS pasadas (linear=true).

    Historia de este arreglo, toda medida sobre el render real:
      1) Con UNA sola pasada el integrado salía en -15.3 LUFS pidiendo I=-14 (el TP sí
         quedaba clavado en -1.5 dBFS).
      2) Pasar a dos pasadas linear sólo lo llevó a -14.5. La causa real era el CREST
         FACTOR: el audio tenía pico -1.48 y integrado -15.3, es decir 13.8 dB de cresta,
         y llegar a -14.0 con TP<=-1.5 exige 12.5 dB. No cabía: le faltaba headroom.
      3) Comprimir SUAVE antes (acompressor threshold=-20dB ratio=3:1) baja el pico sin
         bajar la voz y deja que loudnorm alcance el objetivo: medido -14.1 LUFS con
         TP -1.5. Cadenas medidas: dinamico -14.7 / 2 pasadas -14.5 / alimiter -14.5 /
         speechnorm -14.4 / ESTA -14.1.
      OJO: comprimir FUERTE (ratio 4:1 y threshold -26dB) ROMPE el resultado: medido
      -27.5 LUFS, porque loudnorm en modo linear no recupera esa reducción. No subir el ratio.
    Mide el WAV ya mezclado y devuelve la cadena lista para el -af del render.
    Si la medición falla, degrada a una pasada: nunca rompe el render."""
    pre = "acompressor=threshold=-20dB:ratio=3:attack=5:release=150"
    try:
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af",
                            f"{pre},loudnorm=I={I}:TP={TP}:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=600)
        s = r.stderr
        m = json.loads(s[s.rindex("{"):s.rindex("}") + 1])
        return pre + "," + ("loudnorm=I={}:TP={}:measured_I={}:measured_TP={}:measured_LRA={}"
                            ":measured_thresh={}:offset={}:linear=true").format(
                                I, TP, m["input_i"], m["input_tp"], m["input_lra"],
                                m["input_thresh"], m["target_offset"])
    except Exception as e:
        print(f"   ⚠ loudnorm: no se pudo medir ({e}); se aplica una sola pasada")
        return f"{pre},loudnorm=I={I}:TP={TP}"


def video_encoder():
    """NVENC si está disponible; en CPU usa x264 lento y CRF con límite VBV."""
    if os.getenv("SHORTS_CPU_ENCODER") != "1":
        test = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
                               "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
        if test.returncode == 0:
            return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr",
                    "-cq", "20", "-b:v", "0", "-maxrate", "12M", "-bufsize", "24M"], "h264_nvenc (GPU)"
    return ["-c:v", "libx264", "-preset", "slow", "-crf", "20",
            "-maxrate", "12M", "-bufsize", "24M"], "libx264 slow · CRF 20 (CPU)"

_S = {}
def _init_worker(state):
    set_template(state["plantilla"])
    _S.update(state)
    _S["photos_img"] = [Image.open(p).convert("RGB") for p in state["photos"]]
    _S["video_bg_index"] = -1
    _S["video_bg_image"] = None
    _S["bg"] = Background()
    _S["pal"] = palette_fn(state["moods"])
    ys = np.linspace(0, 1, PH)[:, None, None]
    _S["band"] = 1 - 0.35 * np.exp(-((ys - 0.5) ** 2) / 0.02)
    _S["sprites"] = {}

def _photo_at(p, a, b, t):
    im = _S["photos_img"][p]
    if _S.get("visual_dinamico"):
        box = _camera_crop(im.width, im.height, p, a, b, t, _S.get("motion_seed", 0))
    else:
        pr = min(max((t - a) / (b - a), 0), 1); z = 1 + 0.12 * pr
        cw, ch = PW * 1.12 / z, PH * 1.12 / z
        cx, cy = im.width / 2 + (pr - 0.5) * 30 * (1 if p % 2 else -1), im.height / 2
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return np.asarray(im.resize((PW, PH), Image.BICUBIC, box=box), np.float32)

def _photo_layer(t):
    spans = _S["spans"]
    # Cada escena tiene una sola foto activa. El fundido previo solapaba dos
    # fotos durante 1,4 s y producía la impresión de imágenes fantasma.
    for n, (p, a, b) in enumerate(spans):
        if a <= t < b:
            ph = _photo_at(p, a, b, t)
            dt = t - a
            if _S.get("visual_dinamico") and n and 0 <= dt < 0.14:
                pulse = (1 - dt / 0.14) ** 2
                accent = np.asarray(TPL.get("resalte", (180, 200, 255)), np.float32)
                ph = ph * (1 + 0.06 * pulse) + accent * (0.035 * pulse)
            return ph
    # Huecos entre escenas: mostrar la foto más cercana, sin acumular capas.
    p, a, b = min(spans, key=lambda span: min(abs(t - span[1]), abs(t - span[2])))
    return _photo_at(p, a, b, t)

def _karaoke(img, t, i, S):
    if not S.get("extras", {}).get("karaoke", True):
        return
    import extras as X
    lay = S.setdefault("layouts", {})
    if i not in lay:
        lay[i] = X.layout(S["subs"][i][2])
    X.karaoke(img, t, S["subs"][i], lay[i])

def _render_frame(n):
    t = n / FPS
    if _S.get("video_bg_frames"):
        idx = int(t * _S["video_bg_fps"]) % len(_S["video_bg_frames"])
        if idx != _S["video_bg_index"]:
            with Image.open(_S["video_bg_frames"][idx]) as frame:
                _S["video_bg_image"] = frame.convert("RGB").resize((W, H), Image.BILINEAR)
            _S["video_bg_index"] = idx
        # La banda oscurece el centro, que es donde van los subtitulos. Debe aplicarse aqui
        # igual que en la ruta GPU (gpu_render.py) y en la rama de fotos de mas abajo.
        # _S["band"] es un ndarray (PH,1,1) = (1920,1,1), no una imagen PIL: se multiplica.
        bg = np.asarray(_S["video_bg_image"], np.float32) * 0.78
        img = Image.fromarray(np.clip(bg * _S["band"], 0, 255).astype(np.uint8)).convert("RGBA")
    else:
        g = _S["bg"](t, _S["pal"](t))
        g = np.asarray(Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).resize((PW, PH), Image.BILINEAR), np.float32)
        ph = _photo_layer(t); lum = ph.mean(2, keepdims=True)
        # La foto entra con peso PESO_FOTO (antes 0.7 fijo => 0.294 efectivo, medido como
        # luminancia media 31-51/255 en el render final). gpu_render.py usa la misma constante.
        tint = 0.62 * g * (0.45 + 1.2 * lum / 255) + 0.42 * ph * PESO_FOTO
        img = Image.fromarray(np.clip(tint * _S["band"], 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC).convert("RGBA")
    import extras as X
    z = X.zoom_at(t, _S.get("punches", []))
    if z > 1.001:     # zoom rápido en los giros de la historia
        cw, ch = W / z, H / z
        img = img.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    for i, sub in enumerate(_S["subs"]):
        a, b, lines = sub[:3]
        if not (a <= t < b): continue
        if i not in _S["sprites"]: _S["sprites"][i] = sub_sprite(lines)
        spr, (x0, y0, x1, y1) = _S["sprites"][i]
        al, sc, dy, pin, pout = entrada(t, a, b)
        if al <= 0.01: continue
        w, h = int(spr.width * sc), int(spr.height * sc)
        sp = spr.resize((w, h), Image.BILINEAR)
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * al)))
        img.alpha_composite(sp, (int((x0 + x1) / 2 - w / 2), int((y0 + y1) / 2 + dy - h / 2)))
        _karaoke(img, t, i, _S)
    import extras as X
    X.apply(img, t, _S, _S.setdefault("xcache", {}))
    aviso = _S["aviso"]
    if aviso and t < 3.2:
        al = min(1, t / 0.3, (3.2 - t) / 0.4)
        d = ImageDraw.Draw(img); tw = FONT_SMALL.getlength(aviso)
        d.text(((W - tw) / 2, 1560), aviso, font=FONT_SMALL, fill=(255, 255, 255, int(220 * al)),
               stroke_width=3, stroke_fill=(0, 0, 0, int(200 * al)))
    return img.convert("RGB").tobytes()

# ------------------------------------------------------------------ main
def main(path):
    try:
        path = Path(path)
        max_intentos = 4
        for intento in range(1, max_intentos + 1):
            try:
                _main(path)
                return
            except DuracionFueraDeRango as e:
                limpiar_corrida()
                cfg = json.loads(path.read_text(encoding="utf-8"))
                categoria = cfg.get("categoria_video")
                if categoria not in ("reddit", "salud_mental", "psicologia_diaria"):
                    categoria = "salud_mental" if cfg.get("plantilla") == "tetrica" else "reddit"
                subdir = {"salud_mental": "Salud_Mental", "psicologia_diaria": "Psicologia_Diaria"}.get(categoria, "Reddit")
                out_dir = ROOT / "salida" / subdir
                for sufijo in (".mp4", "_descripcion.txt", "_creditos.txt", "_portada.png"):
                    (out_dir / f"{path.stem}{sufijo}").unlink(missing_ok=True)
                if intento >= max_intentos:
                    raise ValueError(f"Tras {max_intentos} intentos el video siguió fuera de 60–70s. Última duración: {e.segundos:.1f}s. Acorta o amplía el guion manualmente.") from e
                print(f"   Fuera del rango 60–70s; descartando temporales y regenerando el guion (intento {intento + 1}/{max_intentos})…")
                import guion
                guion.ajustar_duracion(path, e.segundos)
                _CB.clear(); _EDGE.clear()
    finally:
        limpiar_corrida()   # siempre, aunque el render falle

def _main(path):
    USADAS.clear(); _CB.clear(); _EDGE.clear()
    path = Path(path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    name = path.stem
    categoria = cfg.get("categoria_video")
    if categoria not in ("reddit", "salud_mental", "psicologia_diaria"):
        categoria = "salud_mental" if cfg.get("plantilla") == "tetrica" else "reddit"
    carpeta = {"salud_mental": "Salud_Mental", "psicologia_diaria": "Psicologia_Diaria"}.get(categoria, "Reddit")
    out_dir = ROOT / "salida" / carpeta
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = CACHE / "imagenes"; cache.mkdir(parents=True, exist_ok=True)
    video_bg = bool(cfg.get("fondo_satisfactorio"))

    import plantillas
    plantilla = plantillas.elegir(cfg, name)
    set_template(plantilla)
    print(f"Plantilla: {plantilla}")
    if TPL.get("velocidad"):
        cfg = {**cfg, "velocidad": TPL["velocidad"]}
    voz_op = cfg.get("voz_opinion") or ("es-MX-JorgeNeural" if "Dalia" in cfg.get("voz", "Dalia") else "es-MX-DaliaNeural")
    opinion_spans = []

    # 1) voz + tiempos
    print("1/4 Generando voz…")
    motor = motor_actual(cfg)
    if motor == "chatterbox":
        chatterbox_lote(cfg, voz_op)          # proceso persistente (modelo cargado una vez por lote)
    elif motor == "edge":
        edge_lote(cfg, voz_op)                # todas las frases en paralelo
    t = 0.4
    audio = [np.zeros(int(0.4 * SR), np.float32)]
    partes, seg_times, moods, subs = [], [], [], []
    for k, s in enumerate(cfg["escenas"]):
        spoken = (s.get("hablado") or "").strip() or s["texto"].replace("*", "")
        if s.get("audio"):                       # grabación propia (ej. tu opinión con tu voz)
            a = decode((ROOT / s["audio"]).read_bytes()); words = []
        elif s.get("tipo") == "opinion":
            a, words = tts(spoken, {**cfg, "voz": voz_op, "perfil_voz": s.get("perfil_voz") or "energetica",
                                    "animo": s.get("animo", "neutro")}, palabras=False)
        else:
            a, words = tts(spoken, {**cfg, "perfil_voz": s.get("perfil_voz"), "animo": s.get("animo", "neutro")},
                           palabras=False)
        d = len(a) / SR
        if s.get("tipo") == "opinion":
            opinion_spans.append((t, t + d))
        seg_times.append((t, t + d))
        moods.append((t, s.get("animo", "calido")))
        pause = s.get("pausa") or 0.35
        if k == len(cfg["escenas"]) - 1 and cfg.get("extras", {}).get("loop", True):
            pause = min(pause, 0.35)      # final en loop: sin silencio largo al terminar
        audio += [a, np.zeros(int(pause * SR), np.float32)]
        partes.append(words)
        t += d + pause
    # Whisper UNA sola vez por video (no por escena) si algún motor no entregó tiempos por palabra
    todas = whisper_words(np.concatenate(audio)) if any(not w for w in partes) else []
    for k, s in enumerate(cfg["escenas"]):
        st0, en0 = seg_times[k]; d = en0 - st0
        words = partes[k] or [(w0 - st0, w1 - st0, wt) for (w0, w1, wt) in todas if st0 - 0.05 <= w0 < en0 + 0.05]
        toks = tokens(s["texto"])
        def tok_time(i, words=words, d=d, toks=toks):
            j = round(i * len(words) / max(len(toks), 1))
            return words[j][0] if j < len(words) else d * i / max(len(toks), 1)
        for lines, first in chunks(toks):
            st = tok_time(first) if first else 0.0
            n_tok = sum(len(l) for l in lines)
            subs.append([st0 + st, None, lines, [st0 + (tok_time(first + q) if first + q else 0.0) for q in range(n_tok)]])
        print(f"   escena {k + 1}/{len(cfg['escenas'])}  {d:.1f}s")
    total = t
    for i in range(len(subs)):
        nxt = subs[i + 1][0] if i + 1 < len(subs) else total
        seg_end = next(e for (a, e) in seg_times if a <= subs[i][0] < e + 0.01)
        subs[i][1] = min(nxt + 0.12, seg_end + 0.6)
        subs[i][0] -= 0.06
    voice = np.concatenate(audio); voice = voice / np.abs(voice).max() * 0.89
    print(f"   duración total: {total:.1f}s")
    if total < 60:
        raise DuracionFueraDeRango(total)
    if total > 70:
        raise DuracionFueraDeRango(total)
    if total > 95:
        print("   ⚠ La duración está fuera de 60–90 s: ajusta el guion.")

    # 2) imágenes o fondo de video
    photos, credits = [], []
    video_bg_frames, video_bg_fps = [], 0
    if video_bg:
        import fondos_satisfactorios as FS
        print("2/4 Eligiendo fondo de vídeo…")
        try:
            frames_bg = []
            fps_bg = 15
            # B-ROLL POR TRAMO (vídeo): un clip distinto por tramo narrativo (<=7 s), buscado
            # con el TEXTO de ese tramo. Antes se elegía UN tema global para los 66 s del vídeo
            # (FS.obtener_clips sortea random.choice(TEMAS) sin mirar el guion). Se degrada en
            # cascada: b-roll por tramo -> tema global -> fondo de fotos.
            if cfg.get("broll", True):
                try:
                    import broll as B
                    pl = B.plan(cfg, seg_times, max_s=float(cfg.get("segundos_clip", 7)))
                    # Default PEXELS, no pixabay: medido en vivo, Pexels devuelve 30/30 clips
                    # VERTICALES 1080x1920 mientras Pixabay apenas tiene vertical (0 de 30 en
                    # "hospital corridor"). También se acepta "coverr" (sin clave, horizontal).
                    pl = B.buscar_clips(pl, cfg.get("fuente_videos", "pexels"))
                    usados = [t for t in pl if t.get("clip")]
                    for t in usados:
                        d = max(t["t1"] - t["t0"], 1.0)
                        f, fps_bg, tmpdir = FS.preparar_frames([t["clip"]], d, fps=fps_bg, seg_por_clip=d)
                        TEMPORALES.append(tmpdir)
                        frames_bg.extend(f)
                    if frames_bg:
                        print(f"   b-roll: {len(usados)} tramos con clip propio · {len(frames_bg)} fotogramas")
                    else:
                        print("   b-roll: ningún tramo con clip utilizable; paso al tema global")
                except Exception as e:
                    print(f"   ⚠ b-roll de vídeo falló ({e}); paso al tema global")
                    frames_bg = []
            if frames_bg:
                video_bg_frames, video_bg_fps = frames_bg, fps_bg
            else:
                clips, tema = FS.obtener_clips(cfg.get("fuente_videos", "pexels"))
                video_bg_frames, video_bg_fps, frames_dir = FS.preparar_frames(
                    clips, total, seg_por_clip=float(cfg.get("segundos_clip", 10)))
                TEMPORALES.append(frames_dir)
            spans = [(0, -0.4, total + 1)]
        except RuntimeError as e:
            # "No hay clips ni en la API ni en videos_fondo" no es fatal: el README promete
            # caer al fondo de fotos temáticas. Se captura SOLO el RuntimeError de falta de
            # material; cualquier otro fallo (red, ffmpeg, permiso) sigue propagándose.
            print(f"   ⚠ {e}")
            print("   → sigo con el fondo de fotos temáticas")
            video_bg = False
    if not video_bg:
        print("2/4 Buscando imágenes…")
        # Orden de busqueda. Se filtra por las fuentes que EXISTEN para que un modulo ausente
        # no provoque KeyError, y solo entran las de IMAGEN (pexels_video/pixabay_video
        # devuelven clips y romperian get_image). Las nuevas van primero: mas catalogo.
        orden = cfg.get("fuentes") or [f for f in ("pexels", "pixabay", "openverse_ampliado",
                                                   "wikimedia_categorias", "openverse", "wikimedia",
                                                   "flickr_cc") if f in FUENTES_IMAGEN]
        imagenes = cfg.get("imagenes") or []
        # B-ROLL POR TRAMO: app/broll.py parte el guion en tramos de <=7 s y propone para cada
        # uno una busqueda EN INGLES derivada del TEXTO de ese tramo. Antes habia 6-7 imagenes
        # para 15 escenas y salian planos de hasta 15.6 s (medido en el render original); asi
        # hay una imagen por tramo y ningun plano pasa de 7 s. Desactivable con "broll": false.
        broll_escenas = None
        if imagenes and cfg.get("broll", True):
            try:
                import broll as B
                pl = B.plan(cfg, seg_times)
                if len(pl) > len(imagenes) and len(pl) <= 30:   # solo si aporta de verdad
                    imagenes = [dict(buscar=t["consulta"],
                                     alternativas=list(t.get("alternativas") or [])) for t in pl]
                    broll_escenas = [list(t.get("escenas") or []) for t in pl]
                    print(f"   b-roll: {len(pl)} tramos (<=7 s) con búsqueda por el texto de cada tramo")
            except Exception as e:
                print(f"   ⚠ broll no disponible ({e}); uso las imágenes del guion")
        if not imagenes:
            print("   ⚠ El guion no trae imágenes; uso un fondo de color liso.")
            imagenes = [None]
        elif broll_escenas is None and not 5 <= len(imagenes) <= 7:
            print(f"   ⚠ El guion trae {len(imagenes)} imágenes; lo ideal son 5 a 7.")
        hash_prev = None
        for k, item in enumerate(imagenes):
            im, meta = (None, None) if item is None else get_image(item, cache, orden)
            # Anti-repetición visual: si la foto es CASI IGUAL a la anterior se prueban las
            # búsquedas alternativas de ese tramo antes de aceptarla. El plan de broll elige por
            # texto, no por lo ya mostrado, y salían tres mesas de comedor seguidas que se veían
            # como un único plano de 13 s (auditoría de la ronda final).
            if im is not None and hash_prev is not None:
                if _hamming(_ahash(im), hash_prev) <= 6 and isinstance(item, dict):
                    for alt in (item.get("alternativas") or [])[:2]:
                        im2, meta2 = get_image({"buscar": alt}, cache, orden)
                        if im2 is not None and _hamming(_ahash(im2), hash_prev) > 6:
                            im, meta = im2, meta2
                            print(f"    ↻ repetida; uso la alternativa «{alt}»")
                            break
            if im is None:
                if not photos:
                    im = Image.new("RGB", (1080, 1920), (60, 25, 50))
                    photos.append(prep_photo(im, bool(cfg.get("visual_dinamico")))); continue
                photos.append(photos[-1]); continue
            hash_prev = _ahash(im)
            photos.append(prep_photo(im, bool(cfg.get("visual_dinamico"))))
            if meta:
                credits.append(f'{meta["artist"]} – {meta["license"]} – {meta["fuente"]} ({meta["page"]})')
            print("   ", credits[-1] if meta else item)
        if broll_escenas is not None:
            # Cada escena usa la imagen de SU tramo (el bucle de arriba añade siempre una
            # entrada a photos, así que len(photos) == len(imagenes) y el índice es válido).
            img_of = [0] * len(cfg["escenas"])
            for k, idxs in enumerate(broll_escenas):
                for e in idxs:
                    if 0 <= e < len(img_of):
                        img_of[e] = k
        else:
            img_of = [min(max(int(s["imagen"]), 0), len(photos) - 1) if isinstance(s.get("imagen"), (int, float))
                      else min(k * len(photos) // len(cfg["escenas"]), len(photos) - 1)
                      for k, s in enumerate(cfg["escenas"])]
        spans = []
        for k, p in enumerate(img_of):
            a = seg_times[k][0] - (0.4 if k == 0 else 0)
            b = seg_times[k + 1][0] if k + 1 < len(seg_times) else total + 1
            if spans and spans[-1][0] == p:
                spans[-1] = (p, spans[-1][1], b)
            else:
                spans.append((p, a, b))

    photo_files = []
    for p, im in enumerate(photos):
        fp = cache / f"_prep_{name}_{p}.jpg"
        im.convert("RGB").save(fp, format="JPEG", quality=95, subsampling=0, optimize=True)
        photo_files.append(str(fp))
    m = re.search(r"/r/([A-Za-z0-9_-]+)", cfg.get("fuente_reddit", ""))
    default_subreddit = {"salud_mental": "Salud mental", "psicologia_diaria": "Psicología cotidiana"}.get(categoria, "r/AmItheAsshole")
    # Para enlaces de Reddit, el subreddit del post es la fuente de verdad;
    # el guion generado puede proponer por error otro subreddit.
    subreddit = (f"r/{m.group(1)}" if categoria == "reddit" and m else
                 cfg.get("subreddit") or default_subreddit)
    pausas = [s.get("pausa") or 0 for s in cfg["escenas"]]
    q = [k for k, pz in enumerate(pausas) if pz >= 1.2]
    poll_start = seg_times[q[-1]][0] if q else seg_times[max(len(seg_times) - 2, 0)][0]
    extras_cfg = cfg.get("extras", {})
    portada_cfg = dict(cfg.get("portada")) if isinstance(cfg.get("portada"), dict) else {}
    # PORTADA OBLIGATORIA EN LOS FORMATOS EDUCATIVOS: los vídeos de salud mental y de
    # psicología salen SIEMPRE con portada, y el rótulo es el NOMBRE de la patología o del
    # sesgo (no el titular completo). Se construye aquí, así que no depende de que el LLM se
    # acuerde de pedirla. Sin doodle por defecto: en educativo es más sobrio.
    if categoria in CATEGORIAS_EDUCATIVAS:
        portada_cfg.setdefault("texto", _nombre_tema(cfg))
        portada_cfg.setdefault("color_fondo", "#14121f")
        portada_cfg.setdefault("color_trazo", "#ffffff")
        portada_cfg.setdefault("dibujo", "ninguno")
    # PORTADA DE IMPACTO EN LAS HISTORIAS DE REDDIT: sin doodle. La portada es una FOTO nítida,
    # buscada en los bancos configurados (Pexels, Pixabay, ...) con `portada.imagen_buscar`, y
    # una PREGUNTA tendenciosa en frase completa (`portada.pregunta`) que resume lo más
    # importante del relato. Si el guion es antiguo y no trae esos campos, la pregunta es el
    # título y la imagen se busca con la primera búsqueda de "imagenes".
    if categoria == "reddit":
        portada_cfg["modo"] = "impacto"
        portada_cfg["dibujo"] = "ninguno"
        pregunta = str(portada_cfg.get("pregunta") or "").strip() or str(cfg.get("titulo") or "").strip()
        portada_cfg["texto"] = pregunta
        try:
            _q = portada_cfg.get("imagen_buscar")
            if not _q:
                _im0 = (cfg.get("imagenes") or [None])[0]
                _q = _im0.get("buscar") if isinstance(_im0, dict) else _im0
            if _q:
                _orden_p = cfg.get("fuentes") or [f for f in ("pexels", "pixabay", "openverse_ampliado",
                                                              "wikimedia_categorias", "openverse", "wikimedia",
                                                              "flickr_cc") if f in FUENTES_IMAGEN]
                print(f"   portada: buscando imagen de impacto «{_q}»")
                # NO REPETIR PORTADA ENTRE VIDEOS: get_image elige la foto que mejor calza con la
                # búsqueda, así que búsquedas parecidas devolvían SIEMPRE la misma foto. Se guardan
                # los ids usados en portadas anteriores y se descartan.
                _reg = ROOT / "salida" / "registros" / "portadas_usadas.json"
                try:
                    _prev = json.loads(_reg.read_text(encoding="utf-8")) if _reg.exists() else []
                except Exception:
                    _prev = []
                USADAS.update(_prev)
                _imp, _meta = get_image({"buscar": _q,
                                         "alternativas": list(portada_cfg.get("imagen_alternativas") or [])},
                                        cache, _orden_p)
                if _imp is not None:
                    _fp = cache / f"_portada_{name}.jpg"
                    _imp.convert("RGB").save(_fp, format="JPEG", quality=95, subsampling=0)
                    TEMPORALES.append(_fp)
                    portada_cfg["imagen_fondo"] = str(_fp)
                    if _meta and _meta.get("id"):
                        try:
                            _reg.parent.mkdir(parents=True, exist_ok=True)
                            _reg.write_text(json.dumps((_prev + [_meta["id"]])[-300:]), encoding="utf-8")
                        except Exception:
                            pass
                    if _meta:
                        credits.append(f'{_meta["artist"]} – {_meta["license"]} – {_meta["fuente"]} ({_meta["page"]}) [portada]')
                else:
                    print("   ⚠ portada: no encontré imagen; uso la primera foto del video")
        except Exception as e:
            print(f"   ⚠ portada: la búsqueda de imagen falló ({e}); uso la primera foto del video")
    # DOODLE ACORDE AL RELATO: se elige SEGÚN EL TEXTO (título + descripción + escenas) con
    # app/doodle_reglas.py y se dibuja con app/doodles.py. Antes era SIEMPRE el mismo
    # app/assets/pensativo.jpg, igual para una traición familiar que para un sesgo cognitivo.
    # Se considera "sin preferencia" el vacío, la palabra "auto" y el pensativo heredado (los
    # guiones antiguos y el prompt lo traían escrito). "ninguno" desactiva el doodle.
    # OJO AL ORDEN: hay que detectar "auto" ANTES de convertir la ruta a absoluta. Si no,
    # "auto" se transformaba en "<proyecto>\auto", la comparación fallaba y portada_sprite
    # omitía el dibujo EN SILENCIO: la portada salía sin doodle y sin ningún error.
    _dib = str(portada_cfg.get("dibujo") or "").strip()
    _sin_dib = _dib.lower() in ("ninguno", "ninguna", "none", "no", "false", "0")
    if _sin_dib:
        portada_cfg["dibujo"] = ""
    _auto = (not _sin_dib) and ((not _dib) or _dib.lower() == "auto"
                                or os.path.basename(_dib).lower() == "pensativo.jpg")
    if portada_cfg.get("dibujo") and not os.path.isabs(portada_cfg["dibujo"]) and not _auto:
        portada_cfg["dibujo"] = str(ROOT / portada_cfg["dibujo"])
    portada_on = (bool(cfg.get("portada_titulo")) or bool(portada_cfg)
                  or categoria in CATEGORIAS_EDUCATIVAS or categoria == "reddit")
    if portada_on and _auto:
        try:
            import doodle_reglas, doodles
            texto = " ".join([str(cfg.get("titulo") or ""), str(cfg.get("descripcion") or "")] +
                             [str(e.get("texto") or "") for e in (cfg.get("escenas") or [])])
            nombre = doodle_reglas.elegir(texto, cfg.get("categoria_video"))
            portada_cfg["dibujo"] = str(doodles.dibujar(nombre, CACHE / f"doodle_{nombre}.png"))
            print(f"   portada: doodle «{nombre}» elegido por el relato")
        except Exception as e:
            print(f"   ⚠ doodle automático no disponible ({e}); uso assets/pensativo.jpg")
            portada_cfg["dibujo"] = str(APP / "assets" / "pensativo.jpg")
    state = dict(subs=subs, spans=spans, moods=moods, photos=photo_files, total=total,
                 video_bg_frames=[str(p) for p in video_bg_frames], video_bg_fps=video_bg_fps,
                 visual_dinamico=bool(cfg.get("visual_dinamico")),
                 motion_seed=sum(name.encode("utf-8")) % 4,
                 aviso=cfg.get("aviso", ""),
                 extras=extras_cfg, subreddit=subreddit, titulo=cfg.get("titulo", ""),
                 portada=portada_on, portada_cfg=portada_cfg,
                 card_end=min(seg_times[0][1] + 0.4, 6.0), poll_start=poll_start,
                 encuesta=cfg.get("encuesta", ["TIENE RAZÓN", "SE PASÓ"]),
                 plantilla=plantilla, opinion_spans=opinion_spans)
    if extras_cfg.get("zoom", True):
        import extras as X
        state["punches"] = X.punch_times(cfg, seg_times, subs)

    # 3) render en paralelo
    import soundfile as sf
    tmp = Path(tempfile.gettempdir()) / f"{name}_mix.wav"; TEMPORALES.append(tmp)
    import musica, zlib
    mus, mdesc, mcred = musica.pista(len(voice), TPL.get("musica", "pad"), zlib.crc32(name.encode()),
                                     ROOT / "musica", voice, cfg.get("volumen_musica", 1.0),
                                     web=False if video_bg else cfg.get("musica_web", True), cache_web=CACHE / "musica_web")
    print(f"   música: {mdesc}")
    mix = voice + mus
    if extras_cfg.get("sonidos", True):
        # SFX AUTOMATICOS: app/sfx.py lee el GUION y decide que efecto va en cada momento
        # (giros, acusaciones, cifras, preguntas, escena de opinion, cambio de plano, encuesta).
        # Sustituye al generador fijo de extras.sfx_track, que solo sabia poner un whoosh por
        # cambio de span y un pop en las palabras resaltadas. Si sfx.py falla, se cae al antiguo.
        try:
            import sfx as SFX
            ev = SFX.momentos(cfg, subs, spans, seg_times,
                              poll_start if extras_cfg.get("encuesta", True) else None)
            mix, sfx_desc = SFX.mezclar(mix, ev, cache_dir=CACHE / "sfx_web",
                                        web=cfg.get("sfx_web", True))
            cuenta = {t: sum(1 for e in ev if e["tipo"] == t) for t in dict.fromkeys(e["tipo"] for e in ev)}
            print("   sfx: " + (", ".join(f"{t}x{n}" for t, n in cuenta.items()) or "ninguno"))
        except Exception as e:
            print(f"   ⚠ sfx.py fallo ({e}); uso el generador antiguo de extras")
            import extras as X
            pops = [a for a, b, lines, tm in subs if any(hl for l in lines for _, hl in l)]
            mix = mix + X.sfx_track(len(mix), [a for _, a, _ in spans[1:]], pops,
                                    poll_start if extras_cfg.get("encuesta", True) else None)
    # La normalización divide por el pico del mix. Si el mix fuese todo ceros (voz vacía por un
    # fallo del TTS) la división daba NaN y el render salía con audio corrupto sin avisar:
    # detectado en la revisión adversarial. El 1e-9 lo deja en silencio limpio en vez de NaN.
    sf.write(tmp, mix / (np.abs(mix).max() + 1e-9) * 0.95, SR)
    out_final = out_dir / f"{name}.mp4"
    # Se renderiza a un .part y se renombra con os.replace al terminar:
    #  - con -y, ffmpeg ya habria machacado el video bueno anterior antes de saber si este
    #    render sale bien; asi el anterior sobrevive si algo falla.
    #  - el .part no lo ve la lista de la GUI ni limpiar.py (que busca *.mp4 en salida\).
    out = out_dir / f"{name}.mp4.part"
    TEMPORALES.append(out)     # si algo falla, limpiar_corrida() borra el .part
    workers = int(os.getenv("SHORTS_PROCESOS") or 0) or max(2, min((os.cpu_count() or 2) - 1, 8))   # 6c/12t → 8
    enc, enc_name = video_encoder()
    use_gpu = os.getenv("SHORTS_RENDER") != "cpu" and (cuda_ok() or os.getenv("SHORTS_RENDER") == "gpu-test")
    modo = "GPU (PyTorch/CUDA)" if use_gpu else f"CPU, {workers} procesos"
    ln = loudnorm_params(tmp)      # mide el mix y devuelve el filtro de DOS pasadas
    print(f"3/4 Renderizando video… ({modo}, codificador {enc_name})")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(tmp), *enc,
                           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                           "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-af", ln, "-ar", "48000",
                           "-shortest", "-movflags", "+faststart", "-f", "mp4", str(out)], stdin=subprocess.PIPE)
    nf = int(total * FPS); t0 = time.time()
    def frames():
        if use_gpu:
            from gpu_render import GPURenderer
            from concurrent.futures import ThreadPoolExecutor
            from collections import deque
            import torch
            r = GPURenderer(state, "cuda" if torch.cuda.is_available() else "cpu")
            # tubería: la GPU calcula el fotograma n+1 mientras hilos de CPU dibujan overlays del n
            pend = deque()
            with ThreadPoolExecutor(max_workers=4) as ex:
                for n in range(nf):
                    pend.append(ex.submit(r.cpu, *r.gpu(n)))
                    if len(pend) >= 6:
                        yield pend.popleft().result()
                while pend:
                    yield pend.popleft().result()
        else:
            with mp.Pool(workers, initializer=_init_worker, initargs=(state,)) as pool:
                yield from pool.imap(_render_frame, range(nf), chunksize=4)
    import queue, threading
    cola = queue.Queue(maxsize=8)
    fallo = threading.Event()

    def escritor():
        # Si ffmpeg muere, este hilo NO debe morir: si muriera, nadie consumiria la cola y el
        # hilo principal se quedaria bloqueado para siempre en cola.put. Por eso drena
        # (descarta) en vez de salir, y avisa con el evento.
        while True:
            buf = cola.get()
            if buf is None:
                break
            if fallo.is_set():
                continue
            try:
                ff.stdin.write(buf)
            except OSError as e:
                # En Windows una tuberia rota lanza OSError [Errno 22], NO BrokenPipeError.
                fallo.set()
                print(f"   ⚠ ffmpeg dejó de aceptar datos: {e}")

    th = threading.Thread(target=escritor, daemon=True); th.start()
    gen = frames()
    try:
        for n, buf in enumerate(gen):
            while True:
                try:
                    cola.put(buf, timeout=30)
                    break
                except queue.Full:
                    # Cubre tambien el caso de un ffmpeg colgado (ni lee ni muere), en el que
                    # el evento nunca se activaria.
                    if fallo.is_set() or not th.is_alive():
                        break
            if fallo.is_set() or not th.is_alive():
                break
            if n % (FPS * 5) == 0:
                print(f"   {n / nf * 100:5.1f}%  ({time.time() - t0:.0f}s)", end="\r")
    finally:
        gen.close()                     # cierra el Pool / ThreadPool del generador
        cola.put(None)
        th.join()
        try:
            ff.stdin.close()
        except OSError:
            pass
        try:
            ff.wait(timeout=60)
        except subprocess.TimeoutExpired:
            ff.kill(); ff.wait()
    print(f"   100.0%  ({time.time() - t0:.0f}s)")

    # Comprobacion del resultado. Sin esto, un video roto o inexistente se daba por bueno:
    # se generaba la portada, se escribian _descripcion.txt/_creditos.txt y "Listo".
    if fallo.is_set() or ff.returncode != 0:
        raise RuntimeError(f"ffmpeg falló (código {ff.returncode}); no se generó {out_final.name}")
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg terminó pero {out.name} no existe o está vacío")
    os.replace(out, out_final)
    out = out_final
    for fp in photo_files:
        try: os.remove(fp)
        except OSError: pass

    # 3b) miniatura: el primer fotograma, como PNG para subirlo de portada
    portada_png = out_dir / f"{name}_portada.png"
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out),
                        "-vf", "select=eq(n\\,0)", "-frames:v", "1", str(portada_png)],
                       check=True, timeout=60, capture_output=True)
        print(f"   portada → {portada_png}")
    except (subprocess.SubprocessError, OSError):
        pass

    # 4) textos
    print("\n4/4 Guardando descripción…")
    cred = "Imágenes:\n" + "\n".join(credits) if credits else ""
    if mcred:
        cred = (cred + "\n\n" if cred else "") + mcred
    sidecar = out_dir / f"{name}_creditos.txt"
    if video_bg:
        sidecar.unlink(missing_ok=True)
        cred = ""
    else:
        sidecar.write_text(cred, encoding="utf-8")
    desc = "\n\n".join(x for x in [cfg.get("titulo", ""), cfg.get("descripcion", ""),
                                   " ".join(cfg.get("hashtags", [])), cred] if x)
    (out_dir / f"{name}_descripcion.txt").write_text(desc, encoding="utf-8")
    print(f"Listo → {out}")

if __name__ == "__main__":
    mp.freeze_support()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    # varios JSON en una misma ejecución: los modelos (Chatterbox, Whisper, CLIP) se cargan una sola vez
    fallos = []
    for i, p in enumerate(sys.argv[1:], 1):
        if len(sys.argv) > 2:
            print(f"\n=== [{i}/{len(sys.argv) - 1}] {Path(p).name}")
        try:
            main(p)
        except (Exception, SystemExit) as e:
            print(f"  ✗ {Path(p).name}: {e}"); fallos.append(p)
    if fallos:
        sys.exit(f"{len(fallos)} video(s) fallaron")
