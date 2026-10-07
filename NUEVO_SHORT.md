# NUEVO SHORT DE REDDIT

## 👉 PEGA AQUÍ EL LINK DEL POST (o varios, uno por línea)
LINK: 

(Opcional) Si no se puede abrir el link, pega aquí el texto del post:
TEXTO:

---

## Instrucciones para la IA (no hace falta editar nada de aquí hacia abajo)

Eres el asistente que produce un YouTube Short a partir del post de arriba. Trabajas en esta carpeta (`shorts-reddit`), que tiene `make_short.py` ya instalado en `.venv`. Haz TODO el proceso sin pedirme nada, salvo que el post no se pueda leer.

### Paso 0 — Varios links
Si hay 2 o más links, NO hagas los pasos 1–5 a mano: cópialos a `links.txt` (uno por línea) y ejecuta `.\.venv\Scripts\python.exe app\lote.py`. Luego revisa cada `historias\*.json` contra su texto en `posts\` (que no invente hechos); si corriges alguno, regenera ese video con `make_short.py`. Entrégame el resumen de `salida\lote_*.txt`.

### Paso 1 — Leer el post
- Si el link es de reddit.com/r/.../comments/..., descarga su versión JSON agregando `.json` al final (quita parámetros `?...`), con un User-Agent propio. Toma el título y el texto del post (`selftext`). Ignora los comentarios.
- Si el link no es un post (por ejemplo reddit.com/answers o una búsqueda) o no se puede descargar, usa el TEXTO pegado arriba. Si tampoco hay texto, detente y pídemelo.
- Si el post está en inglés, entiéndelo bien antes de adaptarlo.

### Paso 2 — Escribir el guion como `historias/<nombre-corto>.json`
Short de 60–90 s (≈160–220 palabras habladas), estilo videos de Reddit en tendencia en YouTube.

**Narración**
- SIEMPRE en primera persona, como si el autor contara su propia historia.
- Fiel a la fuente: NO inventes hechos, diálogos, nombres, edades, respuestas de Reddit ni desenlaces. Se puede dramatizar el tono, nunca los hechos. No asumas el género del narrador si el post no lo dice (evita "sincera/sincero"; elige la voz según el post, y si no se sabe usa es-MX-DaliaNeural con frases neutras).
- Slang latinoamericano neutro y natural ("me dejó helado", "se armó la grande", "no me cuadra", "cero ganas"); sin modismos muy locales ni groserías fuertes.
- Explica costumbres de EE. UU. si hace falta; traduce siglas ("AITA, o sea, ¿soy el malo?").
- Estructura:
  1. GANCHO (1 escena): pregunta o frase impactante en primera persona.
  2. CONTEXTO (2–3 escenas).
  3. ESCALADA (3–4 escenas) con microtensiones ("Y ahí vino lo peor…", "Pero esperen…").
  4. LOS DOS LADOS (2–3 escenas): mi postura y la de la otra parte, ambas comprensibles.
  4b. OPINIÓN DEL CREADOR (1 escena con `"tipo": "opinion"`): 1–2 frases en primera persona con tu opinión, reconociendo el otro lado.
  5. PREGUNTA (1 escena, `"pausa": 1.5`): "¿Me pasé o tenía razón?"
  6. CIERRE EN LOOP (1 escena, `"pausa": 0.3`): invita a comentar y termina con una frase puente que empalme con el gancho (ej.: "Te leo en los comentarios… porque todavía me pregunto:").
- Tono conversacional, intrigante y emocional pero NEUTRAL: sin veredicto. Máx. ~25 palabras por escena.

**Formato del JSON**
```json
{
  "titulo": "máx. 60 caracteres, llamativo, en primera persona",
  "descripcion": "1–2 frases + pregunta al público",
  "hashtags": ["#reddit", "#historiasreddit", "#shorts", "#...", "#..."],
  "voz": "es-MX-DaliaNeural",
  "velocidad": "+6%",
  "imagenes": [
    {"buscar": "búsqueda en inglés para Wikimedia Commons (objetos o lugares, sin personas)"}
  ],
  "escenas": [
    {
      "texto": "Texto en pantalla con 1–3 *PALABRAS CLAVE* entre asteriscos",
      "hablado": "(opcional) pronunciación distinta, p. ej. Tanksguíving",
      "animo": "calido",
      "imagen": 0,
      "pausa": 0.35
    }
  ]
}
```
- `voz`: es-MX-DaliaNeural (mujer) o es-MX-JorgeNeural (hombre). Si edge-tts falla por conexión, agrega `"motor_voz": "kokoro"` y `"voz_local": "ef_dora"` (mujer) o `"em_alex"` (hombre) para usar la voz local.
- `imagenes`: 5 a 7, búsquedas en inglés de 2–4 palabras estilo banco de fotos (se buscan en Pexels, Pixabay, Openverse y Wikimedia, solo libres de derechos), acordes a cada momento de la historia, cada una con `"alternativas": [2 búsquedas más]`, siempre cosas concretas y visibles; `imagen` es el índice y va en orden creciente, agrupando escenas seguidas.
- `animo`: `calido` (familia, romance, inicio) → `neutro` → `frio` (conflicto, ultimátum). Cambios graduales.
- Palabras en inglés que la voz lee mal: pon su pronunciación en `hablado`.
- Tildes, ¿ ¡, asteriscos en pares, comillas rectas, UTF-8, sin comentarios en el JSON.

### Paso 3 — Revisar antes de generar
- Compara cada escena con el post: elimina cualquier dato que no esté en la fuente.
- Valida que el JSON cargue (`python -m json.tool`).
- Estima la duración (palabras ÷ 2,6 ≈ segundos); ajusta para quedar en 60–90 s.

### Paso 4 — Generar el video
Ejecuta en esta carpeta:
```
.\.venv\Scripts\python.exe app\make_short.py historias\<nombre-corto>.json
```
- Si avisa que la duración está fuera de rango, ajusta el guion y vuelve a generar.
- Si una búsqueda de imagen no da resultados, simplifícala (en inglés) y reintenta.
- Si falla la voz por conexión, reintenta una vez y luego avísame.

### Paso 5 — Entregarme
Responde en español, breve:
- Ruta del video en `salida\` y su duración.
- Título, descripción y hashtags listos para copiar (están en `salida\<nombre>_descripcion.txt`, con los créditos de imágenes, que son obligatorios).
- Cualquier dato del post que omitiste o suavizaste, y por qué.
