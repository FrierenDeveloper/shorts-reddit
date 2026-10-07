"""Búsqueda y preparación de videos de fondo silenciosos para Shorts de Reddit."""
import json
from functools import lru_cache
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
MIN_DURACION = 15
OBJETIVO_DURACION = 20
SEGUNDOS_CLIP = 10          # cada cuántos segundos cambia el clip de fondo
CLIPS_FONDO = 4             # cuántos clips distintos se intentan reunir
TEMAS = (
    {"q": "kinetic sand cutting", "label": "arena cinética", "terms": ("kinetic", "sand", "cut", "asmr"), "anchors": ("sand", "kinetic")},
    {"q": "soap cutting ASMR", "label": "corte de jabón", "terms": ("soap", "cut", "asmr"), "anchors": ("soap",)},
    {"q": "slime cutting satisfying", "label": "slime", "terms": ("slime", "cut", "satisfying"), "anchors": ("slime",)},
    {"q": "satisfying vegetable cutting", "label": "corte de verduras", "terms": ("vegetable", "chop", "cut", "food"), "anchors": ("vegetable", "food")},
    {"q": "satisfying chalk cutting", "label": "corte de tiza", "terms": ("chalk", "cut", "satisfying"), "anchors": ("chalk",)},
    {"q": "pressure washing satisfying", "label": "limpieza a presión", "terms": ("pressure", "wash", "clean"), "anchors": ("pressure", "wash")},
)


def _api_key(fuente):
    variable = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}[fuente]
    key = os.getenv(variable, "").strip()
    config = ROOT / "config" / "claves.json"
    if not key and config.is_file():
        try:
            key = str(json.loads(config.read_text(encoding="utf-8")).get(fuente, "")).strip()
        except (OSError, ValueError, TypeError):
            pass
    if key.upper().startswith("PEGA_AQUI"):
        return ""
    return key


def _locales():
    folder = ROOT / "videos_fondo"
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"})


def _puntuacion(hit, tema):
    texto = " ".join((str(hit.get("tags", "")), str(hit.get("description", "")))).lower()
    if not any(term in texto for term in tema["anchors"]):
        return 0
    return sum(1 for term in tema["terms"] if term in texto)


def _descargar_hit(hit, cache):
    video_id = hit.get("id")
    variants = hit.get("videos") or {}
    info = variants.get("medium") or variants.get("small") or variants.get("large")
    url = (info or {}).get("url")
    parsed = urlparse(url or "")
    if not video_id or parsed.scheme != "https" or parsed.hostname != "cdn.pixabay.com" or parsed.path[-4:].lower() != ".mp4":
        return None
    dest = cache / f"pixabay_{int(video_id)}.mp4"
    if dest.is_file() and dest.stat().st_size > 100_000:
        return dest
    tmp = dest.with_suffix(".download")
    try:
        with requests.get(url, stream=True, timeout=(15, 90)) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if content_type and "video" not in content_type and "octet-stream" not in content_type:
                return None
            total = 0
            with tmp.open("wb") as f:
                for chunk in resp.iter_content(1024 * 256):
                    if chunk:
                        total += len(chunk)
                        if total > 150 * 1024 * 1024:
                            raise ValueError("clip demasiado grande")
                        f.write(chunk)
        if total > 100_000:
            tmp.replace(dest)
            return dest
    except (requests.RequestException, OSError, ValueError):
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return None


