"""Música de fondo tranquila y libre de derechos.
1) Si hay archivos en la carpeta musica/ (mp3/wav/ogg/m4a sin copyright: YouTube Audio Library, Pixabay Music…),
   elige uno al azar.
2) Si no, compone una pista nueva (generada por el programa, por lo tanto sin derechos de terceros)
   en el estilo de la plantilla, con tonalidad, tempo y acordes al azar.
En ambos casos la música baja automáticamente cuando habla la voz (ducking)."""
import random, subprocess
from pathlib import Path
import numpy as np

SR = 24000
PROGRESIONES = [
    [0, 5, 3, 4], [0, 3, 5, 4], [5, 3, 0, 4], [0, 4, 5, 3], [0, 5, 1, 4], [0, 2, 5, 4],
]
ESCALA = [0, 2, 4, 5, 7, 9, 11]           # mayor; grados → semitonos


def _acorde(raiz_midi, grado, menor_rel=False):
    base = ESCALA[grado % 7]
    notas = [ESCALA[(grado + k) % 7] + 12 * ((grado + k) // 7) for k in (0, 2, 4)]
    return [raiz_midi + n for n in notas]


def _hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def _env(n, a, r):
    e = np.ones(n); ia, ir = min(int(a * SR), n // 2), min(int(r * SR), n // 2)
    if ia: e[:ia] = np.linspace(0, 1, ia)
    if ir: e[-ir:] *= np.linspace(1, 0, ir)
    return e


def _lp(x, corte):   # filtro pasa-bajos (FFT) para suavizar el timbre
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / corte) ** 4)
    return np.fft.irfft(X, len(x))


def componer(n, estilo, rng):
    t = np.arange(n) / SR
    raiz = rng.choice([45, 47, 48, 50, 52, 53])            # La2..Fa3
    prog = rng.choice(PROGRESIONES)
    bpm = {"pad": 60, "lofi": rng.choice([72, 78, 84]), "synth": 70, "piano": rng.choice([66, 72]),
           "musicbox": rng.choice([80, 90]), "tetrico": rng.choice([54, 58, 62])}[estilo]
    beat = 60 / bpm; compas = beat * 4
    out = np.zeros(n)
    ncomp = int(n / SR / compas) + 2
    for c in range(ncomp):
        t0 = c * compas; i0 = int(t0 * SR)
        if i0 >= n: break
        ac = _acorde(raiz, prog[c % len(prog)])
        seg = min(int(compas * SR * 1.25), n - i0)
        tt = np.arange(seg) / SR
        if estilo in ("pad", "synth", "lofi", "tetrico"):
            notas = ac + [ac[0] - 12]
            if estilo == "tetrico":
                notas = [ac[0] - 12, ac[0], ac[0] + 1, ac[2]]   # segunda menor incluida: disonancia sutil
            for m in notas:
                f = _hz(m)
                if estilo == "synth":
                    w = sum(np.sin(2 * np.pi * f * k * tt * (1 + 0.002 * (k % 2))) / k for k in range(1, 6))
                elif estilo == "tetrico":
                    w = np.sin(2 * np.pi * f * tt * (1 + 0.006 * np.sin(2 * np.pi * 0.15 * tt))) \
                        + 0.25 * np.sin(2 * np.pi * f * 1.997 * tt)   # leve desafinación tipo "wobble"
                else:
                    w = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt)
                out[i0:i0 + seg] += w * _env(seg, compas * 0.35, compas * 0.4) * (0.18 if estilo == "tetrico" else 0.22)
        if estilo in ("piano", "musicbox", "lofi"):
            patron = [0, 1, 2, 1, 0, 2, 1, 2] if estilo != "lofi" else [0, 2, 1, 2]
            paso = beat / 2 if estilo != "lofi" else beat
            for k, idx in enumerate(patron):
                ts = t0 + k * paso
                j = int(ts * SR)
                if j >= n: break
                oct_ = 12 if estilo == "piano" else (24 if estilo == "musicbox" else 12)
                f = _hz(ac[idx] + oct_)
                L = min(int(1.6 * SR), n - j); tt2 = np.arange(L) / SR
                dec = 3.5 if estilo == "piano" else 5.0
                w = (np.sin(2 * np.pi * f * tt2) + 0.4 * np.sin(2 * np.pi * f * 2 * tt2) * np.exp(-tt2 * 6)) * np.exp(-tt2 * dec)
                out[j:j + L] += w * (0.16 if estilo == "piano" else 0.10)
            if estilo == "piano":   # bajo suave
                f = _hz(ac[0] - 12); L = min(int(compas * SR), n - i0); tt3 = np.arange(L) / SR
                out[i0:i0 + L] += np.sin(2 * np.pi * f * tt3) * np.exp(-tt3 * 1.2) * 0.18
        if estilo == "lofi":        # batería muy suave: bombo y "hat"
            for k in range(4):
                j = int((t0 + k * beat) * SR)
                if j >= n: break
                L = min(int(0.25 * SR), n - j); tt4 = np.arange(L) / SR
                if k in (0, 2):
                    out[j:j + L] += np.sin(2 * np.pi * (50 + 60 * np.exp(-tt4 * 30)) * tt4) * np.exp(-tt4 * 14) * 0.35
                h = int((t0 + k * beat + beat / 2) * SR)
                if h < n:
                    Lh = min(int(0.05 * SR), n - h)
                    out[h:h + Lh] += rng.standard_normal(Lh) * np.exp(-np.arange(Lh) / SR * 80) * 0.03
    if estilo in ("pad", "synth", "tetrico"):
        out = _lp(out, 900 if estilo == "synth" else (700 if estilo == "tetrico" else 1800))
    return out


