"""Interfaz visual del generador de Shorts. Se abre en el navegador (todo corre local).
Uso: ABRIR_APP.bat   (o: .venv\\Scripts\\python.exe app\\interfaz.py)"""
import datetime, json, os, re, shutil, subprocess, sys
from pathlib import Path

import gradio as gr

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))
import plantillas  # noqa: E402

DESCRIPCION_PLANTILLAS = {
    "aleatoria": "Una distinta por video (reduce el riesgo de 'contenido repetitivo').",
    "clasica": "Poppins · amarillo/verde · cálida · música pad suave.",
    "impacto": "Anton en MAYÚSCULAS · 2–3 palabras por pantalla · ritmo rápido · lo-fi.",
    "noche": "Montserrat · neón cian/magenta · subtítulos abajo · synth.",
    "diario": "Serif Lora · sepia · entrada lenta · piano.",
    "pop": "Archivo Black · texto en cajas · colores vivos · caja de música.",
    "tetrica": "Subtítulos abajo · tonos fríos y oscuros · música ambiental inquietante.",
}
# Categorías: cada flujo preselecciona una plantilla visual adecuada.
CATEGORIAS = {
    "Historias de Reddit": dict(plantilla="aleatoria", prompt="prompt_guion.md"),
    "Salud mental": dict(plantilla="tetrica", prompt="prompt_guion_salud_mental.md"),
    "Psicología de la vida diaria": dict(plantilla="impacto", prompt="prompt_guion_psicologia_diaria.md"),
}
# Sugerencias de "tendencia": patologías/temas con buen volumen de búsqueda y suficiente material
# educativo real para no inventar datos. Edítalas libremente; son solo un punto de partida.
SUGERENCIAS_SALUD_MENTAL = [
    "Trastorno límite de la personalidad (TLP)", "TDAH en adultos", "Ansiedad social",
    "Trastorno obsesivo-compulsivo (TOC)", "Depresión de alto funcionamiento", "Trastorno bipolar",
    "Trastorno de estrés postraumático (TEPT)", "Alexitimia", "Trastorno de despersonalización-desrealización",
    "Trastorno dismórfico corporal", "Misofonía", "Tricotilomanía", "Trastorno de acumulación (hoarding)",
    "Fobia social vs. timidez", "Burnout / síndrome del trabajador quemado",
]
SUGERENCIAS_PSICOLOGIA = [
    "Sesgo de confirmación en conversaciones cotidianas",
    "Por qué recordamos mejor lo último que pasó",
    "Cómo los recuerdos cambian con el tiempo",
    "Efecto de anclaje al comparar precios",
    "El costo hundido y las decisiones difíciles",
    "Por qué imitamos decisiones de otras personas",
    "Cómo influye el contexto en lo que elegimos",
    "La ilusión de frecuencia: cuando algo parece aparecer en todas partes",
]
VOCES = {"Automática (según la historia)": None,
         "Mujer · México (Dalia)": "es-MX-DaliaNeural", "Hombre · México (Jorge)": "es-MX-JorgeNeural",
         "Mujer · Colombia (Salomé)": "es-CO-SalomeNeural", "Hombre · EE.UU. latino (Alonso)": "es-US-AlonsoNeural",
         "Mujer · Argentina (Elena)": "es-AR-ElenaNeural"}
EXTRAS = ["Tarjeta estilo post", "Barra de progreso", "Palabra actual (karaoke)", "Encuesta final",
          "Zoom en los giros", "Efectos de sonido", "Final en loop"]
EXTRAS_KEY = dict(zip(EXTRAS, ["tarjeta", "barra", "karaoke", "encuesta", "zoom", "sonidos", "loop"]))
EDICIONES_POR_CATEGORIA = {
    "Historias de Reddit": (EXTRAS, EXTRAS),
    "Salud mental": (
        ["Barra de progreso", "Palabra actual (karaoke)", "Zoom en los giros", "Efectos de sonido"],
        ["Barra de progreso", "Palabra actual (karaoke)", "Zoom en los giros", "Efectos de sonido"],
    ),
    "Psicología de la vida diaria": (
        ["Barra de progreso", "Palabra actual (karaoke)", "Encuesta final", "Zoom en los giros"],
        ["Barra de progreso", "Palabra actual (karaoke)", "Encuesta final", "Zoom en los giros"],
    ),
}


