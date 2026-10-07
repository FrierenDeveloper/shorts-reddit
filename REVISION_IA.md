# Brief de revisión técnica — `shorts-reddit`

> **Para:** ChatGPT / otro asistente de IA.
> **De:** auditoría previa hecha sobre el código real, con verificación en ejecución.
> **Objetivo:** que revises los hallazgos, cuestiones los que no te cuadren y propongas los parches.
> **Estado del repo:** sin cambios. Nadie ha modificado código todavía.

Este documento es **autocontenido a propósito**: no tienes acceso a la ruta local
(`C:\Users\kuris\Videos\shorts-reddit`), así que cada hallazgo incluye el código citado
literalmente y las mediciones hechas sobre los archivos reales.

**Aviso importante:** este proyecto tiene claves de API reales en `config\`
(Pexels, Pixabay, DeepSeek, una de Google y una de ElevenLabs). No las he incluido aquí y
**no deben aparecer nunca en un parche, en un commit ni en una respuesta**. Si propones
código que las lea, hazlo por variable de entorno o por el archivo, jamás hardcodeadas.

---

## 0. Cómo trabajar en conjunto (léelo antes que nada)

Reparto de roles, porque **tú no tienes acceso a los archivos**:

| Quién | Hace |
| --- | --- |
| **Tú (ChatGPT)** | Revisas este brief, cuestionas los hallazgos, decides entre las opciones abiertas de la §7 y escribes los parches. |
| **Agente local** | Aplica los parches en `C:\Users\kuris\Videos\shorts-reddit`, ejecuta las verificaciones de la §9 y te devuelve el resultado real. |
| **Usuario** | Pega tu respuesta al agente local y decide cuando hay desacuerdo. |

### Reglas para que tus parches se puedan aplicar

1. **No inventes código que no hayas visto.** Cada hallazgo de este documento trae el código
   citado. Si un parche toca una línea que no está citada aquí, **pide que te la peguen**
   antes de escribir el parche: adivinar el contexto es la forma más rápida de romper algo.
2. **Un parche = un hallazgo.** No mezcles el arreglo del sample rate con el del ffmpeg.
   Así se puede verificar y revertir por separado.
3. **Da el parche como bloque de código con la ruta y el rango de líneas**, en este formato:

   ````text
   ARCHIVO: app\make_short.py   (líneas 963-999)
   ANTES:  <las líneas exactas que se reemplazan>
   DESPUÉS: <las líneas nuevas>
   POR QUÉ: <una frase>
   RIESGO: <qué podría romper>
   PRUEBA: <comando o pasos concretos para comprobarlo>
   ````

   Si el parche es largo (reescribir el pipeline de frames, I3), escribe la función completa
   en lugar de un diff, para evitar errores de contexto.
4. **Di explícitamente cuando NO estés de acuerdo** con un hallazgo o con su severidad. Varios
   están marcados `por confirmar` justamente para que los cuestiones: si crees que uno es
   falso positivo, dilo y explica por qué. Es más útil que aceptarlo.
5. **No propongas refactors grandes sin justificarlos.** El código funciona en producción:
   hay 12 vídeos generados y el flujo de lote se usa. Preferimos muchos parches pequeños y
   verificables a una reescritura.
6. **Nada de claves de API** en tus parches ni en tus respuestas (ver el aviso de arriba).
7. Si necesitas ver un archivo completo que no esté citado, **pídelo por nombre** y el agente
   local te lo pega en el chat.

### Orden de ataque sugerido

Empieza por la **§7 (preguntas abiertas)**: son las decisiones de diseño que condicionan los
parches. Cuando las respondas, el agente local aplica el **Bloque A** de la §10 (cuatro
cambios de bajo riesgo), verifica con la §9 y te devuelve los resultados medidos. Con eso ya
se puede iterar sobre el **Bloque B**, que es donde está la chicha (C1, C2, I2, I3, I5).

---

## 1. Qué es el proyecto

Generador **local** (Windows, sin servicios en la nube salvo voz e imágenes) de Shorts
verticales 9:16 a partir de historias de Reddit y de temas de salud mental / psicología.

Pipeline por vídeo:

```
guion (LLM)  →  JSON de escenas en historias\
            →  voz (edge-tts | kokoro | xtts | chatterbox)
            →  tiempos por palabra (whisper si el motor no los da)
            →  fondo (fotos de Pexels/Pixabay/Openverse/Wikimedia  ó  clips "satisfactorios")
            →  música (archivo propio | descargada | compuesta)
            →  fotogramas (CPU multiproceso | GPU CUDA) + overlays (subtítulos karaoke,
               tarjeta, barra de progreso, encuesta, sonidos)
            →  ffmpeg → salida\<Tema>\<nombre>.mp4 + _descripcion.txt + _creditos.txt
                        + _portada.png
