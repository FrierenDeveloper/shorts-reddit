"""
Convierte un post de Reddit (texto) en historias/<nombre>.json usando un LLM local o barato.

Uso:  python guion.py post.txt mi_historia
Por defecto usa LM Studio (http://localhost:1234/v1). Para otro proveedor compatible con OpenAI:
  $env:LLM_BASE_URL="https://api.deepseek.com"; $env:LLM_API_KEY="tu_clave"; $env:LLM_MODEL="deepseek-chat"
  (OpenCode Go NO sirve tal cual: su endpoint /zen/go/v1 exige la cabecera x-opencode-session,
   que este cliente no envia; responde 400 MissingSessionID. Ver REVISION_IA.md, hallazgo I9.)
  (Ollama: LLM_BASE_URL=http://localhost:11434/v1  LLM_MODEL=qwen2.5:14b)
"""
import json, os, re, sys
from pathlib import Path
from openai import OpenAI

# Mismo blindaje que make_short.py: los avisos de este módulo llevan ≈, ⚠ y → y una consola
# Windows en cp1252 reventaba con UnicodeEncodeError al imprimirlos (detectado al probar
# _guardar). El guion ya estaba escrito en disco, pero la excepción cortaba el proceso.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).resolve().parent
ROOT = APP.parent

def _system():
    """Permite elegir otro prompt de sistema (p. ej. salud mental) con SHORTS_PROMPT=prompt_guion_salud_mental.md.
    Se lee en cada llamada (no al importar) para que interfaz.py pueda cambiarlo por video."""
    f = APP / (os.getenv("SHORTS_PROMPT") or "prompt_guion.md")
    return f.read_text(encoding="utf-8") if f.exists() else (APP / "prompt_guion.md").read_text(encoding="utf-8")

def main(post_file, name):
    return generar(Path(post_file).read_text(encoding="utf-8"), name)

def _cfg():
    f = ROOT / "config" / "llm.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

def proveedor():
    """Usa el endpoint OpenAI compatible de LM Studio o el proveedor definido en llm.json."""
    return "api"

def _llm():
    """Config desde llm.json (si existe) o variables de entorno. Por defecto, LM Studio local."""
    c = _cfg()
    return (c.get("base_url") or os.getenv("LLM_BASE_URL", "http://localhost:1234/v1"),
            c.get("api_key") or os.getenv("LLM_API_KEY", "lm-studio"),
            c.get("modelo") or os.getenv("LLM_MODEL"))

def generar(post, name):
    user = "POST DE REDDIT:\n\n" + post + "\n\nDevuelve SOLO el JSON."
    txt = _api(user)
    return _guardar(txt, name)

def palabras_habladas(data):
    """Cuenta el texto que realmente se narrará, no solo los subtítulos visibles."""
    return sum(len((e.get("hablado") or e.get("texto", "")).replace("*", "").split())
               for e in data.get("escenas", []))

