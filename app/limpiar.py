"""Limpieza del proyecto. Uso: LIMPIAR.bat (o python app/limpiar.py [--si])

Siempre borra (sin preguntar):
  - cache\\            imágenes y miniaturas descargadas
  - __pycache__         archivos compilados del PROYECTO (no los de .venv*)
  - temporales del sistema de este programa (*_mix.wav, cb_*)
Pregunta antes de borrar:
  - salida\\subidos\\  videos que YA publicaste y moviste ahí, con más de 7 días
  - salida\\registros\\ registros de lotes con más de 30 días
  - historias\\ y posts\\ con más de 60 días
Nunca toca: salida\\ (videos sin publicar), config\\, musica\\, voces\\, app\\, .venv*\\.
"""
import os, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIA = 86400

# Directorios que no se recorren nunca: entornos virtuales (bytecode de las dependencias,
# no cache del proyecto) y metadatos de control de versiones / del kit de revision.
EXCLUIDOS = {".venv", ".venv_cb", "venv", ".git", ".revision", "node_modules"}


def tam(p):
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) if Path(p).exists() else 0


def borrar(p):
    try:
        shutil.rmtree(p) if Path(p).is_dir() else Path(p).unlink()
        return True
    except OSError:
        return False


def pycaches():
    """__pycache__ del proyecto, podando EXCLUIDOS.

    Antes se hacía ROOT.rglob("__pycache__"), que entraba en .venv* y borraba unos 4200
    directorios de bytecode de las dependencias instaladas: no es lo que el usuario espera
    de "limpiar caché" y obliga a recompilarlas enteras en el siguiente arranque."""
    res = []
    for raiz, dirs, _ in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUIDOS]
        if os.path.basename(raiz) == "__pycache__":
            res.append(Path(raiz))
            dirs[:] = []                       # no bajar dentro del propio __pycache__
    return res


def viejos(carpeta, dias, patron="*", recursivo=False):
    lim = time.time() - dias * DIA
    p = Path(carpeta)
    fs = p.rglob(patron) if recursivo else p.glob(patron)
    return [f for f in fs if f.is_file() and f.stat().st_mtime < lim] if p.exists() else []


def main(auto_si=False, solo_cache=False):
    liberado = 0
    fallidos = 0
    # 1) automático
    auto = [ROOT / "cache"] + pycaches()
    tmp = Path(tempfile.gettempdir())
    auto += list(tmp.glob("*_mix.wav")) + list(tmp.glob("cb_*"))
    auto += [ROOT / "cache_imagenes", ROOT / "_revision"]            # restos de versiones anteriores
    for p in auto:
        if not Path(p).exists():
            continue
        n = tam(p) if Path(p).is_dir() else Path(p).stat().st_size
        # Se suma SOLO si el borrado tuvo exito: antes se contaba antes de borrar y borrar()
        # se tragaba los OSError, asi que podia anunciar MB liberados sin haber borrado nada.
        if borrar(p):
            liberado += n
        else:
            fallidos += 1
    aviso = f" ({fallidos} no se pudieron borrar, probablemente en uso)" if fallidos else ""
    print(f"Caché y temporales: {liberado / 1e6:.1f} MB liberados{aviso}")
    if solo_cache:
        return

    # 2) con confirmación
    grupos = [
        ("videos ya publicados (salida\\subidos, +7 días)", viejos(ROOT / "salida" / "subidos", 7, recursivo=True)),
        ("registros de lotes (+30 días)", viejos(ROOT / "salida" / "registros", 30)),
        ("guiones (historias, +60 días)", viejos(ROOT / "historias", 60, "*.json")),
        ("textos originales (posts, +60 días)", viejos(ROOT / "posts", 60, "*.txt")),
    ]
    for nombre, archivos in grupos:
        if not archivos:
            continue
        mb = sum(f.stat().st_size for f in archivos) / 1e6
        r = "s" if auto_si else input(f"¿Borrar {len(archivos)} {nombre}, {mb:.1f} MB? (s/n): ").strip().lower()
        if r.startswith("s"):
            for f in archivos:
                borrar(f)
            print(f"  borrados {len(archivos)}")
    pend = [f for f in (ROOT / "salida").rglob("*.mp4") if "subidos" not in f.relative_to(ROOT / "salida").parts]
    if pend:
        print(f"\nTienes {len(pend)} videos sin publicar en salida\\Reddit\\ y salida\\Salud_Mental\\. Cuando los subas, muévelos (con sus .txt) a salida\\subidos\\.")
    print("Listo.")


if __name__ == "__main__":
    main("--si" in sys.argv, "--solo-cache" in sys.argv)