```

Interfaz: GUI de Gradio (`ABRIR_APP.bat`) y modo lote (`LOTE.bat` leyendo `links.txt`).

### Archivos y tamaño

| Archivo | Líneas | Rol |
| --- | --- | --- |
| `app\make_short.py` | 1045 | Orquestador del render: TTS, imágenes, frames, ffmpeg, salidas |
| `app\interfaz.py` | 477 | GUI Gradio |
| `app\extras.py` | 355 | Overlays: tarjeta, barra, karaoke, encuesta, SFX, portada |
| `app\fondos_satisfactorios.py` | 299 | Clips de fondo desde Pexels/Pixabay + caché + fallback local |
| `app\musica.py` | 196 | Música: archivo, descarga (Openverse) o composición |
| `app\guion.py` | 166 | Post → JSON de escenas vía LLM (API compatible OpenAI) |
| `app\gpu_render.py` | 164 | Composición de fotogramas en CUDA |
| `app\lote.py` | 155 | Modo lote sobre `links.txt` |
| `app\limpiar.py` | 77 | Limpieza de caché/temporales |
| `app\plantillas.py` | 80 | 6 plantillas visuales |

### Entorno verificado

- Python 3.12 en `.venv` (5,8 GB) y un segundo entorno `.venv_cb` (5,4 GB) para Chatterbox.
- `ffmpeg` y `ffprobe` en el PATH (Gyan.FFmpeg vía winget).
- CUDA disponible en esta máquina (la ruta GPU se usa si `SHORTS_RENDER != "cpu"`).
- Gradio 6.28.0.
- Proyecto total: **13,6 GB** (11,2 GB son los dos venv).

### Estado de los artefactos (medido, no estimado)

- **12 `.mp4`** en `salida\`, todos válidos: **1080x1920, h264 High/Level 4.0, 30 fps, AAC**,
  62–76 s, 27–84 MB. Bitrate máximo real 9,26 Mbps (el README promete tope de 12).
- LLM configurado en `config\llm.json` → `https://api.deepseek.com` + `deepseek-flash`:
  **probado en vivo, responde sin error de autenticación.**
- `cache\` = **1,35 GB** (942 MB de clips + 411 MB de imágenes). El TTL de 24 h funciona.
- `videos_fondo\` = 3 clips locales; `musica\` **vacía** (solo el LEEME);
  `voces\narrador.wav` presente (clonación Chatterbox configurada).

---

## 2. Cómo leer los hallazgos

Cada uno lleva:

- **Evidencia** — código citado y/o medición reproducible.
- **Disparo** — `EN VIVO` (pasa hoy) o `LATENTE` (existe en el código, hoy no se activa
  en esta máquina, pero se activaría en otra instalación o con otros datos).
- **Confianza** — `verificado` (lo reproduje o lo leí con mis ojos) o
  `por confirmar` (deducción de la auditoría, pendiente de comprobar en ejecución).

Esto importa: **no trates como equivalentes un fallo en vivo y uno latente.** Varios de los
latentes solo se disparan en una instalación nueva, sin claves de API.

---

## 3. CRÍTICO

### C1 — El fondo "satisfactorio" puede tumbar el vídeo completo

**Disparo:** `LATENTE` aquí (hay claves y 2 clips locales válidos) · **EN VIVO** en una
instalación sin claves ni `videos_fondo\`. **Confianza:** verificada.

`app\fondos_satisfactorios.py:226-243`:

```python
def obtener_clips(fuente="pixabay"):
    ...
    key = _api_key(fuente)
    if key:
        clips = buscar(key, tema)
        if clips:
            return clips, tema
        print(f"   {fuente.capitalize()} no encontró clips relacionados; probando la biblioteca local")
    else:
        print(f"   {fuente.capitalize()} sin clave disponible; usando la biblioteca local")
    locales = [p for p in _locales() if _duracion_local(str(p)) >= MIN_DURACION]
    if not locales:
        raise RuntimeError(f"No encontré clips de fondo de al menos {MIN_DURACION} segundos. "
                           f"Revisa Pixabay o agrega videos largos a videos_fondo.")
```

Y el consumo en `app\make_short.py:873-881` **no captura la excepción**:

```python
    if video_bg:
        import fondos_satisfactorios as FS
        print("2/4 Eligiendo fondo satisfactorio…")
        clips, tema = FS.obtener_clips(cfg.get("fuente_videos", "pixabay"))   # <- puede lanzar
```

**Impacto:** en vez de caer al fondo de fotos temáticas —lo que promete el README— se pierde
**toda** la generación. La opción está **activada por defecto**:
`app\interfaz.py:386` `gr.Checkbox(value=True, ...)` y el modo lote también la usa.
Sin claves, el README dice que la herramienta funciona igual (con Openverse/Wikimedia) —
pero eso es para *fotos*; los *clips* exigen clave o biblioteca local. Consecuencia: una
instalación nueva falla en todos los vídeos.

**Medición del caso real aquí:** de los 3 clips en `videos_fondo\`, dos pasan el filtro
(`pixabay_sand_beach_338904.mp4` 23,62 s, `pixabay_sand_dunes_284568.mp4` 17,68 s) y uno se
descarta (`pixabay_kinetic_sand_144459.mp4`, **6,93 s** < 15 s).

**Pregunta para ti:** ¿dónde debe vivir el fallback? Veo dos opciones y quiero tu criterio:
(a) que `obtener_clips` devuelva `None` y `make_short` decida caer a fotos; o (b) capturar
en `make_short` y rehacer el `if video_bg` a `False`. La (a) separa mejor responsabilidades,
pero cambia el contrato de la función (¿hay otros llamadores? Solo `make_short.py:876`).

---

### C2 — La ruta GPU del fondo de vídeo NO equivale a la CPU

**Disparo:** `EN VIVO` en cualquier render con `fondo_satisfactorio: true` · **Confianza:** verificada.

`app\gpu_render.py:27` define la banda que oscurece el centro:

```python
        self.band = (1 - 0.35 * torch.exp(-((ys - 0.5) ** 2) / 0.02))[None].to(self.dt)   # 1xPHx1
