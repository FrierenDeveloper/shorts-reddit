"""
Modo por lotes: lee links.txt (un link de Reddit por línea, 4–10), descarga cada post,
escribe el guion con el LLM configurado (ver guion.py) y genera todos los videos.

Uso:  python lote.py            (usa links.txt)
      python lote.py otros.txt
Resultado: salida\\*.mp4 + salida\\lote_<fecha>.txt con el resumen.
"""
import datetime, html, json, re, subprocess, sys, time
from pathlib import Path
import requests

# Los mensajes llevan acentos, flechas y a veces caracteres raros de un titulo; evita que el
# CLI falle al imprimirlos desde una consola Windows configurada con cp1252 (igual que en
# make_short.py).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).resolve().parent
ROOT = APP.parent
UA = {"User-Agent": "windows:shorts-reddit-local:v1.0 (uso personal)"}

def post_id(url):
    m = re.search(r"/comments/([a-z0-9]+)", url) or re.search(r"redd\.it/([a-z0-9]+)", url)
    return m.group(1) if m else None

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/140.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}

def _claves_reddit():
    f = ROOT / "config" / "claves.json"
    c = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return c.get("reddit_client_id", ""), c.get("reddit_client_secret", "")

def _desde_json(d):
    d = d[0]["data"]["children"][0]["data"]
    return d.get("subreddit", ""), d.get("title", ""), html.unescape(d.get("selftext") or ""), d.get("removed_by_category")

def _via_oauth(pid):
    """Método oficial (el más confiable): app gratuita de Reddit, ver README."""
    cid, sec = _claves_reddit()
    if not (cid and sec):
        raise RuntimeError("sin claves de Reddit")
    tok = requests.post("https://www.reddit.com/api/v1/access_token", auth=(cid, sec), headers=UA, timeout=30,
                        data={"grant_type": "client_credentials"}).json()["access_token"]
    r = requests.get(f"https://oauth.reddit.com/comments/{pid}?raw_json=1&limit=1", timeout=30,
                     headers={**UA, "Authorization": f"bearer {tok}"})
    r.raise_for_status()
    return _desde_json(r.json())

def _via_json(pid):
    last = None
    for base in ("https://www.reddit.com", "https://old.reddit.com", "https://api.reddit.com"):
        for hdr in (UA, BROWSER_UA):
            try:
                r = requests.get(f"{base}/comments/{pid}.json?raw_json=1&limit=1", headers=hdr, timeout=30)
                if r.status_code == 429:
                    time.sleep(10); continue
                r.raise_for_status()
                return _desde_json(r.json())      # si Reddit devuelve HTML (bloqueo), falla aquí y prueba otra ruta
            except Exception as e:
                last = e
    raise RuntimeError(f"JSON bloqueado ({type(last).__name__})")

def _via_rss(url, pid):
    import xml.etree.ElementTree as ET
    m = re.search(r"/r/([^/]+)/", url)
    sub = m.group(1) if m else "all"
    for espera in (0, 20, 45):          # si Reddit dice "demasiadas peticiones", espera y reintenta
        time.sleep(espera)
        r = requests.get(f"https://www.reddit.com/r/{sub}/comments/{pid}/.rss", headers=BROWSER_UA, timeout=30)
        if r.status_code != 429:
            break
        print(f"    Reddit pide esperar… ({espera + 20}s)")
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = ET.fromstring(r.content).find("a:entry", ns)
    titulo = e.findtext("a:title", "", ns)
    cuerpo = html.unescape(e.findtext("a:content", "", ns))
    cuerpo = re.sub(r"<!-- SC_OFF -->|<!-- SC_ON -->", "", cuerpo)
    cuerpo = re.sub(r"</p>|<br\s*/?>", "\n\n", cuerpo)
    cuerpo = re.sub(r"<[^>]+>", "", cuerpo)
    cuerpo = re.sub(r"\s*submitted by.*$", "", cuerpo, flags=re.S).strip()
    return sub, titulo, html.unescape(cuerpo), None