def ampliar_si_corto(path, material, minimo=185):
    """Hace una única pasada de ampliación cuando el guion no alcanza el mínimo hablado.

    El mínimo está CALIBRADO con la velocidad real del TTS de este canal: 3,36 palabras por
    segundo de habla pura (medido sobre 18 pares guion<->mp4 de salida\\Reddit, rango
    3,10-3,69). Antes valía 135, heredado de una voz mucho más lenta: un guion de 135 palabras
    dura ~44 s y el render lo RECHAZA por corto, así que se gastaba una llamada al LLM de más."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    palabras = palabras_habladas(data)
    if palabras >= minimo:
        return path
    print(f"Guion corto ({palabras} palabras habladas); ampliando antes de sintetizar la voz…")
    user = (
        "AMPLÍA ESTE GUION CORTO PARA QUE TENGA ENTRE 195 Y 205 PALABRAS HABLADAS Y DURE ENTRE 62 Y 68 SEGUNDOS. "
        "Devuelve el JSON completo, conservando exactamente su estructura y el gancho inicial. "
        "Reparte el desarrollo adicional en escenas cortas y narrables; conserva el cierre y no añadas relleno. "
        "El diálogo debe ser un monólogo continuo de oraciones completas: enlaza cada escena, evita frases sueltas o poéticas y mantén el foco de la descripción.\n\n"
        "REGLAS DE FIDELIDAD: usa solo hechos incluidos en el material original y el guion. "
        "No inventes eventos, diálogos, pensamientos, nombres, cifras, estudios ni desenlaces. "
        "Si hay pocos hechos, desarrolla el contexto ya dado, las reacciones expresadas y los matices "
        "sin presentar inferencias como hechos. En contenido educativo, mantén las cautelas de evidencia "
        "y no diagnostiques a nadie.\n\n"
        f"MATERIAL ORIGINAL:\n{material}\n\n"
        f"GUION ACTUAL ({palabras} palabras habladas):\n{json.dumps(data, ensure_ascii=False, indent=2)}\n\n"
        "Devuelve SOLO el JSON válido, sin Markdown ni explicaciones."
    )
    txt = _api(user)
    return _guardar(txt, path.stem)

def ajustar_duracion(path, duracion):
    """Reescribe el guion conservando su configuración para corregir el tiempo medido por TTS."""
    path = Path(path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    palabras = palabras_habladas(cfg)
    categoria = cfg.get("categoria_video")
    if categoria not in ("reddit", "salud_mental", "psicologia_diaria"):
        categoria = "salud_mental" if cfg.get("plantilla") == "tetrica" else "reddit"
    fuente = ROOT / "posts" / f"{path.stem}.txt"
    material = fuente.read_text(encoding="utf-8") if fuente.exists() else (
        f"TEMA: {cfg.get('titulo', '')}\n{cfg.get('descripcion', '')}"
    )
    direccion = "AMPLÍA" if duracion < 60 else "RECORTA"
    user = (
        f"{direccion} el guion para que su duración narrada medida quede entre 62 y 68 segundos. "
        f"El intento anterior duró {duracion:.1f} segundos con {palabras} palabras habladas. "
        "Ajusta la cantidad de narración de forma proporcional a ese resultado; no agregues pausas para falsear la duración. "
        "Mantén un monólogo conectado de oraciones naturales y completas; no lo conviertas en palabras o frases sueltas, poéticas o inconexas. "
        "Conserva el gancho, los hechos centrales, el cierre y cualquier pregunta de serie obligatoria. "
        "No inventes hechos, ejemplos presentados como reales, estudios, cifras ni diagnósticos. "
        "Si es Reddit, respeta exclusivamente la fuente. Si es educativo, conserva los matices y límites de evidencia. "
        "Devuelve el JSON completo con la misma estructura.\n\n"
        f"MATERIAL DE REFERENCIA:\n{material}\n\n"
        f"GUION ACTUAL:\n{json.dumps(cfg, ensure_ascii=False, indent=2)}\n\n"
        "Devuelve SOLO JSON válido, sin Markdown ni explicaciones."
    )
    prompt_por_categoria = {
        "salud_mental": "prompt_guion_salud_mental.md",
        "psicologia_diaria": "prompt_guion_psicologia_diaria.md",
        "reddit": "prompt_guion.md",
    }
    clave = "SHORTS_PROMPT"
    anterior = os.environ.get(clave)
    os.environ[clave] = prompt_por_categoria.get(categoria, "prompt_guion.md")
    try:
        ajustado = _guardar(_api(user), path.stem)
    finally:
        if anterior is None:
            os.environ.pop(clave, None)
        else:
            os.environ[clave] = anterior
    nuevo = json.loads(ajustado.read_text(encoding="utf-8"))
    cfg.update(nuevo)  # retiene categoría, extras, voces, plantilla y demás opciones del usuario
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def _api(user):
    base, key, model = _llm()
    cli = OpenAI(base_url=base, api_key=key)
    msgs = [{"role": "system", "content": _system()}, {"role": "user", "content": user}]
    try:
        model = model or cli.models.list().data[0].id
        print("Modelo:", model)
        r = cli.chat.completions.create(model=model, temperature=0.7, messages=msgs)
    except Exception as e:
        if "model" not in str(e).lower():
            raise
        # nombre de modelo inválido: mostrar los disponibles y elegir uno de DeepSeek automáticamente
        ids = [m.id for m in cli.models.list().data]
        print(f"  ⚠ El modelo '{model}' no existe aquí. Disponibles: {', '.join(ids)}")
        pref = [i for i in ids if "deepseek" in i.lower() and not re.search(r"r1|reason|think", i, re.I)] \
            or [i for i in ids if "deepseek" in i.lower()] or ids
        model = pref[0]
        print(f"  → usando '{model}' (cámbialo en llm.json para no ver este aviso)")
        r = cli.chat.completions.create(model=model, temperature=0.7, messages=msgs)
    return r.choices[0].message.content or ""

def _validar_guion(data):
    """Comprueba lo imprescindible ANTES de escribir el guion en disco.

    El JSON lo genera un LLM y el usuario lo edita a mano, asi que la validacion es
    permisiva a proposito: no rechaza variaciones legitimas de forma, solo lo que
    reventaria el render o dejaria un guion invalido en historias\\."""
    if not isinstance(data, dict):
        raise ValueError("La IA no devolvió un objeto JSON (¿una lista o texto suelto?).")
    escenas = data.get("escenas")
    if not isinstance(escenas, list) or not escenas:
        raise ValueError("El guion no trae 'escenas', o viene vacía.")
    for i, e in enumerate(escenas, 1):
        if not isinstance(e, dict) or not str(e.get("texto") or "").strip():
            raise ValueError(f"La escena {i} no tiene 'texto' utilizable.")


def _guardar(txt, name):
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    txt = re.sub(r"```(?:json)?", "", txt)   # modelos que "piensan" (DeepSeek R1, Qwen3)
    txt = re.sub(r"^.*?(\{)", r"\1", txt, flags=re.S)
    txt = txt[: txt.rfind("}") + 1]
    try:
        data = json.loads(txt)
    except json.JSONDecodeError as e:
        lineas = txt.splitlines()
        fragmento = lineas[e.lineno - 1].strip() if e.lineno <= len(lineas) else ""
        raise ValueError(
            f"La IA devolvió JSON inválido (línea {e.lineno}, columna {e.colno}: {e.msg}). "
            f"Revisa esta parte de la respuesta: {fragmento[:180]!r}"
        ) from e
    _validar_guion(data)      # antes de escribir: si falla, no queda un guion roto en historias\
    # Red de seguridad de retención: si el LLM omite "extras", el vídeo sale plano y mudo
    # (zoom y sonidos son los que dan ritmo). Se rellenan los que falten; si el guion los trae
    # explícitamente en false se respetan, pero se avisa.
    ex = data.setdefault("extras", {})
    if isinstance(ex, dict):
        for k in ("tarjeta", "barra", "karaoke", "encuesta", "zoom", "sonidos", "loop"):
            ex.setdefault(k, True)
        if ex.get("zoom") is False or ex.get("sonidos") is False:
            print("   ⚠ zoom/sonidos están en false en este guion: el vídeo saldrá más plano y mudo.")
    # La tarjeta estilo post saca el subreddit de `fuente_reddit`. Si el guion no lo trae,
    # make_short cae a "r/AmItheAsshole": una historia de r/JUSTNOFAMILY acabó mostrando la
    # tarjeta de AITA. Aviso para detectarlo antes de renderizar — pero SOLO si la tarjeta
    # está encendida: en los formatos educativos (salud mental, psicología) va apagada.
    if (isinstance(ex, dict) and ex.get("tarjeta", True)
            and not data.get("subreddit") and not data.get("fuente_reddit")):
        print("   ⚠ El guion no trae 'subreddit' ni 'fuente_reddit': la tarjeta usará "
              "r/AmItheAsshole por defecto. Añádelo si la historia viene de otro subreddit.")
    out = ROOT / "historias" / f"{name}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    escenas = data.get("escenas") or []
    palabras = sum(len((e.get("texto") or "").split()) for e in escenas)
    # 3.36 palabras/s = velocidad REAL medida del TTS (antes 2.6, que la subestimaba un 29 % y
    # hacía creer que un guion corto duraba lo suficiente).
    # La duración total = habla + PAUSAS. Sin sumar las pausas la estimación se quedaba ~6 s
    # corta y avisaba en falso de que 195 palabras no llegaban al mínimo (medido: 201 palabras
    # dieron 66.2 s reales, de los cuales 6.8 s eran pausas).
    pausas = sum(float(e.get("pausa") or 0) for e in escenas)
    est = palabras / 3.36 + pausas
    print(f"Guardado {out}  ({len(escenas)} escenas, ~{palabras} palabras ≈ {est:.0f}s "
          f"= {palabras / 3.36:.0f}s de voz + {pausas:.1f}s de pausas)")
    if est < 60:
        print(f"   ⚠ Duraría ~{est:.0f}s: POR DEBAJO del mínimo de 60 s que exige el render. "
              f"Apunta a 190-200 palabras.")
    elif est > 70:
        print(f"   ⚠ Duraría ~{est:.0f}s: por encima del máximo de 70 s. Recorta hacia 190-200 palabras.")
    print("Revísalo y luego: arrástralo sobre CREAR_SHORT.bat")
    return out

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