```

`app\gpu_render.py:119-120` (fondo de vídeo) **la aplica**:

```python
            ph = self.video_bg_image * 0.78
            tint = F.interpolate(ph[None], size=(M.PH, M.PW), mode="bilinear", align_corners=False)[0] * self.band
```

`app\make_short.py:725` (fondo de vídeo, CPU) **no la aplica**:

```python
            img = _S["video_bg_image"].point(lambda v: int(v * 0.78)).convert("RGBA")
```

En cambio en modo **fotos** ambas rutas sí la usan
(`gpu_render.py:124` y `make_short.py:730-731`).

**Impacto:** el mismo proyecto sale visiblemente más oscuro en la banda central según la
máquina. Contradice el docstring del propio módulo (`gpu_render.py:1`: "Mismo resultado
visual que el render en CPU").

**Pregunta para ti:** la banda existe para dar legibilidad al texto sobre el vídeo. Si es
así, lo correcto es **añadirla en CPU** (`make_short.py:725`), no quitarla de GPU. ¿Lo ves
igual? ¿`_S["band"]` está disponible en el worker de CPU? Según `make_short.py:731` sí, así
que el parche es de una línea — pero confírmame que no hay una razón de rendimiento detrás.

---

### C3 — Falla de render → `.mp4` truncado con el nombre definitivo, y ffmpeg huérfano

**Disparo:** `LATENTE` (solo al fallar un render, p. ej. OOM de CUDA) · **Confianza:** verificada.

`app\make_short.py:963-999`:

```python
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(tmp), *enc, ...
                           "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    ...
    for n, buf in enumerate(frames()):
        cola.put(buf)
        ...
    cola.put(None); th.join()
    ff.stdin.close(); ff.wait()          # <- no se mira ff.returncode
```

No hay `try/finally`. Si `frames()` lanza (p. ej. `pend.popleft().result()` re-lanza un OOM
de CUDA en `gpu_render.py:108-143`), nadie mata ni espera a ffmpeg. Como ffmpeg arrancó con
`-y` ya creó el archivo: al liberarse el pipe, **finaliza un mp4 parcial con el nombre final**
en `salida\...`, sin `_descripcion.txt`. El bucle del CLI (`make_short.py:1040-1043`) solo
imprime `✗` y sigue; `limpiar_corrida()` sí corre en el `finally` (`:785`) pero el `.mp4` no
está registrado en `TEMPORALES`, así que sobrevive.

El fallo **sí se detecta** (no hay fallback silencioso a un fotograma erróneo). El problema
es el artefacto roto que parece un entregable.

---

## 4. IMPORTANTE

### I1 — Audio a 96 kHz en vez de 24 kHz

**Disparo:** `EN VIVO` en los 12 vídeos · **Confianza:** verificada y **reproducida en laboratorio**.

`app\make_short.py:30` → `W, H, FPS, SR = 1080, 1920, 30, 24000` (la fuente es 24 kHz).
`app\make_short.py:966` aplica el filtro **sin** `-ar`:

```python
                           "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5",
```

`ffprobe` sobre los vídeos reales: **`aac 96000 Hz 1ch`**.

Prueba controlada que hice, con una fuente idéntica a la del proyecto:

| Entrada | Filtro | Salida | Tamaño |
| --- | --- | --- | --- |
| 24000 Hz mono | `loudnorm=I=-14:TP=-1.5` | **96000 Hz**, 193 kbps | 50 082 B |
| 24000 Hz mono | `loudnorm=I=-14:TP=-1.5 -ar 48000` | 48000 Hz, 159 kbps | 41 466 B |

**Causa:** `loudnorm` trabaja internamente a muy alta frecuencia y el codificador AAC la
recorta a 96 kHz. **Impacto:** el doble de datos de audio sin ninguna ganancia perceptible
(la fuente son 24 kHz), y 96 kHz mono es un formato raro para las plataformas, que
re-codificarán igualmente.

**Pregunta para ti:** ¿basta `-ar 48000` al final del `-af`, o es mejor mover `-ar` como
opción de salida independiente para que no lo reordene el parser de filtros? Y de paso:
¿`loudnorm` de una pasada a `I=-14` es suficiente para estas plataformas, o recomiendas dos
pasadas (medir y luego normalizar)? No quiero tocar la sonoridad actual sin criterio.

---

### I2 — No se comprueba el resultado de ffmpeg: "Listo" sin vídeo válido

**Disparo:** `LATENTE` · **Confianza:** verificada.

Mismo bloque que C3: `ff.stdin.close(); ff.wait()` ignora `ff.returncode`, y después
`make_short.py:1029` hace `print(f"Listo → {out}")` sin comprobar que `out` exista o no esté
vacío. El único punto que lo notaría es la miniatura (`:1007-1013`), cuyo fallo se traga
`except (subprocess.SubprocessError, OSError): pass`. Se escriben `_descripcion.txt` y
`_creditos.txt` y se reporta éxito.

**Impacto:** falso positivo de éxito tanto en el CLI como en el resumen de `lote.py`.

---

### I3 — El render puede colgarse para siempre, sin mensaje

**Disparo:** `LATENTE` · **Confianza:** verificada (lógica leída; no provoqué el cuelgue).

`app\make_short.py:988-998`:

```python
    cola = queue.Queue(maxsize=8)
    def escritor():
        while (buf := cola.get()) is not None:
            ff.stdin.write(buf)                     # <- sin try/except; hilo daemon
    th = threading.Thread(target=escritor, daemon=True); th.start()
    for n, buf in enumerate(frames()):
        cola.put(buf)                               # <- se bloquea para siempre si el hilo murió