@lru_cache(maxsize=64)
def _duracion_local(clip):
    probe = shutil.which("ffprobe")
    if not probe:
        return 0
    try:
        info = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(clip)],
                              check=True, capture_output=True, text=True, timeout=20)
        return float(info.stdout.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0


def _sin_menores(hits):
    """Seguridad: ningún clip de fondo puede mostrar niños, bebés o adolescentes."""
    try:
        import seguridad_menores as SM
        return SM.filtrar_hits_video(hits)
    except ImportError:
        return hits


def _desde_pixabay(key, tema):
    cache = ROOT / "cache" / "videos_satisfactorios"
    cache.mkdir(parents=True, exist_ok=True)
    consulta = tema["q"]
    cache_id = re.sub(r"[^a-z0-9]+", "_", consulta.lower()).strip("_")
    cache_json = cache / f"busqueda_{cache_id}.json"
    hits = []
    try:
        if cache_json.is_file() and time.time() - cache_json.stat().st_mtime < 24 * 3600:
            hits = json.loads(cache_json.read_text(encoding="utf-8"))
        else:
            resp = requests.get("https://pixabay.com/api/videos/", params={
                "key": key, "q": consulta, "per_page": 25, "safesearch": "true", "order": "popular",
            }, timeout=25)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            cache_json.write_text(json.dumps(hits), encoding="utf-8")
    except (requests.RequestException, OSError, ValueError, TypeError):
        return None
    hits = _sin_menores(hits)
    candidatos = [h for h in hits if _puntuacion(h, tema) >= 1 and int(h.get("duration", 0)) >= MIN_DURACION]
    preferidos = [h for h in candidatos if int(h.get("duration", 0)) >= OBJETIVO_DURACION]
    otros = [h for h in candidatos if h not in preferidos]
    random.shuffle(preferidos)
    random.shuffle(otros)
    candidatos = preferidos + otros
    seleccion = []
    for hit in candidatos:
        clip = _descargar_hit(hit, cache)
        if clip and clip not in seleccion:
            seleccion.append(clip)
        if len(seleccion) >= CLIPS_FONDO:
            return seleccion
    return seleccion


def _descargar_pexels(hit, cache):
    video_id = hit.get("id")
    files = [f for f in hit.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("link")]
    if not video_id or not files:
        return None
    # Prefiere HD con suficiente resolución y vertical cuando está disponible.
    # OJO (verificado en vivo): en Pexels `video_files[].quality` llega NULL, así que el
    # criterio `quality == "hd"` que había aquí NUNCA se aplicaba. Se ordena por resolución
    # real y por verticalidad, que sí discriminan.
    files.sort(key=lambda f: (
        int(f.get("height", 0)) >= 720,
        int(f.get("height", 0)) / max(int(f.get("width", 1)), 1),
        int(f.get("height", 0)),
    ), reverse=True)
    url = files[0]["link"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"player.vimeo.com", "videos.pexels.com", "cdn.pexels.com"}:
        return None
    dest = cache / f"pexels_{int(video_id)}.mp4"
    if dest.is_file() and dest.stat().st_size > 100_000:
        return dest
    tmp = dest.with_suffix(".download")
    try:
        with requests.get(url, stream=True, timeout=(15, 90)) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if content_type and "video" not in content_type and "octet-stream" not in content_type:
                return None
            total = 0
            with tmp.open("wb") as f:
                for chunk in resp.iter_content(1024 * 256):
                    if chunk:
                        total += len(chunk)
                        if total > 150 * 1024 * 1024:
                            raise ValueError("clip demasiado grande")
                        f.write(chunk)
        if total > 100_000:
            tmp.replace(dest)
            return dest
    except (requests.RequestException, OSError, ValueError):
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return None


def _desde_pexels(key, tema):
    cache = ROOT / "cache" / "videos_satisfactorios"
    cache.mkdir(parents=True, exist_ok=True)
    consulta = tema["q"]
    cache_id = re.sub(r"[^a-z0-9]+", "_", consulta.lower()).strip("_")
    cache_json = cache / f"pexels_busqueda_{cache_id}.json"
    try:
        if cache_json.is_file() and time.time() - cache_json.stat().st_mtime < 24 * 3600:
            hits = json.loads(cache_json.read_text(encoding="utf-8"))
        else:
            resp = requests.get("https://api.pexels.com/v1/videos/search", headers={"Authorization": key}, params={
                "query": consulta, "per_page": 30, "orientation": "portrait",
            }, timeout=25)
            resp.raise_for_status()
            hits = resp.json().get("videos", [])
            cache_json.write_text(json.dumps(hits), encoding="utf-8")
    except (requests.RequestException, OSError, ValueError, TypeError):
        return None

    hits = _sin_menores(hits)
    candidatos = [h for h in hits if int(h.get("duration", 0)) >= MIN_DURACION]
    preferidos = [h for h in candidatos if int(h.get("duration", 0)) >= OBJETIVO_DURACION]
    otros = [h for h in candidatos if h not in preferidos]
    random.shuffle(preferidos)
    random.shuffle(otros)
    candidatos = preferidos + otros
    seleccion = []
    for hit in candidatos:
        clip = _descargar_pexels(hit, cache)
        if clip and clip not in seleccion:
            seleccion.append(clip)
        if len(seleccion) >= CLIPS_FONDO:
            return seleccion
    return seleccion


def obtener_clips(fuente="pixabay"):
    fuente = str(fuente or "pixabay").lower()
    if fuente not in ("pixabay", "pexels"):
        fuente = "pixabay"
    tema = random.choice(TEMAS)
    key = _api_key(fuente)
    if key:
        buscar = _desde_pexels if fuente == "pexels" else _desde_pixabay
        clips = buscar(key, tema)
        if clips:
            print(f"   fondo: {len(clips)} clips de {fuente.capitalize()} · {tema['label']} · mínimo {MIN_DURACION}s, preferencia {OBJETIVO_DURACION}s+")
            return clips, tema
        print(f"   {fuente.capitalize()} no encontró clips relacionados; probando la biblioteca local")
    else:
        print(f"   {fuente.capitalize()} sin clave disponible; usando la biblioteca local")
    locales = [p for p in _locales() if _duracion_local(str(p)) >= MIN_DURACION]
    if not locales:
        raise RuntimeError(f"No encontré clips de fondo de al menos {MIN_DURACION} segundos. Revisa Pixabay o agrega videos largos a videos_fondo.")
    grupos = [(t, [p for p in locales if any(term in p.stem.lower() for term in t["terms"])])
              for t in TEMAS]
    grupos = [(t, archivos) for t, archivos in grupos if archivos]
    if grupos:
        tema, compatibles = random.choice(grupos)
    else:
        # Sin clave, conserva el tema del clip local seleccionado para que ambos segmentos coincidan.
        clip = random.choice(locales)
        etiqueta = clip.stem.replace("_", " ")
        tema = {"q": etiqueta, "label": etiqueta, "terms": ()}
        compatibles = [clip]
    random.shuffle(compatibles)
    clips = compatibles[:CLIPS_FONDO]
    if not clips:
        raise RuntimeError(f"No hay clips locales de al menos {MIN_DURACION} segundos. Agrega videos a videos_fondo.")
    print(f"   fondo: {len(clips)} clips locales · {tema['label']}")
    return clips, tema


def preparar_frames(clips, segundos, fps=15, seg_por_clip=SEGUNDOS_CLIP):
    """Prepara el fondo a pantalla completa en 9:16, cambiando de clip cada ~seg_por_clip segundos.
    Si hay más segmentos que clips, vuelve a usar los mismos con un punto de entrada distinto."""
    destino = Path(tempfile.mkdtemp(prefix="shorts_fondo_"))
    duracion = min(max(float(segundos), 1.0), 90.0)
    if not clips:
        shutil.rmtree(destino, ignore_errors=True)
        raise ValueError("Se necesita al menos un clip para el fondo del Short.")
    seg_por_clip = max(float(seg_por_clip), 1.0)
    n_seg = max(1, math.ceil(duracion / seg_por_clip))
    medias = {str(c): _duracion_local(str(c)) for c in clips}
    arranques = (0.0, 0.48, 0.22, 0.70, 0.35, 0.60, 0.12, 0.85)
    frames = []
    try:
        for n in range(n_seg):
            clip = clips[n % len(clips)]
            media = medias.get(str(clip), 0)
            reuso = n // len(clips)          # cuántas veces se repite este clip
            offset = arranques[reuso % len(arranques)] * media if media > 2 else 0.0
            dur = min(seg_por_clip, duracion - n * seg_por_clip)
            subdir = destino / str(n)
            subdir.mkdir()
            # Rellena todo el lienzo 9:16 con el metraje: no hay banda borrosa ni márgenes.
            filtro = f"fps={fps},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,format=yuvj420p"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1",
                "-ss", f"{offset:.3f}", "-i", str(clip),
                "-vf", filtro, "-t", f"{dur:.3f}", "-q:v", "3", str(subdir / "%06d.jpg"),
            ], check=True, timeout=180, capture_output=True)
            frames.extend(sorted(subdir.glob("*.jpg")))
        if not frames:
            raise RuntimeError("FFmpeg no produjo fotogramas para el fondo satisfactorio.")
        print(f"   composición: {n_seg} segmentos de ~{seg_por_clip:.0f}s ({len(clips)} clips) · {len(frames)} fotogramas")
        return frames, fps, destino
    except Exception:
        shutil.rmtree(destino, ignore_errors=True)
        raise