def _cargar(path, n):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"],
                       capture_output=True, check=True)
    a = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    if len(a) < n:
        a = np.tile(a, int(np.ceil(n / max(len(a), 1))))
    ini = random.randint(0, max(len(a) - n, 0))
    return a[ini:ini + n]


# ------------------------------------------------------------------ música de internet (sin copyright)
# Openverse (Freesound, ccMixter, Jamendo, Wikimedia…) filtrado a CC0 / Dominio Público:
# sin derechos ni atribución obligatoria. Solo pistas instrumentales de 45 s o más.
import re
BUSQUEDAS = {
    "pad": ["ambient calm", "ambient pad", "relaxing ambient"],
    "lofi": ["lofi chill", "lofi beat", "chill hop"],
    "synth": ["synthwave ambient", "synth calm", "retro synth"],
    "piano": ["piano calm", "soft piano", "piano relaxing"],
    "musicbox": ["music box", "lullaby instrumental", "calm acoustic"],
    "tetrico": ["dark ambient", "eerie drone", "horror ambient instrumental", "unsettling atmosphere"],
}
GENERICAS = ["instrumental calm", "soft background music", "acoustic guitar calm", "calm instrumental loop"]
NO_INSTRUMENTAL = re.compile(r"vocal|voice|sing|song|lyric|rap\b|choir|speech|spoken|podcast|talk|narrat|poem", re.I)
UA = {"User-Agent": "ShortsLocal/1.0 (uso personal)"}