```

Si `ff.stdin.write` lanza `BrokenPipeError` (encoder inválido, disco lleno, `-shortest`
cortando), el hilo muere; nadie consume la cola y el principal se bloquea en `cola.put` al
llegar a 8 fotogramas. No hay timeout ni comprobación de `th.is_alive()`. En modo lote
bloquea el lote entero.

**Pregunta para ti:** ¿flag compartido (`threading.Event`) que el bucle consulte antes de
`cola.put`, o reestructurar para escribir desde el hilo principal y renderizar en un pool
aparte? La segunda es más limpia pero toca el pipeline de frames; quiero tu recomendación
antes de reescribirlo.

---

### I4 — El selector "Motor de voz" de la GUI solo funciona a medias

**Disparo:** `EN VIVO` si un guion trae `motor_voz` distinto de `edge` · **Confianza:** verificada.

`app\interfaz.py:114` — la función **no recibe `motor`** y nunca escribe `cfg["motor_voz"]`:

```python
def _aplicar_opciones(js, plantilla, voz, extras, volumen, fondo_satisfactorio=None):
    ...
    cfg.pop("voz_elevenlabs", None)
    if cfg.get("motor_voz") == "elevenlabs":
        cfg.pop("motor_voz", None)
```

`app\interfaz.py:135-137` — solo se define la variable para Chatterbox, sin rama `else`:

```python
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    if motor.startswith("Chatterbox"):
        env["SHORTS_MOTOR_VOZ"] = "chatterbox"
```

`app\make_short.py:277` — **la variable de entorno manda sobre el JSON**:

```python
def motor_actual(cfg):
    return os.getenv("SHORTS_MOTOR_VOZ") or cfg.get("motor_voz", "edge")
```

**Impacto:** un guion con `"motor_voz": "kokoro"` o `"xtts"` seguirá usándolos aunque el
usuario elija "edge-tts" en la GUI. Solo la opción Chatterbox surte efecto.

---

### I5 — `_guardar()` escribe el guion antes de validarlo

**Disparo:** `LATENTE` (depende de que el LLM omita campos) · **Confianza:** verificada.

`app\guion.py:156-158`:

```python
    out = ROOT / "historias" / f"{name}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    palabras = sum(len(e["texto"].split()) for e in data["escenas"])     # <- KeyError
```

Compárese con `app\guion.py:47`, que sí es defensivo:
`sum(len((e.get("hablado") or e.get("texto", "")).replace("*", "").split()) for e in data.get("escenas", []))`

**Impacto:** si el modelo omite `escenas` o `texto`, el archivo **ya está escrito** cuando
salta el `KeyError`: queda un guion inválido en `historias\` que además aparece en la lista
de la GUI, pese a que el log diga "Falló". El mismo acceso directo en
`app\interfaz.py:305` (`e['texto'].replace('*', '**')`) revienta al previsualizar.

---

### I6 — Lote: sin registro si se interrumpe, y sobrescritura silenciosa

**Disparo:** `LATENTE` · **Confianza:** verificada.

`app\lote.py:147-149` — el resumen se escribe **después** del bucle:

```python
        time.sleep(15)  # pausa entre posts para que Reddit no bloquee
    out = ROOT / "salida" / "registros" / f"lote_{fecha}.txt"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(resumen), encoding="utf-8")
```

- Un Ctrl+C o un fallo previo **no deja ningún registro** (el `sleep(15)` además se ejecuta
  también tras el último link: 15 s regalados).
- `app\lote.py:126` `name = f"{fecha}_{i:02d}_{slug(titulo)}"` con `fecha` a resolución de
  **minuto** y `slug` truncado a 40 caracteres: dos ejecuciones en el mismo minuto con el
  mismo índice y título parecido sobrescriben `historias\{name}.json`, `posts\{name}.txt` y
  `salida\{carpeta}\{name}.mp4` en silencio.
- Existe `post_id(url)` (`app\lote.py:17`) y **no se usa para nombrar nada**.
- Los links duplicados dentro de una misma corrida no se deduplican: generan dos vídeos
  idénticos y dos entradas `OK` (coste y tiempo duplicados).

---

### I7 — "Limpiar caché" del GUI limpia de más y reporta de menos

**Disparo:** `EN VIVO` al pulsar el botón · **Confianza:** verificada.

`app\limpiar.py:42` recorre el árbol completo buscando `__pycache__`:

```python
    auto = [ROOT / "cache"] + list(ROOT.rglob("__pycache__"))
```

**Medido: 4205 directorios `__pycache__`, de los cuales 4204 están dentro de `.venv`/`.venv_cb`** —
es decir, borra el bytecode compilado de las dependencias instaladas (se regenera, pero
ralentiza el siguiente arranque y no es lo que el usuario espera de "limpiar caché").

`app\limpiar.py:46-49` cuenta antes de borrar, y `borrar()` se traga los errores:

```python
    for p in auto:
        if Path(p).exists():
            liberado += tam(p) if Path(p).is_dir() else Path(p).stat().st_size
            borrar(p)
    print(f"Caché y temporales: {liberado / 1e6:.1f} MB liberados")
