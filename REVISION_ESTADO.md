# Estado de la revisión — `shorts-reddit`

**Este es el documento vivo.** `REVISION_IA.md` es el análisis (hallazgos y preguntas);
**este archivo es el marcador**: qué se ha decidido, qué se ha aplicado y qué se ha verificado.

## Quién escribe qué

| Sección | La escribe | Cuándo |
| --- | --- | --- |
| **Decisiones** | ChatGPT (o el usuario) | Al responder una pregunta de la §7 del brief |
| **Aplicado** | El agente local | Al tocar código, con el resultado real |
| **Verificado** | El agente local | Al correr las comprobaciones de la §9 |
| **Bitácora** | Cualquiera | Al cerrar cada vuelta del ciclo |

**Vocabulario cerrado de estados** (no inventar otros, para que se pueda leer de un vistazo):
`pendiente` · `decidida` · `aplicada` · `verificada` · `descartada` · `bloqueada`

Regla importante: un cambio pasa a `verificada` **solo** con la medición hecha. Si algo no se
puede comprobar sin gastar créditos de API o sin renderizar un vídeo completo, se queda en
`aplicada` y se dice por qué.

---

## Decisiones (preguntas §7 del brief)

**Las 8 están `decidida`.** El detalle y quién fijó cada una está en la tabla "Decisiones
arbitradas" de la sección **Aplicado**, más abajo.

| # | Pregunta | Estado |
| --- | --- | --- |
| 1 | Fallback del fondo (C1) | `decidida` — capturar en `make_short` y caer a fotos |
| 2 | Banda GPU/CPU (C2) | `decidida` — añadirla en CPU (ya `aplicada`) |
| 3 | Sample rate (I1) | `decidida` — `-ar 48000` como opción de salida, una pasada (ya `aplicada`) |
| 4 | Cuelgue del escritor (I3) | `decidida` — drenar la cola en vez de morir |
| 5 | Error de ffmpeg (I2/C3) | `decidida` — `<nombre>.mp4.part` + `os.replace` |
| 6 | `_guardar` (I5) | `decidida` — validación mínima antes de escribir |
| 7 | OpenCode Go (I9) | `decidida` — solo corregir el docstring |
| 8 | Duplicados (I6) | `decidida` — nombre con `post_id(url)` + registro incremental |

---

## Aplicado (parches en el código)

**Bloque A — COMPLETO y verificado.** Decidido en un debate a tres: Codex (GPT-6 Luna, sin
acceso a archivos), Revisor B (contexto independiente, con acceso al código y mediciones de
laboratorio) y Claude (árbitro, leyó el código él solo).

| # | Hallazgo | Archivo / líneas | Estado | Verificación |
| --- | --- | --- | --- | --- |
| A1 | `config/claves.json` sin cubrir por `.gitignore` | `.gitignore:4` | `verificada` | Repo de prueba: `git check-ignore -v` casa con la línea 4 y `git status` no lista las claves |
| A2 | Audio a 96 kHz (I1) | `make_short.py:970` | `verificada` | Fuente 24000 Hz → salida **48000 Hz, 1ch, 159419 bps** (antes 96000 / 193050) |
| A3 | Banda oscura ausente en la ruta CPU (C2) | `make_short.py:725-729` | `verificada` | Banda 1,0 → **0,65** en el centro; píxel central 156 → **101** |
| A4 | El motor de voz de la GUI no tenía efecto (I4) | `interfaz.py:132-148` | `verificada` | `_motor_id` pasa 4 casos (incluido `None`); `SHORTS_MOTOR_VOZ` se fija siempre |

**Bloque B — COMPLETO y verificado** con un render real de extremo a extremo.

| # | Hallazgo | Archivo / líneas | Estado | Verificación |
| --- | --- | --- | --- | --- |
| B1 | El fondo podía tumbar el vídeo entero (C1) | `make_short.py:877-903` | `verificada` | Se captura solo el `RuntimeError` de "no hay material" y se cae a fotos; los 17 guiones con fondo tienen `imagenes`, y si faltaran usa un color liso |
| B2 | Éxito silencioso con vídeo roto (I2/C3) | `make_short.py:973-1050` | `verificada` | `.part` + `os.replace`: render real de 81 s con 0 ficheros `.part` huérfanos y nombre final correcto |
| B3 | El render podía colgarse para siempre (I3) | `make_short.py:1004-1040` | `verificada` | Prueba con ffmpeg que muere: detecta el fallo y termina en **0,00 s** en vez de colgarse en `cola.put` |
| B4 | El guion se escribía antes de validarse (I5) | `guion.py:142-176` | `verificada` | `_validar_guion` pasa **7/7** casos (válido, escenas vacías, sin texto, texto en blanco, raíz lista, campos extra) |