def musica_web(estilo, semilla, cache_dir, max_cache=25):
    """Descarga una pista instrumental CC0/Dominio Público al azar. Devuelve (ruta, meta) o (None, None)."""
    import requests
    rnd = random.Random(semilla)
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    consultas = BUSQUEDAS.get(estilo, []) + GENERICAS
    rnd.shuffle(consultas)
    for q in consultas[:4]:
        try:
            r = requests.get("https://api.openverse.org/v1/audio/", headers=UA, timeout=20, params=dict(
                q=q, license="cc0,pdm", category="music", page_size=40, mature="false")).json()
        except Exception as e:
            print(f"    (Openverse no respondió: {e})"); return None, None
        cand = [x for x in r.get("results", [])
                if (x.get("duration") or 0) >= 45000 and x.get("url")
                and not NO_INSTRUMENTAL.search(f"{x.get('title', '')} " + " ".join(t.get("name", "") for t in (x.get("tags") or [])))]
        rnd.shuffle(cand)
        for x in cand[:3]:
            ext = (x.get("filetype") or Path(x["url"]).suffix.strip(".") or "mp3")[:4]
            f = cache_dir / f"ov_{x['id']}.{ext}"
            try:
                if not f.exists():
                    f.write_bytes(requests.get(x["url"], headers=UA, timeout=60).content)
                meta = dict(titulo=x.get("title") or "sin título", autor=x.get("creator") or "desconocido",
                            licencia={"cc0": "CC0", "pdm": "Dominio Público"}.get(x.get("license"), x.get("license")),
                            fuente=f"Openverse/{x.get('source', '')}", pagina=x.get("foreign_landing_url", ""))
                for v in sorted(cache_dir.glob("ov_*"), key=lambda p: p.stat().st_mtime)[:-max_cache]:
                    try: v.unlink()                  # no acumular: máximo max_cache pistas guardadas
                    except OSError: pass
                return f, meta
            except Exception:
                continue
    return None, None


def pista(n, estilo, semilla, carpeta, voz, volumen=1.0, web=True, cache_web=None):
    """Devuelve (audio, descripción, crédito|None). voz: pista de voz (para el ducking).
    Prioridad: tus archivos en musica/ → música de internet sin copyright → pista compuesta."""
    rng = np.random.default_rng(semilla)
    archivos = [f for f in Path(carpeta).glob("*") if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".flac")] \
        if Path(carpeta).exists() else []
    m, credito = None, None
    if archivos:
        random.seed(semilla)
        f = random.choice(sorted(archivos))
        m, desc = _cargar(f, n), f"archivo {f.name}"
    elif web and cache_web:
        f, meta = musica_web(estilo, semilla, cache_web)
        if f:
            try:
                m = _cargar(f, n)
                desc = f"internet: «{meta['titulo']}» de {meta['autor']} ({meta['licencia']}, {meta['fuente']})"
                credito = f"Música: «{meta['titulo']}» – {meta['autor']} – {meta['licencia']} – {meta['fuente']} ({meta['pagina']})"
            except Exception as e:
                print(f"    (no se pudo leer la pista descargada: {e})"); m = None
    if m is None:
        m, desc = componer(n, estilo, rng), f"compuesta ({estilo})"
    m = m - m.mean()
    rms = np.sqrt((m ** 2).mean()) + 1e-9
    # Nivel base de la musica. Estaba en 0.035 (~ -29 dBFS RMS): medido sobre el render
    # final, los huecos mas silenciosos daban -29.5/-29.3/-29.6 dB, y con el ducking la
    # musica quedaba en ~ -34 dBFS durante el habla. En un altavoz de movil eso es
    # inaudible: parecia que el video no tenia musica. 0.10 -> ~ -19 dBFS RMS.
    m = m / rms * 0.10 * volumen                           # nivel base audible (~ -19 dBFS RMS)
    # ducking: baja al 45 % mientras habla la voz (1 - 0.55). Con la base mas alta hacía
    # falta mas atenuacion para no competir con la voz.
    env = np.abs(voz[:n]) if len(voz) >= n else np.pad(np.abs(voz), (0, n - len(voz)))
    k = int(0.25 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    habla = np.clip(env / 0.02, 0, 1)
    m = m * (1 - 0.55 * habla)
    tt = np.arange(n) / SR
    m *= np.minimum(1, np.minimum(tt / 2.0, (tt[-1] - tt) / 2.5))  # fade in/out
    return m.astype(np.float32), desc, credito
