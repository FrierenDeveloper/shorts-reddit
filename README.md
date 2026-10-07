# Shorts Reddit (local)

## Versión Android

La adaptación nativa con render en el teléfono está en `android/`. La versión actual del APK es **1.1.2** (versionCode 4). Consulta `android/LEEME_ANDROID.md` para instalar, transferir los archivos y conocer las diferencias respecto al motor de PC. Incluye voces locales Daniela, Claude y Kokoro opcional, selección independiente de narrador/opinión y análisis contextual de emoción, suspenso, énfasis y pausas. Consulta `android/INTERPRETACION_VOZ.md` para el alcance de las órdenes. El APK y el paquete de entrega se generan en `entrega-android/` con los scripts de compilación de `android/`.

Los instaladores y el paquete completo se publican en las [releases del repositorio](https://github.com/FrierenDeveloper/shorts-reddit/releases). La entrega excluye la biblioteca antigua y las claves privadas.

## Estructura
```
CREAR_SHORT.bat   LOTE.bat   LIMPIAR.bat   (+ versiones _CHATTERBOX)   INSTALAR*.bat
links.txt         ← pega aquí los links o posts\archivo.txt
config\           llm.json (DeepSeek) y claves.json (Pexels/Pixabay) — no compartir
historias\        guiones JSON            posts\  textos originales de Reddit
salida\Reddit\         videos, descripciones y créditos de historias de Reddit
salida\Salud_Mental\   videos, descripciones y créditos de salud mental
salida\Psicologia_Diaria\ videos, descripciones y créditos sobre psicología cotidiana
salida\subidos\   muévelos aquí cuando los publiques
salida\registros\ resúmenes de cada lote
musica\  voces\   tus archivos (opcionales)
app\              código, fuentes, modelos e instaladores (no tocar)
cache\            temporal: se vacía solo
```

## Buenas prácticas para no acumular basura
- Cada video borra al terminar sus imágenes descargadas, miniaturas y audios temporales (automático).
- Cuando publiques un video, usa la app para mover el .mp4 y sus .txt a salida\subidos\ (conserva la carpeta del tema).
- Ejecuta LIMPIAR.bat una vez por semana: vacía caché/temporales y te PREGUNTA antes de borrar
  videos ya subidos (+7 días), registros (+30 días) y guiones/textos (+60 días). Nunca toca videos sin publicar.
- Para conservar la caché (p. ej. re-renderizar varias veces seguidas): $env:SHORTS_MANTENER_CACHE="1".


Genera Shorts 9:16 de historias de Reddit **en tu PC**: voz, subtítulos animados, fondo con fotos libres, música y créditos.

## Instalar (una vez)
PowerShell en esta carpeta:
    powershell -ExecutionPolicy Bypass -File .\instalar.ps1

Instala Python 3.12, FFmpeg y las librerías (edge-tts, faster-whisper, etc.) en un entorno `.venv`.

## Flujo
1. **Guion** (elige uno):
   - Con IA local (LM Studio con un modelo cargado y el servidor encendido):
         .\.venv\Scripts\python.exe guion.py post.txt mi_historia
   - Con un proveedor compatible con OpenAI (DeepSeek, LM Studio, Ollama…): define antes `LLM_BASE_URL`, `LLM_API_KEY` y `LLM_MODEL` (ver guion.py). **OpenCode Go no sirve tal cual**: su endpoint exige la cabecera `x-opencode-session`, que este cliente no envía.
   - O pégale `prompt_guion.md` + el post a cualquier chat y guarda el JSON en `historias\`.
2. **Revisa** `historias\mi_historia.json` (hechos fieles al post, tildes, *palabras resaltadas*).
3. **Video**:
         .\.venv\Scripts\python.exe make_short.py historias\mi_historia.json
   (o arrastra el .json sobre `CREAR_SHORT.bat`)
4. En `salida\Reddit\`, `salida\Salud_Mental\` o `salida\Psicologia_Diaria\` quedan los archivos de cada video.

## Ajustes útiles en el JSON
- `voz`: es-MX-DaliaNeural, es-MX-JorgeNeural, es-CO-SalomeNeural, es-AR-ElenaNeural, es-US-AlonsoNeural…
  (lista completa: `.\.venv\Scripts\edge-tts.exe --list-voices | findstr es-`)
- `velocidad`: "+0%" a "+12%".
- `imagenes`: 5 o 6. `{"buscar": "..."}` (en inglés; `"opcion": 1` para tomar el 2º resultado) o `{"archivo": "mis_fotos/x.jpg"}`.
- `aviso`: texto pequeño inicial ("" para quitarlo). `volumen_musica`: 0 a 2.

Necesita internet para la voz (edge-tts) y las imágenes; el render usa solo tu CPU (~3–6 min por video).

## GPU NVIDIA y voces locales (opcional)
Después de INSTALAR.bat, ejecuta **INSTALAR_GPU.bat** (PyTorch CUDA, Kokoro, XTTS; ~3–4 GB).

- **Render**: si hay CUDA, los fotogramas se componen en la GPU; si no, en paralelo con todos los núcleos de la CPU.
  Forzar CPU: `$env:SHORTS_RENDER="cpu"`.
- **Codificación**: usa NVENC con CQ 20 si tu FFmpeg lo soporta; si no, libx264 con preset `slow`, CRF 20 y tope VBV de 12 Mbps / buffer 24 Mbps. H.264 sale en `yuv420p`, con audio AAC 192 kbps y etiquetas BT.709. Forzar CPU: `$env:SHORTS_CPU_ENCODER="1"`.
- **Voz** (campo `motor_voz` en el JSON):
  - `"edge"` (por defecto): online, voces latinas (`"voz": "es-MX-DaliaNeural"`).
  - `"kokoro"`: local, sin internet, uso comercial permitido. `"voz_local": "ef_dora"` (mujer) o `"em_alex"` (hombre).
  - `"xtts"`: local en GPU, puede **clonar una voz** con `"voz_referencia": "mi_voz.wav"` (6–15 s limpios).
    ⚠ Licencia Coqui CPML: **no permite uso comercial** (canal monetizado). Úsalo solo para pruebas.
  - Con kokoro/xtts, los subtítulos se sincronizan con faster-whisper (en GPU).

## Imágenes libres de derechos (mejor calidad)
Se buscan en este orden y solo se aceptan fotos de al menos 1080×1013 px (la referencia vertical son 1080×1350), prefiriendo verticales:
1. **Pexels** y 2. **Pixabay**: fotos profesionales, uso libre y comercial. Necesitan una clave gratis:
   - Pexels: https://www.pexels.com/api/ → "Get Started" → copia tu API key.
   - Pixabay: https://pixabay.com/api/docs/ (con sesión iniciada, la clave aparece en la página).
   - Copia `claves.ejemplo.json` como `config\claves.json` y pega las claves.
3. **Openverse** y 4. **Wikimedia Commons**: solo CC0 / Dominio Público (sin copyright). No necesitan clave.

Sin claves funciona igual, usando solo Openverse y Wikimedia. Cambiar el orden en el JSON: `"fuentes": ["pixabay", "pexels", "openverse"]`.
Nunca repite la misma foto en un video. Los créditos quedan junto al video en su carpeta temática (en Pexels/Pixabay no son obligatorios, pero es buena práctica).

## Fondo satisfactorio para historias de Reddit
En la GUI, deja activada **Fondo satisfactorio aleatorio** y elige **Pixabay** o **Pexels** para añadir hasta cuatro clips silenciosos del mismo tema (arena, jabón, slime y otras acciones) en cada generación, en las tres temáticas: **Historias de Reddit**, **Salud mental** y **Psicología de la vida diaria**. Desactívala para conservar las imágenes temáticas. Se descartan los clips de menos de 15 segundos y se prefieren los de 20 segundos o más. Cada clip ocupa la pantalla completa en 9:16, recortando los lados de videos horizontales cuando hace falta. La narración y los subtítulos van encima.

La app usa las claves de Pexels o Pixabay ya guardadas en `config\claves.json`, busca clips y conserva temporalmente los resultados durante 24 horas. Si la búsqueda falla o falta la clave elegida, usa la biblioteca local `videos_fondo\`. La GUI enlaza a Pexels cuando se selecciona esa fuente, siguiendo sus indicaciones para la API. Los renders no añaden créditos del fondo al video ni a la descripción.

## Varios videos de una vez (lote)
1. Configura el LLM una vez: copia `llm.ejemplo.json` como `config\llm.json` (LM Studio local, u OpenCode Go/DeepSeek con tu clave).
2. Pega de 4 a 10 links de Reddit en `links.txt`, uno por línea (links de post: `.../comments/...`).
3. Doble clic en **LOTE.bat**.
   Por cada link: lee el post (solo el texto, sin comentarios) → escribe el guion → genera el video.
   Si un link falla (post borrado, solo imagen, Reddit bloqueó la lectura), lo salta y sigue con el resto.
4. En `salida\Reddit\` quedan los videos; `salida\registros\lote_<fecha>.txt` guarda el resumen. Los textos originales quedan en `posts\`
   para que revises que el guion no invente nada.

## Si Reddit bloquea la lectura
El lote prueba 3 rutas: API oficial (si hay claves) → JSON público → RSS. Para que sea 100 % confiable,
crea una app gratis de Reddit (2 minutos):
1. Con tu cuenta de Reddit, entra a https://www.reddit.com/prefs/apps → "create another app…".
2. Nombre: shorts-local · tipo: **script** · redirect uri: http://localhost:8080 → "create app".
3. El **client_id** es el código bajo "personal use script"; el **secret** aparece como "secret".
4. Pégalos en `config\claves.json` en `reddit_client_id` y `reddit_client_secret`.
Sin claves: si un link falla, copia el texto del post a `posts\mi_post.txt` (1ª línea = título) y pon `posts\mi_post.txt` en links.txt en lugar del link.

## Elementos de retención (activados por defecto)
Tarjeta estilo post al inicio · barra de progreso · palabra actual en verde (karaoke) · encuesta final · efectos de sonido.
Para desactivar alguno en un video, agrega al JSON:
    "extras": {"tarjeta": true, "barra": true, "karaoke": true, "encuesta": true, "sonidos": true}
Cambiar los botones de la encuesta:  "encuesta": ["TIENE RAZÓN", "SE PASÓ"]
Cambiar el subreddit de la tarjeta:  "subreddit": "r/AmItheAsshole"

## Plantillas, música y opinión
- Plantillas ("plantilla" en el JSON; por defecto "aleatoria"): clasica · impacto · noche · diario · pop.
  Cambian tipografía, colores, ritmo de subtítulos, posición, tarjeta, barra, fondo, música y velocidad de voz.
- Música: pistas sin copyright en la carpeta musica\ → usa una al azar; si está vacía, compone una nueva
  (libre de derechos) en el estilo de la plantilla. Baja sola cuando habla la voz. "volumen_musica": 0.5–1.5.
- Opinión del creador: escena con "tipo": "opinion" → otra voz ("voz_opinion") + etiqueta "MI OPINIÓN".
  Con TU voz: graba un audio, guárdalo en la carpeta y pon en esa escena "audio": "mi_opinion.mp3".

## Voz con Chatterbox (opcional, local en la GPU)
1. Una vez: INSTALAR_CHATTERBOX.bat (entorno aparte con Python 3.11, ~4 GB).
2. Opcional: graba tu voz en voces\narrador.wav y/o voces\opinion.wav (ver voces\LEEME.txt).
3. Usa CREAR_SHORT_CHATTERBOX.bat o LOTE_CHATTERBOX.bat en lugar de los normales.
Licencia MIT (uso comercial permitido). Los audios llevan una marca de agua inaudible de Resemble AI.