**Bloque C — COMPLETO y verificado.**

| # | Hallazgo | Archivo / líneas | Estado | Verificación |
| --- | --- | --- | --- | --- |
| C1 | `limpiar.py` borraba los `__pycache__` de `.venv*` y anunciaba MB que no liberaba | `limpiar.py` (docstring, `pycaches()`, `main`) | `verificada` | Candidatos **4205 → 1** (solo el del proyecto); **0** dentro de `.venv*`. El recuento suma solo si el borrado tuvo éxito, e informa de los que fallaron |
| C2 | La limpieza del GUI congelaba la interfaz | `interfaz.py:341-346` | `verificada` | `timeout=300` con mensaje propio si se agota |
| C3 | El lote no dejaba registro si se interrumpía | `lote.py:112-160` | `verificada` | Prueba con un link inválido: **se crea el registro pese al fallo** (antes no se escribía nada). **Evidencia del mundo real**: el lote del 30-09 a las 00:47 generó guion, post y vídeo pero **ningún `lote_20260930_0047.txt`**, que es justo lo que este arreglo evita |
| C4 | Sobrescritura silenciosa en el lote | `lote.py:135-142` | `verificada` | Nombre derivado de `post_id(url)` con respaldo `fecha_índice` para el texto pegado a mano; `sleep(15)` solo **entre** items |
| C5 | README con mojibake y datos falsos | `README.md` | `verificada` | **Cero mojibake**; "dos clips" → **cuatro** (`CLIPS_FONDO=4`); umbral de imagen corregido a 1080×1013 |
| C6 | El docstring mandaba a un endpoint que devuelve 400 | `guion.py:4-9` y `README.md:39` | `verificada` | Ahora avisa de que OpenCode Go exige `x-opencode-session` y remite al hallazgo I9 |

**Dos bugs extra que destapó la propia verificación del Bloque C** (no estaban en la auditoría):

| # | Hallazgo | Evidencia |
| --- | --- | --- |
| C7 | Un `links.txt` guardado **con BOM** rompía el lote | Reproducido: `UnicodeEncodeError` con el carácter `\ufeff`. PowerShell (`Set-Content -Encoding UTF8`) y el Bloc de notas añaden BOM. Arreglado leyendo con `utf-8-sig` (en `links.txt` y en los posts pegados a mano) |
| C8 | `lote.py` no reconfiguraba la salida a UTF-8 | Un título o un link con caracteres no imprimibles en cp1252 tumbaba el proceso. Ahora usa el mismo `reconfigure(encoding="utf-8", errors="replace")` que `make_short.py` |

Además del arbitraje, el Bloque B incorpora dos detalles que **solo detectó Claude** leyendo el
código: que en Windows una tubería rota lanza `OSError [Errno 22]` y no `BrokenPipeError`, y que
con `-y` ffmpeg ya había destruido el vídeo bueno anterior antes de saber si el render fallaba.

### Decisiones arbitradas (las 8 preguntas de la §7)

| Q | Decisión | Quién la fijó |
| --- | --- | --- |
| Q1 | Capturar en `make_short` la excepción específica y caer a fotos con `video_bg=False` | A y B coinciden |
| Q2 | **Añadir** la banda en CPU; no quitarla de GPU | A, B y Claude |
| Q3 | `-ar 48000` como opción de salida, después del `-af`; **una** pasada de `loudnorm` | A y B; Claude avala la pasada única |
| Q4 | Escritor que **drena** la cola (no muere), + `break` en el productor, + `gen.close()` en `finally` | B; Claude lo elige sobre el `Event`+timeout de A |
| Q5 | Escribir a `<nombre>.mp4.part` y `os.replace` al terminar; borrar el `.part` si falla | **Claude** (cuarta opción: protege el vídeo anterior, que `-y` ya machacaba) |
| Q6 | Validación mínima **antes** de `write_text` + `.get()` defensivo | A y B |
| Q7 | Solo corregir el docstring (`guion.py:6` y `README.md:39`) | A y B; ninguno pudo verificar que la cabecera baste |
| Q8 | Nombrar con `post_id(url)` y escribir el registro de forma incremental | A y B coinciden |