def leer_post(url):
    """Devuelve (subreddit, título, texto) del post, sin comentarios. Prueba varias rutas."""
    url = url.strip()
    local = ROOT / url
    if url.lower().endswith(".txt") and local.exists():      # texto pegado a mano: posts/mi_post.txt
        t = local.read_text(encoding="utf-8-sig").strip().split("\n", 1)
        return "", t[0], t[1] if len(t) > 1 else t[0]
    if "/s/" in url:  # links cortos para compartir
        url = requests.get(url, headers=BROWSER_UA, timeout=30, allow_redirects=True).url
    pid = post_id(url)
    if not pid:
        raise ValueError("no es un link de post (debe contener /comments/)")
    errores = []
    for nombre, fn in (("oauth", lambda: _via_oauth(pid)), ("json", lambda: _via_json(pid)),
                       ("rss", lambda: _via_rss(url, pid))):
        try:
            sub, titulo, texto, removido = fn()
        except Exception as e:
            errores.append(f"{nombre}: {e}"); continue
        if removido or texto.strip() in ("[removed]", "[deleted]"):
            raise ValueError("el post fue eliminado")
        if not texto.strip():
            raise ValueError("el post no tiene texto (¿es solo imagen o link?)")
        print(f"  (leído vía {nombre})")
        return sub, titulo, texto
    raise RuntimeError("Reddit bloqueó la lectura → " + " | ".join(errores) +
                       ". Solución: agrega claves de Reddit (README) o pega el texto en posts\\x.txt y pon esa ruta en links.txt")

def slug(t):
    t = re.sub(r"[^\w\s-]", "", t.lower())
    return re.sub(r"\s+", "_", t).strip("_")[:40] or "historia"

def main(lista):
    import guion
    # utf-8-sig quita el BOM si lo hay: PowerShell (Set-Content -Encoding UTF8) y el Bloc de
    # notas lo anaden al guardar, y un BOM al principio del primer link lo dejaba inservible.
    links = [l.strip() for l in Path(lista).read_text(encoding="utf-8-sig").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not links:
        sys.exit(f"{lista} está vacío: pega un link de Reddit por línea.")
    print(f"{len(links)} links\n")
    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    (ROOT / "posts").mkdir(exist_ok=True)
    out = ROOT / "salida" / "registros" / f"lote_{fecha}.txt"; out.parent.mkdir(parents=True, exist_ok=True)
    resumen = []

    def guardar():
        # Se reescribe tras CADA item. Antes se escribia solo al final del bucle, asi que un
        # Ctrl+C o un fallo previo (import, links.txt inexistente) no dejaban ningun registro.
        out.write_text("\n".join(resumen), encoding="utf-8")

    try:
        for i, url in enumerate(links, 1):
            print(f"=== [{i}/{len(links)}] {url}")
            try:
                sub, titulo, texto = leer_post(url)
                pid = post_id(url)
                # Nombre determinista por publicacion: reejecutar sobrescribe A PROPOSITO en vez
                # de duplicar. cogia la fecha con resolucion de minuto, asi que dos corridas en
                # el mismo minuto con el mismo indice se pisaban en silencio.
                # El fallback cubre el texto pegado a mano (posts\x.txt), que no tiene id.
                name = f"{pid}_{slug(titulo)}" if pid else f"{fecha}_{i:02d}_{slug(titulo)}"
                (ROOT / "posts" / f"{name}.txt").write_text(f"{titulo}\n\n{texto}\n\n{url}", encoding="utf-8")
                print(f"  r/{sub}: {titulo}  ({len(texto.split())} palabras)")
                material = f"r/{sub}\nTÍTULO: {titulo}\n\n{texto}"
                js = guion.generar(material, name)
                actual = json.loads(js.read_text(encoding="utf-8"))
                if guion.palabras_habladas(actual) < 135:
                    js = guion.ampliar_si_corto(js, material)
                cfg = json.loads(js.read_text(encoding="utf-8"))
                cfg["fuente_reddit"] = url
                js.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                # mismo proceso para todo el lote: Chatterbox, Whisper y CLIP se cargan UNA sola vez
                import make_short
                try:
                    make_short.main(str(js))
                except SystemExit as e:
                    raise RuntimeError(f"make_short falló: {e}")
                resumen.append(f"OK    {name}.mp4  |  {cfg.get('titulo', '')}  |  {url}")
            except Exception as e:
                print("  ✗", e)
                resumen.append(f"FALLÓ {url}  →  {e}")
            guardar()
            if i < len(links):
                time.sleep(15)  # pausa ENTRE posts para que Reddit no bloquee (no tras el ultimo)
    finally:
        guardar()
    print("\n" + "\n".join(resumen) + f"\n\nResumen guardado en {out}")

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "links.txt")