# ------------------------------------------------------------------ utilidades
def _py():
    return sys.executable


def _slug(t):
    t = re.sub(r"[^\w\s-]", "", t.lower())
    return re.sub(r"\s+", "_", t).strip("_")[:40] or "historia"


def _categoria_guion(nombre):
    if not nombre:
        return "Historias de Reddit"
    cfg = json.loads((ROOT / "historias" / nombre).read_text(encoding="utf-8"))
    categoria = cfg.get("categoria_video")
    return {
        "reddit": "Historias de Reddit",
        "salud_mental": "Salud mental",
        "psicologia_diaria": "Psicología de la vida diaria",
    }.get(categoria, "Salud mental" if cfg.get("plantilla") == "tetrica" else "Historias de Reddit")


def _ediciones_guion(nombre):
    categoria = _categoria_guion(nombre)
    opciones, predeterminadas = EDICIONES_POR_CATEGORIA[categoria]
    if not nombre:
        seleccionadas = predeterminadas
    else:
        cfg = json.loads((ROOT / "historias" / nombre).read_text(encoding="utf-8"))
        extras = cfg.get("extras", {})
        seleccionadas = [opcion for opcion in opciones
                         if extras.get(EXTRAS_KEY[opcion], opcion in predeterminadas)]
    return gr.update(choices=opciones, value=seleccionadas)


def _entradas_generacion(categoria, links, texto, patologia, tema_psicologia):
    if categoria in ("Salud mental", "Psicología de la vida diaria"):
        # Ignorar links/texto Reddit que pueden seguir guardados aunque sus
        # controles estén ocultos; esta pestaña recibe únicamente temas.
        texto_temas = tema_psicologia if categoria == "Psicología de la vida diaria" else patologia
        return [("__tema__", t.strip()) for t in (texto_temas or "").splitlines() if t.strip()]
    entradas = [l.strip() for l in (links or "").splitlines() if l.strip() and not l.strip().startswith("#")]
    if texto and texto.strip():
        entradas.append(("__texto__", texto.strip()))
    return entradas


def _aplicar_opciones(js, plantilla, voz, extras, volumen, fondo_satisfactorio=None):
    cfg = json.loads(Path(js).read_text(encoding="utf-8"))
    cfg["plantilla"] = plantilla
    if VOCES.get(voz):
        cfg["voz"] = VOCES[voz]
    cfg.pop("voz_elevenlabs", None)
    if cfg.get("motor_voz") == "elevenlabs":
        cfg.pop("motor_voz", None)
    if cfg.get("categoria_video") == "salud_mental":
        cfg["aviso"] = ""
    cfg["extras"] = {k: (nombre in extras) for nombre, k in EXTRAS_KEY.items()}
    cfg["volumen_musica"] = volumen
    if fondo_satisfactorio is not None:
        cfg["fondo_satisfactorio"] = bool(fondo_satisfactorio)
    Path(js).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def _motor_id(motor):
    """Etiqueta del radio de la GUI -> valor interno que entiende make_short.motor_actual.

    motor puede llegar como None si el control no se ha tocado nunca."""
    return "chatterbox" if str(motor or "").startswith("Chatterbox") else "edge"