Detalles que solo aparecieron en el debate y que valen su peso:

- **Claude refutó a Revisor B**: `salida\_fallidos\` **sí** molesta — `limpiar.py:69` busca
  `*.mp4` en todo `salida\` y solo excluye `subidos`, así que esos vídeos quedarían contados
  como "sin publicar" para siempre.
- **Claude detectó** que `-y` destruye el vídeo bueno anterior antes de saber si el render
  falla, y que en Windows una tubería rota lanza `OSError [Errno 22]`, **no** `BrokenPipeError`.
- **Revisor B detectó** que los `.bat` de Chatterbox exportan `SHORTS_MOTOR_VOZ`, y que
  `loudnorm` emite a 192000 Hz (de ahí el 96000: el AAC no soporta esa tasa).
- **Codex detectó** su propio límite: avisó de que el tipo de `_S["band"]` no lo podía
  verificar, y su parche resultó incorrecto por eso (`_S["band"]` es un ndarray, no una
  imagen PIL). Su A4 fue directamente una invención y se descartó.

---

## Verificado (mediciones reales)

| Comprobación | Línea base | Ahora |
| --- | --- | --- |
| Sample rate del audio (I1) | ✗ 96000 Hz | ✓ **48000 Hz** — confirmado en un render real y en laboratorio |
| Banda en la ruta CPU (C2) | ✗ ausente (156 plano) | ✓ centro a 101; ratio centro/bordes **0,729** en el vídeo renderizado |
| Ficheros `.part` huérfanos tras un render | n/a | ✓ **0** (`.part` + `os.replace`) |
| Colgado del render con ffmpeg muerto | ✗ se bloqueaba en `cola.put` | ✓ detecta el fallo y termina en **0,00 s** |
| Validación del guion | `KeyError` tras escribir | ✓ `_validar_guion` 7/7 casos, **antes** de escribir |
| `config\claves.json` cubierto (A1) | ✗ no | ✓ sí (`git check-ignore`) |
| Motor de voz de la GUI (I4) | ✗ ignorado | ✓ `SHORTS_MOTOR_VOZ` siempre fijado |
| Vídeos válidos 1080x1920 h264 30fps | 12 de 12 | 13 de 13 (`_verif_bloqueB`, 63,6 s) |
| Bitrate máximo (tope README 12 Mbps) | 9,26 Mbps | sin cambios |
| Ficheros `_prep_*` / `*.download` fugados | 0 | 0 |
| Directorios `__pycache__` en `.venv*` (I7) | 4204 | ✓ **intactos**: `pycaches()` devuelve 1 candidato (el del proyecto) en vez de 4205 |
| `links.txt` guardado con BOM | ✗ rompía el lote (`UnicodeEncodeError`) | ✓ tolerado (`utf-8-sig`) |
| Registro del lote ante una interrupción | ✗ no se escribía nada | ✓ se escribe tras cada item y en el `finally` |
| Mojibake en el README | ✗ 4 líneas | ✓ **0** |
| `cache\` | 1,35 GB | — |

**Render de verificación del Bloque B**: `salida\Reddit\_verif_bloqueB.mp4` (81 s de CPU,
14 escenas, fondo de vídeo de 4 clips, 954 fotogramas). Es un **artefacto de prueba**, no una
publicación: se puede borrar junto con su portada cuando ya no haga falta.

---

## Siguiente

**Los tres bloques (A, B y C) están aplicados y verificados.** Queda esto, todo opcional:

1. Un render por **GPU** con el mismo guion, para confirmar la paridad CPU/GPU de la banda (el
   docstring de `gpu_render.py` afirma que dan el mismo resultado y ahora debería ser cierto).
2. Una **segunda pasada de `loudnorm`** si algún día se quiere afinar el LUFS: hoy mide −14,4 a
   −16,0 frente al objetivo −14. Claude lo desaconsejó salvo medición previa de picos.
3. Borrar los artefactos de prueba: `salida\Reddit\_verif_bloqueB.mp4` y `_verif_bloqueB_portada.png`.

---

## Bitácora

| Fecha | Qué pasó |
| --- | --- |
| — | Auditoría completa del proyecto: 3 críticos, 9 importantes, 24 menores. Redactado `REVISION_IA.md`. |
| — | Creado el kit de sincronización: snapshot en `.revision\base\`, hashes de referencia y `sincronizar.ps1`. Código **sin modificar**. |
| — | Kit probado de extremo a extremo: detección de cambios y diff verificados modificando y restaurando `app\clip_rank.py` (hash restaurado idéntico al de la línea base). Portapapeles operativo. |
| — | Montado el bucle de debate con `codex_revisar.ps1` (Codex en solo lectura, GPT-6 Luna/low) y `claude_revisar.ps1` (Claude Code en `--permission-mode plan`). Codex no puede leer archivos aquí: su servidor MCP de ficheros falla. Claude sí los lee. |
| — | Debate a tres: Codex propuso y se le corrigió el A3; Revisor B midió `loudnorm` a 192 kHz y los LUFS reales; Claude arbitró las 4 divergencias y aportó la cuarta opción del `.part`. |
| — | **Bloque A aplicado y verificado** (A1 .gitignore, A2 `-ar 48000`, A3 banda en CPU, A4 motor de voz). Los 4 con medición, no por inspección. |
| — | Claude arbitró las 4 divergencias y refutó a Revisor B en un punto (`salida\_fallidos\` sí molesta a `limpiar.py:69`). Aportó la cuarta opción del `.part`. |
| — | **Bloque B aplicado y verificado** (B1 fallback del fondo, B2 `.part` + comprobación de ffmpeg, B3 drenado de la cola, B4 validación del guion). Render real de 81 s: **48000 Hz**, 0 `.part` huérfanos, ratio de banda 0,729. |
| — | **Bloque C aplicado y verificado** (C1 `limpiar.py` 4205→1, C2 timeout del GUI, C3 registro incremental, C4 nombre con `post_id`, C5 README sin mojibake, C6 docstring de OpenCode Go). |
| — | La verificación del Bloque C destapó **dos bugs que la auditoría no vio**: un `links.txt` con BOM rompía el lote, y `lote.py` no reconfiguraba la salida a UTF-8. Ambos reproducidos y arreglados (C7 y C8). |
| — | **Kit corregido**: `.gitignore` no estaba en el conjunto vigilado por `sincronizar.ps1`, así que su cambio no salía en el diff. Añadido, con la versión original como línea base. |

---

## Cómo generar el bloque para pegar

```powershell
.\sincronizar.ps1              # genera .revision\bloque.md y lo copia al portapapeles
.\sincronizar.ps1 -Diff        # además incluye el diff completo de cada archivo cambiado
.\sincronizar.ps1 -SinPortapapeles
```

Pega el contenido de `.revision\bloque.md` en ChatGPT: lleva los hashes actuales, qué archivos
cambiaron desde su revisión, este mismo documento y las mediciones en vivo. Así siempre sabe
sobre qué versión está opinando.

### Mantenimiento (importante)

`sincronizar.ps1` **debe conservar su BOM UTF-8** (`EF BB BF` al principio del archivo). Este
entorno es Windows PowerShell 5.1, que lee los `.ps1` como ANSI cuando no hay BOM: sin él, los
acentos del script se corrompen y el bloque sale con mojibake. Si editas el archivo con una
herramienta que elimine el BOM, vuelve a añadirlo:

```powershell
$f = '.\sincronizar.ps1'
$t = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($f, $t, (New-Object System.Text.UTF8Encoding($true)))
```

El propio `bloque.md` se escribe **sin** BOM a propósito, y su contenido es UTF-8 válido. Si lo
abres con `Get-Content` en PowerShell verás `SINCRONIZACIÃ“N`: es el artefacto de consola de
siempre (lee UTF-8 como CP1252), no un fallo del archivo. Compruébalo así:

```powershell
[System.IO.File]::ReadAllText('.\REVISION_ESTADO.md', [System.Text.Encoding]::UTF8)
```