```

`app\limpiar.py:24-29` `borrar()` devuelve `False` en silencio ante `OSError` (típico en
Windows con `.pyc` en uso) → se anuncia "X MB liberados" aunque no se haya borrado nada.

Y la llamada del GUI (`app\interfaz.py:331-332`) **no tiene `timeout`** y es síncrona, así que
congela la interfaz mientras recorre 4205 directorios:

```python
    r = subprocess.run([_py(), str(APP / "limpiar.py"), "--solo-cache"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or r.stderr).strip()
```

---

### I8 — `config\llm.json` promete un proveedor Gemini que no existe

**Disparo:** `EN VIVO` (config inerte) · **Confianza:** verificada.

El archivo tiene `"proveedor": "gemini-cli"` y una ayuda que menciona
`INSTALAR_GEMINI.bat`. Pero:

- `gemini` aparece **0 veces** en todo `app\*.py`.
- `INSTALAR_GEMINI.bat` **no existe** (solo hay `INSTALAR.bat`, `INSTALAR_CHATTERBOX.bat`, `INSTALAR_GPU.bat`).
- `app\guion.py:29-31` define `proveedor()` que **no tiene ningún llamador** y devuelve `"api"` fijo:
  ```python
  def proveedor():
      """Usa el endpoint OpenAI compatible de LM Studio o el proveedor definido en llm.json."""
      return "api"
  ```
- `app\guion.py:36-38` solo lee tres claves (`base_url`, `api_key`, `modelo`).
- `app\interfaz.py:173` `os.environ["SHORTS_LLM"] = "api"` tampoco se lee en ningún sitio.
- `config\gemini.json` (con una clave real) **no lo lee nadie**.

**Impacto hoy:** ninguno funcional (el `base_url` de DeepSeek está puesto y probado). Pero si
el usuario sigue la ayuda y deja `base_url`/`api_key` vacíos, `guion.py:37` cae a
`http://localhost:1234/v1` + `lm-studio` y el error que verá será de conexión a LM Studio,
sin ninguna pista sobre Gemini. Hay una clave real durmiendo en disco para una función que no existe.

---

### I9 — La ayuda de `guion.py` recomienda OpenCode Go, que devuelve 400

**Disparo:** `EN VIVO` si alguien sigue el docstring · **Confianza:** verificada contra registros reales.

`app\guion.py:6`:

```
  $env:LLM_BASE_URL="https://opencode.ai/zen/go/v1"; $env:LLM_API_KEY="tu_clave"; $env:LLM_MODEL="deepseek-chat"
```

El endpoint de OpenCode Go **exige** la cabecera `x-opencode-session`, que el SDK de OpenAI no
envía. Prueba: el propio proyecto lo sufrió y quedó registrado en
`salida\registros\lote_20260928_0030.txt`:

```
FALLÓ ... → Error code: 400 - {'type': 'error', 'error': {'type': 'MissingSessionID',
'message': 'Request is missing x-opencode-session and cannot be routed efficiently.
Please see https://opencode.ai/docs/go/#where-can-i-use-it'}}
```

Y antes, en el mismo histórico de registros: `Model deepseek-chat is not supported` (401) e
`Invalid API key`. El usuario acabó pasándose a `api.deepseek.com`.

**Nota de contexto externa** (por si propones reintroducir OpenCode Go): su documentación
lista a los clientes que envían la cabecera; un cliente que use el SDK de OpenAI tal cual
**no** la envía, y varios agentes de código están en la lista de "no conformes". Si quieres
soportar OpenCode Go de verdad, hay que inyectar esa cabecera por sesión (el SDK acepta
`default_headers`) y mantener un id de sesión estable por conversación. **Eso es una decisión
de diseño, no un parche de una línea** — no lo metas sin discutirlo.

---

## 5. MENOR

| # | Defecto | Evidencia | Confianza |
| --- | --- | --- | --- |
| M1 | Rama muerta: `if total > 95` es inalcanzable porque antes `total > 70` ya lanzó, y el texto "60–90 s" contradice el rango 60–70 aplicado | `make_short.py:863-868` y `:174`, `:779` | verificada |
| M2 | Umbral de imágenes contradice el README ("al menos 1080×1350"): el código acepta `MIN_H * 0.75` = 1012,5 px de alto | `make_short.py:299` (`MIN_W, MIN_H = 1080, 1350`) y `:391` `(MIN_W, MIN_H * 0.75)` | verificada |
| M3 | `cfg.update(nuevo)` deja que el JSON del LLM pise las opciones del usuario (`voz`, `extras`, `plantilla`), contra el comentario de esa misma línea | `guion.py:117` | verificada |
| M4 | Parámetro muerto: `tts(..., palabras=True)` — las dos llamadas pasan `False`, así que el fallback de whisper dentro de `tts` nunca se usa | `make_short.py:279`, `:289-290`, llamadas en `:825`, `:828` | verificada |
| M5 | Variable muerta `i0` (se asigna, nunca se lee) | `make_short.py:514` | verificada |
| M6 | `next()` sin default: si un timestamp de whisper cae en la pausa, `StopIteration` en el render (el margen `+0.01` no cubre el `+0.05` del filtro de palabras) | `make_short.py:858` vs `:845` | por confirmar |
| M7 | División sin épsilon en un span de ancho 0, donde el resto del código sí protege (`max(b - a, 1e-6)` en `:625`) | `make_short.py:685` | por confirmar |
| M8 | División por cero si toda la narración es silencio → audio `nan` con solo un RuntimeWarning | `make_short.py:861` y `:956` | verificada (la guarda no existe) |
| M9 | Claves obligatorias sin guarda: `cfg["imagenes"]` → `KeyError`; con `"imagenes": []` el bucle no corre, `photos` queda vacío y `len(photos) - 1 == -1` → `IndexError` en el worker | `make_short.py:884`, `:886`, `:897-898` | verificada |
| M10 | El `subreddit` del JSON se ignora en historias de Reddit (el comentario dice que es intencional, pero el README afirma que se puede cambiar) | `make_short.py:914-919` vs `README` §Elementos de retención | verificada |
| M11 | `TypeError` si `fuente_reddit` es `null` (`re.search(patrón, None)`) | `make_short.py:914` | verificada |
| M12 | Un mp3 corrupto o de 0 bytes en `musica\` **aborta el vídeo**: la vía de archivo no está en `try`, a diferencia de la vía web | `musica.py:173` vs `:177-182`; `_cargar` usa `check=True` en `:102-103` | verificada |
| M13 | La portada puede tapar el dibujo, contra su propio docstring: con `dw = 700`, `lh = 110` y 6 líneas, el `max(..., 560)` produce ~80 px de solape | `extras.py:122` (docstring), `:138-145` | por confirmar (aritmética sí) |
| M14 | `"encuesta": true` (patrón que el propio README usa para los extras) lanza `TypeError` al desestructurar `a, b = ...` | `extras.py:240` | verificada (la guarda no existe) |
| M15 | `marcar_subido` mueve por **prefijo**: `glob(f"{stem}*")` puede arrastrar a `subidos\` un vídeo cuyo nombre comparte prefijo — y `limpiar.py` borra `subidos\` a los 7 días | `interfaz.py:324` y `limpiar.py:56` | verificada (el glob) / impacto por confirmar |
| M16 | La caché de clips **no caduca**: solo el JSON de búsqueda tiene 24 h, los `.mp4` se reutilizan indefinidamente. Evidencia: 43 mp4 + 11 json acumulados | `fondos_satisfactorios.py:118`, `:198` vs `:69-70`, `:163-164` | verificada por evidencia en disco |
| M17 | Caché negativa de 24 h: una respuesta 200 con esquema inesperado guarda `[]` y la búsqueda se salta un día entero | `fondos_satisfactorios.py:125-126` | por confirmar |
| M18 | Fuga de `*.download`: si la respuesta es válida pero < 100 KB (o vacía) se sale sin `tmp.unlink()` | `fondos_satisfactorios.py:86-94`, `:180-188` | verificada (hoy 0 archivos) |
| M19 | La fuga de `_prep_*.jpg` es real pero **latente y se autocorrige**: no se registran en `TEMPORALES`, pero `LIMPIAR.bat` vacía `cache\` entero. **Medido: 0 archivos en disco** | `make_short.py:909-913` vs `:176-189` | verificada |
| M20 | `random.seed(semilla)` siembra el RNG **global**: al procesar varios JSON en una corrida, el tema/clips del vídeo siguiente quedan determinados por el nombre del anterior | `musica.py:171` | por confirmar |
| M21 | Fondo generado a 720×1280 y 15 fps y mostrado en 1080×1920 a 30 fps → reescalado 1,5× y fotogramas duplicados (geometría 9:16 correcta) | `fondos_satisfactorios.py:263`, `:286`, `:291`; `make_short.py:720` | verificada |
| M22 | Discrepancias de README: dice "dos clips" y el código junta **4** (`CLIPS_FONDO = 4`), y el texto del checkbox repite "dos clips" | `fondos_satisfactorios.py:21`; `interfaz.py:387`; `README` §Fondo satisfactorio | verificada |
| M23 | README con mojibake real en las líneas 9, 10, 11 y 78 (`crÃ©ditos`, `temÃ¡tica`, `prÃ¡ctica`) | `README.md` | verificada |
| M24 | Código muerto vario: `cache["hint"]`, parámetro `menor_rel`, variable `base`, `import extras as X` sin uso | `extras.py:243`; `musica.py:18-19`; `gpu_render.py:125` | por confirmar |

**Nota sobre los `posts\*.txt` y los registros de lote:** son UTF-8 **correcto**. Que se vean
como `SÃ­ndrome` al leerlos con `Get-Content` en Windows PowerShell es un artefacto de consola,
**no** un fallo del proyecto. No lo "arregles".

---

## 6. Verificado como CORRECTO — no lo toques sin motivo

Esto ya se comprobó y cumple lo que promete. Si un parche lo cambia, debe ser a propósito.

- **`limpiar.py` nunca borra vídeos sin publicar.** Solo actúa sobre `salida\subidos` (+7 d),
  `salida\registros` (+30 d), `historias` y `posts` (+60 d). Los vídeos sin publicar solo se
  **cuentan** para avisar. Umbrales idénticos al README.
- **La limpieza de temporales que promete el README se cumple** para descargas, miniaturas,
  wav de mezcla y carpeta de frames: `limpiar_corrida()` corre en el `finally` de `main`
  (`make_short.py:785`), incluso si el render falla, y respeta `SHORTS_MANTENER_CACHE=1`.
- **Umbrales del fondo exactos:** `MIN_DURACION = 15` con `>=` descarta < 15 s;
  `OBJETIVO_DURACION = 20` con `>=` y mezcla preferidos+otros. El README acierta aquí.
- **Red del fondo robusta:** timeouts (`timeout=(15, 90)` y `timeout=25`), `raise_for_status()`,
  validación de host/esquema/extensión, comprobación de content-type y tope de 150 MB.
  JSON malformado → `ValueError` capturado; caché corrupta → fallback local sin crash.
- **Sin créditos del fondo** cuando hay vídeo: se borra el sidecar y se limpia la descripción
  (`make_short.py:1021-1023`), y la música web se desactiva en ese modo (`:948`).
- **Geometría 9:16 correcta:** `scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280`.
- **`preparar_frames` sin off-by-one ni división por cero:** `max(seg_por_clip, 1.0)` y
  `n_seg = max(1, ceil(...))` garantizan duración > 0.
- **El karaoke no puede dar `IndexError`:** hay una entrada de tiempo por token y una por
  palabra en el layout; x/y/w reproducen exactamente `sub_sprite` con la misma fuente y trazo.
- **Encoder conforme al README:** NVENC p5/CQ 20 o libx264 slow CRF 20 con VBV 12/24 Mbps;
  salida BT.709 + AAC 192k. El máximo real medido es 9,26 Mbps.
- **`loudnorm` no es un bug de sonoridad** — el nivel está bien; el problema es solo el
  sample rate (I1).
- **Cableado de Gradio 6.28.0 correcto:** se construyeron los `Blocks` sin excepción; la
  aridad de los 20 eventos casa (`generar` 12 entradas, `rerender` 6/6, etc.).
- **`gpu_render`: sin `IndexError`** (índice de fondo con módulo), recorte de cámara y zoom
  con las mismas fórmulas que CPU, FreeType serializado bajo `_LOCK` en los 4 hilos.

---

## 7. Preguntas abiertas para ti

Responde en concreto a estas; son las decisiones que no quiero tomar solo:

1. **Fallback del fondo (C1):** ¿`obtener_clips` devuelve `None` y decide `make_short`, o se
   captura la excepción en `make_short`? ¿Añadirías, además, un aviso visible en la GUI
   cuando no hay claves ni clips locales?
2. **Banda GPU/CPU (C2):** confirmado que la intención es oscurecer para legibilidad, ¿lo
   correcto es aplicar `_S["band"]` en CPU en `make_short.py:725`? ¿Ves algún riesgo de
   doble oscurecimiento o de romper el color?
3. **Sample rate (I1):** ¿`-ar 48000` dentro del `-af` o como opción de salida? ¿Una o dos
   pasadas de `loudnorm` para `I=-14`?
4. **Cuelgue del escritor (I3):** ¿flag + `Event`, o rediseñar el pipeline de frames para
   escribir desde el hilo principal? Quiero la opción con menos riesgo de regresión.
5. **Redacción del error de ffmpeg (I2/C3):** al detectar `returncode != 0`, ¿borramos el
   `.mp4` parcial o lo renombramos a `.parcial.mp4` para diagnóstico?
6. **`_guardar` (I5):** ¿validación con esquema mínimo (¿`jsonschema`? ¿a mano?) antes de
   escribir, o solo `.get()` defensivo? Ten en cuenta que el JSON lo genera un LLM y puede
   variar de forma.
7. **OpenCode Go (I9):** ¿merece la pena implementar la cabecera `x-opencode-session` con
   `default_headers` + id de sesión estable, o dejamos DeepSeek oficial y corregimos el
   docstring? Si lo implementas, ¿cómo gestionarías el id de sesión entre llamadas?
8. **Duplicados de `historias\`:** hay 8 historias regeneradas varias veces (hasta 4 versiones
   del mismo título). ¿Conviene que `lote.py` derive el nombre de `post_id(url)` para que
   reejecutar no duplique?

---

## 8. Restricciones y convenciones

- **No tocar** `config\`, `salida\`, `posts\`, `historias\` ni `.venv*`: son datos del usuario
  o entornos instalados. Los parches van a `app\` y a `README.md`.
- **Nunca** escribir claves reales en código, parches, logs ni respuestas.
- **Windows + PowerShell.** Python 3.12. `ffmpeg`/`ffprobe` en el PATH.
- El formato del JSON de guion es un **contrato externo**: lo edita el usuario y lo leen
  varias partes. No lo cambies de forma incompatible; si añades campos, que sean opcionales
  con valor por defecto.
- Mantén el estilo actual: español, funciones cortas, comentarios de intención.
- Un cambio por parche, con su prueba. Nada de refactors grandes mezclados con arreglos.

---

## 9. Cómo verificar cada arreglo

```powershell
# 1) Audio: debe pasar de 96000 a 48000 (I1)
ffprobe -v error -select_streams a -show_entries stream=sample_rate,channels,bit_rate -of csv=p=0 "salida\Reddit\<video>.mp4"

# 2) Integridad del vídeo generado (I2/C3): debe ser 1080x1920, h264, 30 fps, con audio
ffprobe -v error -show_entries stream=codec_type,width,height,codec_name,r_frame_rate -of csv=p=0 "salida\Reddit\<video>.mp4"

# 3) Bitrate por debajo del tope del README (12 Mbps)
ffprobe -v error -show_entries format=bit_rate -of csv=p=0 "salida\Reddit\<video>.mp4"

# 4) Fuga de temporales: no debe quedar nada _prep_* ni *.download (M18/M19)
(Get-ChildItem cache -Recurse -File -Include "_prep_*","*.download").Count

# 5) "Limpiar caché" no debe tocar .venv (I7)
(Get-ChildItem .venv -Recurse -Directory -Filter __pycache__).Count   # debe seguir siendo > 0 tras limpiar

# 6) El fondo no debe abortar el vídeo (C1): renombra videos_fondo y quita la clave de turno,
#    y comprueba que el render cae a fotos temáticas en vez de fallar.

# 7) Igualdad GPU/CPU (C2): renderiza el mismo JSON con y sin SHORTS_RENDER=cpu y compara
#    un fotograma del centro (deben coincidir; hoy difieren en brillo de la banda).
```

---

## 10. División de trabajo propuesta

**Bloque A — arreglos de una línea, sin riesgo (hazlos primero):**

1. `claves.json` al `.gitignore` (hoy contiene claves reales **sin cubrir**; no hay repo git
   todavía, así que aún no se ha filtrado nada, pero es la prioridad número uno).
2. `-ar 48000` (I1).
3. `_S["band"]` en la ruta CPU del fondo (C2).
4. `motor_voz` en `_aplicar_opciones` (I4).

**Bloque B — robustez (cambios pequeños y acotados):**

5. Comprobar `ff.returncode` + `try/finally` con `kill()` y limpieza del parcial (I2/C3).
6. Flag de error en el hilo `escritor` (I3).
7. `try/except` con fallback a fotos en el fondo (C1).
8. Validar el guion antes de escribirlo en `_guardar` (I5).

**Bloque C — limpieza y documentación:**

9. `limpiar.py`: excluir `.venv*`, añadir `timeout` a la llamada del GUI, contar MB después de
   borrar (I7).
10. `lote.py`: escribir el registro de forma incremental o en `finally` (I6).
11. README: mojibake (M23), "dos clips" → 4 (M22), umbral de imagen (M2), y corregir el
    docstring de OpenCode Go (I9).

---

## 11. Anexo: comandos de diagnóstico útiles

```powershell
# Inventario de salidas con metadatos completos
Get-ChildItem salida -Recurse -File -Filter *.mp4 | ForEach-Object {
  $j = ffprobe -v error -print_format json -show_format -show_streams $_.FullName | ConvertFrom-Json
  $v = $j.streams | Where-Object codec_type -eq video | Select-Object -First 1
  [pscustomobject]@{ Archivo=$_.Name; MB=[math]::Round($_.Length/1MB,1)
    Dur=[math]::Round([double]$j.format.duration,1); Video="$($v.width)x$($v.height) $($v.codec_name)" }
} | Format-Table -AutoSize

# Tamaño por carpeta (para decidir qué limpiar)
Get-ChildItem . -Directory | ForEach-Object {
  $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  "{0,-20} {1,10:N0} MB" -f $_.Name, ($s/1MB)
}

# Historial de fallos de lote (útil para ver patrones de error del LLM)
Get-ChildItem salida\registros -File | ForEach-Object { "### $($_.Name)"; Get-Content $_.FullName }
```

---

## 12. Registro de decisiones y resultados

ChatGPT rellena la columna **Decisión**; el agente local rellena **Verificado**. Se va
actualizando conforme avanza el trabajo, para que ninguno de los tres pierda el hilo.

| # | Pregunta (§7) | Decisión de ChatGPT | Verificado en local |
| --- | --- | --- | --- |
| 1 | Fallback del fondo (C1): ¿`None` o capturar en `make_short`? | *(pendiente)* | — |
| 2 | Banda GPU/CPU (C2): ¿aplicar `_S["band"]` en CPU? | *(pendiente)* | — |
| 3 | Sample rate (I1): ¿`-ar` en el `-af` o como salida? ¿1 o 2 pasadas? | *(pendiente)* | — |
| 4 | Cuelgue del escritor (I3): ¿flag o rediseño? | *(pendiente)* | — |
| 5 | Error de ffmpeg (I2/C3): ¿borrar el parcial o renombrarlo? | *(pendiente)* | — |
| 6 | `_guardar` (I5): ¿esquema mínimo o `.get()` defensivo? | *(pendiente)* | — |
| 7 | OpenCode Go (I9): ¿implementar la cabecera o corregir el docstring? | *(pendiente)* | — |
| 8 | Duplicados (I6): ¿nombrar con `post_id(url)`? | *(pendiente)* | — |

### Estado de los bloques (§10)

| Bloque | Contenido | Estado |
| --- | --- | --- |
| A | 4 cambios de bajo riesgo: `.gitignore`, `-ar 48000`, banda en CPU, `motor_voz` | *(sin empezar)* |
| B | Robustez: ffmpeg, cuelgue, fallback del fondo, `_guardar` | *(sin empezar)* |
| C | Limpieza y documentación: `limpiar.py`, `lote.py`, README | *(sin empezar)* |

### Cómo reporta el agente local

Tras aplicar un bloque devuelve, por cada parche: el archivo y líneas tocadas, la salida real
de las verificaciones de la §9 (mediciones, no impresiones) y cualquier cosa que se haya
comportado distinto de lo previsto. Si algo no se puede verificar sin gastar créditos de API
o sin renderizar un vídeo completo, se dice explícitamente en lugar de darlo por bueno.

---

*Documento generado a partir de una auditoría con verificación en ejecución sobre el código
real. Los hallazgos marcados `por confirmar` necesitan comprobarse antes de actuar sobre ellos.
Ninguna clave de API aparece en este documento por diseño.*