def _render(js, motor, log):
    """Ejecuta make_short.py (uno o varios JSON en un solo proceso) y va devolviendo el log en vivo."""
    js = js if isinstance(js, list) else [js]
    # SHORTS_MOTOR_VOZ tiene PRIORIDAD sobre el motor_voz del JSON (make_short.motor_actual).
    # Por eso se fija siempre y no solo para Chatterbox: si no, elegir "edge-tts" en la GUI
    # no anularia un motor_voz heredado del entorno ni un kokoro/xtts del guion.
    # Se fija como variable de entorno en vez de escribirlo en el JSON para no destruir un
    # valor (kokoro/xtts) que la interfaz no puede volver a poner.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               SHORTS_MOTOR_VOZ=_motor_id(motor))
    p = subprocess.Popen([_py(), str(APP / "make_short.py"), *map(str, js)], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        for parte in line.replace("\r", "\n").split("\n"):
            parte = parte.rstrip()
            if parte and not re.search(r"FutureWarning|deprecat|warn\(|HF_TOKEN|huggingface_hub|output_attentions|self\.gen", parte):
                log.append(parte)
                yield
    p.wait()
    if p.returncode != 0:
        raise RuntimeError("el render falló (revisa el registro)")


def _salida(js):
    name = Path(js).stem
    cfg = json.loads(Path(js).read_text(encoding="utf-8"))
    categoria = cfg.get("categoria_video")
    if categoria not in ("reddit", "salud_mental", "psicologia_diaria"):
        categoria = "salud_mental" if cfg.get("plantilla") == "tetrica" else "reddit"
    carpeta = {"salud_mental": "Salud_Mental", "psicologia_diaria": "Psicologia_Diaria"}.get(categoria, "Reddit")
    mp4 = ROOT / "salida" / carpeta / f"{name}.mp4"
    desc = mp4.with_name(f"{name}_descripcion.txt")
    # Compatibilidad con videos viejos que aún estén en la raíz.
    if not mp4.exists():
        mp4 = ROOT / "salida" / f"{name}.mp4"
        desc = mp4.with_name(f"{name}_descripcion.txt")
    return (str(mp4) if mp4.exists() else None), (desc.read_text(encoding="utf-8") if desc.exists() else "")


# ------------------------------------------------------------------ acciones
def generar(links, texto, patologia, tema_psicologia, categoria, plantilla, motor, voz, extras, volumen,
            fondo_satisfactorio=True, fuente_videos="Pixabay",
            progress=gr.Progress(track_tqdm=False)):
    """Link(s), texto o patología(s) → guiones (IA) → videos (todos en un solo render). Actualiza la pantalla en vivo."""
    import guion, lote
    os.environ["SHORTS_LLM"] = "api"
    os.environ["SHORTS_PROMPT"] = CATEGORIAS.get(categoria, CATEGORIAS["Historias de Reddit"])["prompt"]
    log, video, desc = [], None, ""
    entradas = _entradas_generacion(categoria, links, texto, patologia, tema_psicologia)
    if not entradas:
        yield "Escribe un tema, pega un link de Reddit o el texto de un post.", gr.skip(), gr.skip()
        return
    progress(0, desc="Preparando entradas")
    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    (ROOT / "posts").mkdir(exist_ok=True)
    guiones = []
    for i, e in enumerate(entradas, 1):
        try:
            progress(0.45 * (i - 1) / len(entradas), desc=f"Paso 1 de 2 · Preparando guion {i}/{len(entradas)}")
            if isinstance(e, tuple) and e[0] == "__tema__":
                titulo, cuerpo, sub, fuente = e[1][:120], e[1], "", ""
                log.append(f"=== [{i}/{len(entradas)}] tema: {e[1]}")
            elif isinstance(e, tuple):
                lineas = e[1].split("\n", 1)
                titulo, cuerpo, sub, fuente = lineas[0][:120], e[1], "", ""
                log.append(f"=== [{i}/{len(entradas)}] texto pegado")
            else:
                log.append(f"=== [{i}/{len(entradas)}] {e}"); yield "\n".join(log[-60:]), gr.skip(), gr.skip()
                progress(None, desc=f"Paso 1 de 2 · Leyendo publicación {i}/{len(entradas)}")
                sub, titulo, cuerpo = lote.leer_post(e); fuente = e
                log.append(f"Post leído: r/{sub} · {titulo}")
            yield "\n".join(log[-60:]), gr.skip(), gr.skip()
            name = f"{fecha}_{i:02d}_{_slug(titulo)}"
            (ROOT / "posts" / f"{name}.txt").write_text(f"{titulo}\n\n{cuerpo}\n\n{fuente}", encoding="utf-8")
            log.append("Escribiendo guion con el proveedor configurado…"); yield "\n".join(log[-60:]), gr.skip(), gr.skip()
            progress(None, desc=f"Paso 1 de 2 · Escribiendo guion {i}/{len(entradas)}")
            entrada_llm = f"TEMA: {titulo}" if isinstance(e, tuple) and e[0] == "__tema__" else f"r/{sub}\nTÍTULO: {titulo}\n\n{cuerpo}"
            js = guion.generar(entrada_llm, name)
            antes = json.loads(Path(js).read_text(encoding="utf-8"))
            palabras = guion.palabras_habladas(antes)
            if palabras < 135:
                log.append(f"Guion corto ({palabras} palabras); ampliándolo antes de generar la voz…")
                yield "\n".join(log[-60:]), gr.skip(), gr.skip()
                js = guion.ampliar_si_corto(js, entrada_llm)
            cfg = _aplicar_opciones(js, plantilla, voz, extras, volumen)
            cfg["categoria_video"] = {
                "Salud mental": "salud_mental",
                "Psicología de la vida diaria": "psicologia_diaria",
            }.get(categoria, "reddit")
            # En Reddit, el subreddit leído desde el post manda sobre cualquier
            # subreddit que el modelo haya incluido en el guion.
            if cfg["categoria_video"] == "reddit" and sub:
                cfg["subreddit"] = f"r/{sub.removeprefix('r/')}"
            if cfg["categoria_video"] == "salud_mental":
                cfg["aviso"] = ""
            cfg["fondo_satisfactorio"] = bool(fondo_satisfactorio)
            cfg["fuente_videos"] = {"Pixabay": "pixabay", "Pexels": "pexels"}.get(fuente_videos, "pixabay")
            if fuente:
                cfg["fuente_reddit"] = fuente
            Path(js).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            log.append(f"Guion listo: «{cfg.get('titulo', '')}» ({len(cfg['escenas'])} escenas)")
            guiones.append(js)
            progress(0.45 * i / len(entradas), desc=f"Paso 1 de 2 · Guiones listos {i}/{len(entradas)}")
        except Exception as ex:
            log.append(f"❌ Falló: {ex}")
        yield "\n".join(log[-60:]), gr.skip(), gr.skip()
    if not guiones:
        progress(1, desc="No se pudo crear ningún guion")
        yield "\n".join(log[-60:]), gr.skip(), gr.skip()
        return
    log.append(f"=== Renderizando {len(guiones)} video(s) en un solo proceso (modelos cargados una vez)")
    progress(0.5, desc=f"Paso 2 de 2 · Renderizando {len(guiones)} video(s)")
    try:
        for _ in _render(guiones, motor, log):
            progress(None, desc="Paso 2 de 2 · Renderizando video(s); consulta el registro para ver el detalle")
            yield "\n".join(log[-60:]), gr.skip(), gr.skip()
    except Exception as ex:
        log.append(f"❌ {ex}")
    hechos = [js for js in guiones if _salida(js)[0]]
    if hechos:
        video, desc = _salida(hechos[-1])
        carpeta = {"Salud mental": "Salud_Mental",
                   "Psicología de la vida diaria": "Psicologia_Diaria"}.get(categoria, "Reddit")
        log.append(f"✅ {len(hechos)}/{len(guiones)} video(s) listos en salida\\{carpeta}\\")
    progress(1, desc=f"Listo · {len(hechos)}/{len(guiones)} video(s) generados")
    yield "\n".join(log[-60:]), (desc if hechos else gr.skip()), (video if hechos else gr.skip())


def lista_historias():
    fs = sorted((ROOT / "historias").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [f.name for f in fs]


def _ruta_video(nombre):
    if not nombre:
        return gr.skip()
    out = (ROOT / "salida").resolve()
    video = (out / nombre).resolve()
    return str(video) if video.is_relative_to(out) and video.is_file() else gr.skip()


def _descripcion_video(nombre):
    ruta = _ruta_video(nombre)
    if not isinstance(ruta, str):
        return ""
    video = Path(ruta)
    desc = video.with_name(video.stem + "_descripcion.txt")
    return desc.read_text(encoding="utf-8") if desc.exists() else ""


def rerender(nombre, plantilla, motor, voz, extras, volumen, progress=gr.Progress(track_tqdm=False)):
    if not nombre:
        yield "Elige un guion de la lista.", gr.skip(), gr.skip()
        return
    js = ROOT / "historias" / nombre
    _aplicar_opciones(js, plantilla, voz, extras, volumen)
    progress(0.05, desc="Paso 1 de 2 · Guion listo; preparando render")
    log = [f"=== {nombre} (sin gastar IA: el guion ya existe)"]
    try:
        progress(None, desc="Paso 2 de 2 · Renderizando video")
        for _ in _render(js, motor, log):
            progress(None, desc="Paso 2 de 2 · Renderizando; consulta el registro para ver el detalle")
            yield "\n".join(log[-60:]), gr.skip(), gr.skip()
        v, d = _salida(js); log.append("✅ Listo")
        progress(1, desc="Listo · video generado")
        yield "\n".join(log[-60:]), d, v
    except Exception as ex:
        log.append(f"❌ {ex}"); yield "\n".join(log[-60:]), gr.skip(), gr.skip()


def ver_guion(nombre):
    if not nombre:
        return ""
    cfg = json.loads((ROOT / "historias" / nombre).read_text(encoding="utf-8"))
    lineas = [f"# {cfg.get('titulo', '')}", ""]
    for e in cfg.get("escenas", []):
        tag = " 🗣️ MI OPINIÓN" if e.get("tipo") == "opinion" else ""
        lineas.append(f"- {e['texto'].replace('*', '**')}{tag}")
    return "\n".join(lineas)


def lista_videos():
    out = ROOT / "salida"
    videos = [f for carpeta in ("Reddit", "Salud_Mental", "Psicologia_Diaria") for f in (out / carpeta).glob("*.mp4")]
    videos += list(out.glob("*.mp4"))  # los antiguos aparecen mientras se migran o no tienen guion
    return [str(f.relative_to(out)) for f in sorted(videos, key=lambda p: p.stat().st_mtime, reverse=True)]


def marcar_subido(nombre):
    if not nombre:
        return gr.update(), "Elige un video."
    out = (ROOT / "salida").resolve()
    video = (out / nombre).resolve()
    if not video.is_relative_to(out) or not video.is_file():
        return gr.update(), "No encontré ese video en sus carpetas."
    dest = out / "subidos" / video.parent.relative_to(out); dest.mkdir(parents=True, exist_ok=True)
    for f in video.parent.glob(f"{video.stem}*"):
        if f.is_file():
            shutil.move(str(f), str(dest / f.name))
    return gr.update(choices=lista_videos(), value=None), f"Movido a {dest.relative_to(ROOT)}: {video.name}"


def limpiar():
    # Con timeout: sin el, un recorrido lento (o un fichero bloqueado) congelaba la interfaz
    # entera, porque es una llamada sincrona dentro del evento.
    try:
        r = subprocess.run([_py(), str(APP / "limpiar.py"), "--solo-cache"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return "La limpieza tardó más de 5 minutos y se canceló. Prueba LIMPIAR.bat desde una consola."
    return (r.stdout or r.stderr).strip()


def abrir_carpeta():
    p = ROOT / "salida"
    if os.name == "nt":
        os.startfile(p)  # noqa
    return f"Abierta: {p}"


TEMA = gr.themes.Soft(primary_hue="violet", secondary_hue="rose", neutral_hue="slate", radius_size="lg")
CSS = """
.gradio-container {max-width: 1440px !important; width: calc(100% - 48px) !important; margin: auto}
#cabecera {text-align: center; margin-bottom: 4px}
#cabecera p {color: var(--body-text-color-subdued); margin-top: 0}
#cabecera h1 {font-size: 2rem; letter-spacing: -0.04em}
.step-title {margin: 8px 0 2px; color: var(--body-text-color)}
.step-hint {color: var(--body-text-color-subdued); margin-top: 0}
#resultado {border: 1px solid var(--border-color-primary); border-radius: 16px; padding: 12px}
#progreso textarea {font-family: var(--font-mono); font-size: 0.88rem}
footer {display: none !important}
"""


# ------------------------------------------------------------------ pantalla
def construir():
    opciones_pl = list(DESCRIPCION_PLANTILLAS)
    with gr.Blocks(title="Shorts Reddit", fill_width=True) as demo:
        gr.Markdown("# 🎬 Generador de Shorts\nCrea, revisa y organiza tus videos desde tu PC.",
                    elem_id="cabecera")

        with gr.Tabs():
            # ---------------------------------------------------- Nuevo
            with gr.Tab("✨ Nuevo"):
                gr.Markdown("### 1 · Elige el contenido", elem_classes=["step-title"])
                gr.Markdown("Elige una temática y completa su entrada.", elem_classes=["step-hint"])
                categoria = gr.State(list(CATEGORIAS)[0])
                with gr.Tabs():
                    with gr.Tab("📖 Historias de Reddit") as tab_reddit:
                        links = gr.Textbox(label="Link(s) de Reddit", lines=2,
                            placeholder="https://www.reddit.com/r/AmItheAsshole/comments/...\n(uno por línea para hacer varios)")
                        with gr.Accordion("…o pega el texto directamente (si Reddit bloquea la lectura)", open=False):
                            texto = gr.Textbox(label="Título en la 1ª línea, luego el texto", lines=6, show_label=False,
                                               placeholder="Título en la 1ª línea, luego el texto")
                    with gr.Tab("🧠 Salud mental") as tab_salud:
                        patologia = gr.Textbox(label="Patología o tema", lines=2,
                            placeholder="Escribe el nombre (uno por línea para hacer varios videos), o elige una sugerencia abajo ↓")
                        sugerencias = gr.Dropdown(SUGERENCIAS_SALUD_MENTAL, label="💡 Sugerencias en tendencia")
                    with gr.Tab("💭 Psicología cotidiana") as tab_psicologia:
                        tema_psicologia = gr.Textbox(label="Sesgo, recuerdo o decisión cotidiana", lines=2,
                            placeholder="Escribe un tema (uno por línea para hacer varios videos)")
                        sugerencias_psicologia = gr.Dropdown(SUGERENCIAS_PSICOLOGIA, label="💡 Ideas para empezar")

                fondo_satisfactorio = gr.Checkbox(value=True, label="Fondo satisfactorio aleatorio",
                    info="Tema y clips elegidos al azar; dos clips en 9:16, sin audio propio, mínimo 15 s y preferencia por 20 s o más.")
                fuente_videos = gr.Radio(["Pixabay", "Pexels"], value="Pixabay", label="Buscar clips en",
                    info="Se usa la clave ya guardada en config/claves.json; si falla, prueba la carpeta local.")
                enlace_pexels = gr.Markdown('[Videos proporcionados por Pexels](https://www.pexels.com/)', visible=False)
                fuente_videos.change(lambda f: gr.update(visible=f == "Pexels"), fuente_videos, enlace_pexels)

                gr.Markdown("### 2 · Personaliza el video", elem_classes=["step-title"])

                with gr.Accordion("⚙️ Opciones de guion, voz y estilo", open=False):
                    with gr.Row():
                        plantilla = gr.Dropdown(opciones_pl, value="aleatoria", label="Plantilla visual")
                        motor = gr.Radio(["edge-tts (rápida, online)", "Chatterbox (local, GPU, clona voces)"],
                                         value="edge-tts (rápida, online)", label="Motor de voz")
                    info_pl = gr.Markdown(DESCRIPCION_PLANTILLAS["aleatoria"])
                    with gr.Row():
                        voz = gr.Dropdown(list(VOCES), value=list(VOCES)[0], label="Voz del narrador (Edge TTS)")
                        volumen = gr.Slider(0, 2, value=1.0, step=0.1, label="Volumen de la música")
                    gr.Markdown("El guion usa el proveedor configurado en `config/llm.json` (LM Studio local o API compatible).")
                    ediciones_opciones, ediciones_predeterminadas = EDICIONES_POR_CATEGORIA["Historias de Reddit"]
                    extras = gr.CheckboxGroup(ediciones_opciones, value=ediciones_predeterminadas,
                                              label="Ediciones disponibles para esta temática")
                gr.Markdown("### 3 · Genera y revisa", elem_classes=["step-title"])
                btn = gr.Button("🚀 Crear guion y video", variant="primary", size="lg")

            # ---------------------------------------------------- Re-render
            with gr.Tab("🔁 Re-renderizar"):
                gr.Markdown("### 1 · Elige un guion", elem_classes=["step-title"])
                with gr.Row():
                    hist = gr.Dropdown(lista_historias(), label="Guion (historias\\)", scale=4)
                    ref_h = gr.Button("🔄", scale=0, min_width=60)
                prev = gr.Markdown(label="Vista previa del guion")
                gr.Markdown("### 2 · Renderiza con las opciones actuales", elem_classes=["step-title"])
                btn2 = gr.Button("🎬 Renderizar video", variant="primary", size="lg")

            # ---------------------------------------------------- Videos
            with gr.Tab("📁 Mis videos"):
                gr.Markdown("### Tu biblioteca", elem_classes=["step-title"])
                gr.Markdown("Selecciona un video para verlo y copiar su descripción.", elem_classes=["step-hint"])
                with gr.Row():
                    vids = gr.Dropdown(lista_videos(), label="Videos sin publicar · Reddit / Salud_Mental / Psicologia_Diaria", scale=4)
                    ref_v = gr.Button("🔄", scale=0, min_width=60)
                with gr.Row():
                    b_sub = gr.Button("✅ Marcar como subido")
                    b_carp = gr.Button("📂 Abrir carpeta")
                    b_lim = gr.Button("🧹 Limpiar caché")
                estado = gr.Textbox(label="Estado", lines=2)

        with gr.Group(elem_id="resultado"):
            gr.Markdown("## Resultado y progreso")
            with gr.Row():
                with gr.Column(scale=3):
                    log = gr.Textbox(label="Registro por etapas", lines=12, max_lines=16, autoscroll=True,
                                     elem_id="progreso", placeholder="Aquí aparecerá el avance: lectura, guion y render.")
                with gr.Column(scale=2):
                    video = gr.Video(label="Vista previa del Short", height=420, interactive=False)
                    video_pendiente = gr.State(None)
            desc = gr.Textbox(label="Descripción para publicar", lines=5, buttons=["copy"],
                              placeholder="La descripción aparecerá al terminar el video.")

        def _cambio_categoria(cat):
            opciones, predeterminadas = EDICIONES_POR_CATEGORIA[cat]
            return (cat, CATEGORIAS.get(cat, {}).get("plantilla", "aleatoria"),
                    gr.update(choices=opciones, value=predeterminadas))
        tab_reddit.select(lambda: _cambio_categoria("Historias de Reddit"), None,
                          [categoria, plantilla, extras])
        tab_salud.select(lambda: _cambio_categoria("Salud mental"), None,
                         [categoria, plantilla, extras])
        tab_psicologia.select(lambda: _cambio_categoria("Psicología de la vida diaria"), None,
                              [categoria, plantilla, extras])
        sugerencias.change(lambda s: s, sugerencias, patologia)
        sugerencias_psicologia.change(lambda s: s, sugerencias_psicologia, tema_psicologia)
        plantilla.change(lambda p: DESCRIPCION_PLANTILLAS.get(p, ""), plantilla, info_pl)
        ref_h.click(lambda: gr.update(choices=lista_historias()), None, hist)
        hist.change(ver_guion, hist, prev).then(_ediciones_guion, hist, extras)
        ref_v.click(lambda: gr.update(choices=lista_videos()), None, vids)
        vids.change(_descripcion_video, vids, desc).then(_ruta_video, vids, video)
        b_sub.click(marcar_subido, vids, [vids, estado])
        b_carp.click(abrir_carpeta, None, estado)
        b_lim.click(limpiar, None, estado)

        entradas = [plantilla, motor, voz, extras, volumen]
        btn.click(generar, [links, texto, patologia, tema_psicologia, categoria] + entradas +
                  [fondo_satisfactorio, fuente_videos],
                  [log, desc, video_pendiente]).then(_ruta_video, video_pendiente, video)
        btn2.click(rerender, [hist] + entradas, [log, desc, video_pendiente]).then(_ruta_video, video_pendiente, video)
    return demo


if __name__ == "__main__":
    construir().queue().launch(inbrowser=True, server_name="127.0.0.1",
                               server_port=int(os.getenv("GRADIO_SERVER_PORT", "7863")), theme=TEMA, css=CSS)
