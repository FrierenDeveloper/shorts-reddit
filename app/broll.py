"""B-roll de vídeo COHERENTE CON EL TEXTO, tramo a tramo.

Problema que resuelve
---------------------
`fondos_satisfactorios.obtener_clips(fuente)` elige UN tema global al azar de `TEMAS`
(arena cinética, jabón, slime...) para TODO el vídeo, y `make_short.py` reparte esos 4
clips cada `segundos_clip` (10 s por defecto). Los guiones, en cambio, traen 15-20 escenas
para 5-7 fotos, así que un mismo plano puede quedarse hasta 15.6 s en pantalla.

Este módulo parte el guion en TRAMOS (grupos de escenas consecutivas que comparten
`imagen`), garantiza que NINGÚN tramo pase de `max_s` segundos (7 s por defecto) y propone
para cada tramo una consulta de búsqueda EN INGLÉS de 2-4 palabras derivada del propio
texto, para pedir un clip distinto y coherente en cada tramo.

API pública
-----------
- `tramos(cfg, seg_times=None) -> list[dict]`
- `plan(cfg, seg_times=None, max_s=7.0) -> list[dict]`
- `buscar_clips(plan, fuente="pixabay", cache_dir=None, max_por_tramo=1) -> list[dict]`

Ninguna de las tres lanza excepción por falta de red, de claves o de clips: degradan a
`"clip": None` con el motivo en `"error"`. Este módulo NO modifica nada fuera de sí mismo.

Cómo se integraría en make_short.py (NO lo he cambiado)
------------------------------------------------------
Hoy, el bloque de fondo de vídeo es esto (líneas ~947-955; los números bailan porque el
archivo se está editando, busca el texto):

    if video_bg:
        import fondos_satisfactorios as FS
        print("2/4 Eligiendo fondo satisfactorio…")
        try:
            clips, tema = FS.obtener_clips(cfg.get("fuente_videos", "pixabay"))
            video_bg_frames, video_bg_fps, frames_dir = FS.preparar_frames(
                clips, total, seg_por_clip=float(cfg.get("segundos_clip", 10)))
            TEMPORALES.append(frames_dir)
            spans = [(0, -0.4, total + 1)]

Sustitución propuesta (mismo contrato de salida: `video_bg_frames`, `video_bg_fps`,
`spans`; las líneas 1160+ y el pintado en `_S["video_bg_frames"]`, ~líneas 719-724, no
cambian):

    if video_bg:
        import fondos_satisfactorios as FS
        import broll as B
        print("2/4 Eligiendo fondo satisfactorio…")
        try:
            pl = B.plan(cfg, seg_times, max_s=float(cfg.get("segundos_clip", 7)))
            pl = B.buscar_clips(pl, cfg.get("fuente_videos", "pixabay"))
            frames, fps_bg = [], 15
            for t in pl:
                if not t["clip"]:
                    continue                      # tramo sin clip: se salta y el índice
                dur = max(t["t1"] - t["t0"], 1.0)  # modular reutiliza el resto
                f, fps_bg, d = FS.preparar_frames([t["clip"]], dur, fps=fps_bg,
                                                  seg_por_clip=dur)
                TEMPORALES.append(d)
                frames.extend(f)
            if not frames:
                raise RuntimeError("broll sin clips utilizables")
            video_bg_frames, video_bg_fps = frames, fps_bg
            spans = [(0, -0.4, total + 1)]
        except RuntimeError as e:
            print(f"   ⚠ {e}")
            print("   → sigo con el fondo de fotos temáticas")
            video_bg = False

Detalles verificados de esa sustitución:
- `FS.preparar_frames(clips, segundos, fps=15, seg_por_clip=SEGUNDOS_CLIP)` acepta una lista
  de clips y los segundos exactos del tramo, así que se puede llamar UNA vez por tramo. Crea
  un directorio temporal por llamada (todos van a `TEMPORALES`, se limpian igual).
- `_S["video_bg_frames"]` se indexa con `int(t * fps) % len(frames)`, o sea que el orden de
  concatenación ES el orden temporal: por eso los tramos se recorren en orden de `i`.
- AVISO no medido por mí: el número de fotogramas que produce `-t dur` con `fps=15` puede
  diferir en ±1 del esperado `round(dur*fps)`, y ese desfase no se corrige dentro del bucle;
  se traduce en un desplazamiento de pocos fotogramas del fondo, no en un fallo. Si se quiere
  exactitud, lo suyo es que `fondos_satisfactorios` gane una variante que reciba la lista de
  tramos y controle el conteo de fotogramas por tramo (yo no la he escrito: no toco otros
  archivos).
- Un tramo sin clip se salta: el índice modular sigue cubriendo su franja de tiempo con los
  fotogramas del vecino, así que el vídeo nunca se queda sin fondo.

Calibración de duraciones (medida, no inventada)
------------------------------------------------
Con `seg_times=None` las duraciones se estiman. El ritmo de voz se calibró con 9 pares
reales guion↔mp4 de `salida/Reddit` medidos con ffprobe (`format=duration`): la suma de voz
menos cabecera y pausas da 0.2966 s por palabra (3.37 palabras/s, +6% de velocidad), error
medio 2.2 s sobre 60-70 s de vídeo. Para el guion de prueba
`historias/20260930_0839_...json` la estimación da 67.5 s y el mp4 real de esa misma
historia dura 66.2 s. Se usa `PALABRA_S = 0.30` redondeado.

Búsqueda de clips (endpoints REALES, leídos de fondos_satisfactorios.py)
-----------------------------------------------------------------------
`obtener_clips(fuente)` sólo acepta `fuente` (no admite consulta ni tema: el tema lo sortea
con `random.choice(TEMAS)`), así que la búsqueda por consulta se implementa aquí copiando
los endpoints que ya usa el proyecto:
- Pixabay: `https://pixabay.com/api/videos/` con `key, q, per_page, safesearch, order`
  (fondos_satisfactorios.py:121) y descarga de `videos.<medium|small|large>.url` en
  `cdn.pixabay.com` (fondos_satisfactorios.py:60-94).
- Pexels: `https://api.pexels.com/v1/videos/search` con cabecera `Authorization` y
  `query, per_page, orientation` (fondos_satisfactorios.py:201) y descarga de
  `video_files[].link` en `player.vimeo.com|videos.pexels.com|cdn.pexels.com`
  (fondos_satisfactorios.py:145-188).
La descarga reutiliza `fondos_satisfactorios._descargar_hit` / `_descargar_pexels` cuando el
módulo es importable (su firma SÍ acepta el directorio de caché), y si no (p. ej. intérprete
sin `requests`), cae a `_descargar()` de aquí, con las MISMAS reglas de host y tamaño.

Cómo se elige el clip (y por qué así)
-------------------------------------
La primera prueba en vivo contra Pixabay devolvió, para un tramo de hospital, un clip de
`type: "animation"` con un hígado dibujado: sus tags casaban más términos de la consulta que
el metraje real. Por eso el orden de preferencia de `_elegir` es: metraje real antes que
animación/IA/baja calidad (`type`, `isAiGenerated`, `isLowQuality`, campos comprobados en las
respuestas), luego más términos de la consulta en los tags, luego el orden de relevancia que
ya dio el banco, y sólo al final el clip más largo. Además la petición a Pixabay lleva
`video_type=film` (parámetro verificado en vivo: 25/25 hits "film" frente a 20 "film" + 5
"animation" sin él). No se usa azar en ninguna fase: la misma caché da el mismo clip.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

try:                        # requests es opcional: tramos()/plan() deben funcionar sin red
    import requests
except Exception:           # ImportError, o cualquier binario roto
    requests = None

# Los avisos de este módulo llevan ⚠ y → : una consola Windows en cp1252 reventaba con
# UnicodeEncodeError al imprimirlos. Mismo blindaje que make_short.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# --- parámetros del corte en tramos ------------------------------------------------------
MAX_TRAMO_S = 7.0           # tope duro: ningún tramo puede durar más que esto
CABECERA_S = 0.4            # make_short arranca el audio en t = 0.4 (línea ~821: t = 0.4)
PALABRA_S = 0.30            # calibrado contra 9 mp4 reales (ver docstring del módulo)
MIN_ESCENA_S = 0.9          # una escena corta igual ocupa casi un segundo
FALLBACK_CONSULTA = "family home"

# --- parámetros de la búsqueda -----------------------------------------------------------
CLIP_MIN_S = 3.0            # por debajo de esto el clip es demasiado corto para un tramo
CLIP_PREF_S = 8.0           # preferencia: clips que cubren un tramo entero de 7 s
TIMEOUT_BUSQ = 25
TIMEOUT_DESC = (15, 90)
TTL_CACHE_S = 24 * 3600
MAX_DESCARGA_B = 150 * 1024 * 1024
PER_PAGE = 25

# Endpoints copiados de fondos_satisfactorios.py (NO inventados).
URL_PIXABAY = "https://pixabay.com/api/videos/"                 # FS:121
URL_PEXELS = "https://api.pexels.com/v1/videos/search"          # FS:201
URL_COVERR = "https://coverr.co/api/videos"                     # sin clave (endpoint del sitio)
HOSTS_PIXABAY = {"cdn.pixabay.com"}                             # FS:66
HOSTS_PEXELS = {"player.vimeo.com", "videos.pexels.com", "cdn.pexels.com"}   # FS:160
HOSTS_COVERR = {"cdn.coverr.co"}
HOSTS = {"pixabay": HOSTS_PIXABAY, "pexels": HOSTS_PEXELS, "coverr": HOSTS_COVERR}
# Fuentes de vídeo usables. Medido en vivo: Pexels devuelve 30/30 clips VERTICALES 1080x1920;
# Pixabay apenas tiene vertical (0 de 30 en "hospital corridor", 2 de 30 en "empty dinner
# table"); Coverr no necesita clave pero es casi todo horizontal (el pipeline lo recorta).
FUENTES_VALIDAS = ("pexels", "pixabay", "coverr")
SIN_CLAVE = ("coverr",)          # funcionan sin clave de API
DEFAULT_VIDEO = "pexels"         # mejor relación vertical/disponibilidad de las tres

# Campos reales de las respuestas, comprobados sobre respuestas cacheadas y una petición en
# vivo (no inventados):
#   Pixabay -> type ("film" | "animation"), isAiGenerated, isLowQuality, isGRated, duration, tags
#   Pexels  -> SIN 'type' y con tags casi siempre vacío: se puntúa por el slug de 'url'
# `video_type=film` en la petición a Pixabay también es real: medido en vivo, 25/25 hits
# "film" frente a 20 "film" + 5 "animation" sin el parámetro (totalHits 305 vs 471).
NO_FILMABLE = re.compile(r"animation|animated|cartoon|illustration|render|rendered|motion graphic|"
                         r"abstract|plexus|geometric|screensaver|wallpaper|green screen|"
                         r"ai.generat|generated by ai|user-ai-", re.I)

# Stopwords: lista STOP de make_short.py (líneas ~363-364, copiada literal) + español.
STOP = {"with", "from", "the", "and", "for", "into", "over", "under", "near", "photo", "image", "empty", "hand", "hands",
        "a", "an", "of", "on", "in", "to", "at", "by", "or", "and",
        # español
        "que", "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "o", "u", "en", "con", "sin", "por",
        "para", "mi", "mis", "tu", "tus", "su", "sus", "me", "te", "se", "le", "les", "lo", "nos", "al", "del", "es",
        "son", "era", "eran", "fue", "fueron", "ser", "esta", "este", "esto", "estas", "estos", "ese", "esa", "eso",
        "esos", "esas", "hay", "ya", "mas", "muy", "no", "ni", "si", "sí", "como", "cuando", "donde", "porque", "pero",
        "tambien", "tampoco", "todo", "toda", "todos", "todas", "nada", "nadie", "algo", "alguien", "solo", "cada",
        "aqui", "ahi", "alli", "hoy", "ayer", "manana", "ahora", "antes", "despues", "luego", "entonces", "aunque",
        "mientras", "casi", "cada", "otro", "otra", "otros", "otras", "mismo", "misma", "tan", "tanto", "tanta",
        "tenia", "tenian", "tiene", "tienen", "tener", "hace", "hacia", "hasta", "desde", "entre", "sobre", "bajo",
        "puede", "pueden", "puedo", "puedes", "quiere", "quieren", "queria", "queria", "dijo", "dice", "dicen",
        "dijeron", "creo", "cree", "creen", "parece", "parecen", "vez", "veces", "cosa", "cosas", "parte", "lado",
        "gente", "persona", "personas", "momento", "rato", "dia", "dias", "ano", "anos", "semana", "semanas", "mes",
        "meses", "hora", "horas", "minuto", "minutos", "vez", "veces", "tema", "caso", "forma", "manera", "gracias",
        "favor", "pues", "bueno", "buena", "malo", "mala", "mucho", "mucha", "muchos", "muchas", "poco", "poca",
        "pocos", "pocas", "mas", "menos", "tan", "muy", "aun", "aun", "quizas", "quiza", "ojala", "sino", "ademas",
        "incluso", "siempre", "nunca", "jamas", "tarde", "temprano", "aqui", "alli", "ahi", "voy", "vas", "va",
        "vamos", "van", "estoy", "estas", "esta", "estamos", "estan", "estaba", "estaban", "he", "has", "ha", "han",
        "hemos", "habia", "habian", "fui", "fuiste", "fuimos", "dije", "dijiste", "hicimos", "hice", "hizo",
        "hicieron", "ver", "vio", "vi", "visto", "decir", "dicho", "hacer", "hecho", "ir", "irse", "dar", "darle",
        "poner", "quedar", "quedo", "pasar", "paso", "pasado", "saber", "sabe", "sabia", "querer", "gusta",
        "gustaria", "entiendo", "entiende", "entienden", "suele", "suelen", "realmente", "literalmente", "reddit",
        "comentarios", "cuentenme", "leo", "opinion", "historia", "video", "shorts", "short"}

# Palabras que sí valen como término de búsqueda visual (ES->EN).
# Criterio: el valor tiene que ser algo que exista como metraje de banco (objeto, lugar,
# persona o situación filmable). Lo abstracto que no se puede filmar NO entra: esos tramos
# se quedan con las palabras de `imagenes[i]["buscar"]`, que ya son coherentes.
VISUAL = {
    # familia y personas
    "madre": "mother", "mama": "mother", "mami": "mother", "padre": "father", "papa": "father", "papi": "father",
    "padrastro": "father", "madrastra": "mother", "esposa": "wife", "mujer": "wife", "esposo": "husband",
    "marido": "husband", "novio": "boyfriend", "novia": "girlfriend", "pareja": "couple", "prometida": "fiance",
    "hijo": "family", "hija": "family", "hijos": "family", "hijas": "family", "nino": "family", "nina": "family",
    "ninos": "family", "ninas": "family", "bebe": "family", "hermano": "siblings", "hermana": "siblings",
    "hermanos": "siblings", "hermanas": "siblings", "suegra": "inlaws", "suegro": "inlaws", "abuelo": "grandparents",
    "abuela": "grandparents", "tio": "uncle", "tia": "aunt", "primo": "cousin", "sobrino": "family", "familia": "family",
    "familiar": "family", "familiares": "family", "amigo": "friends", "amiga": "friends", "amigos": "friends",
    "amigas": "friends", "vecino": "neighbors", "vecina": "neighbors", "vecinos": "neighbors", "companero": "coworkers",
    "companera": "coworkers", "jefe": "boss", "medico": "doctor", "doctor": "doctor", "doctora": "doctor",
    "enfermera": "nurse", "abogado": "lawyer", "juez": "judge", "policia": "police", "soldado": "soldier",
    "profesor": "teacher", "alumno": "student", "desconocido": "stranger", "extrano": "stranger", "hombre": "man",
    "senora": "woman", "chico": "young man", "chica": "young woman", "gente": "crowd", "multitud": "crowd",
    # cuerpo y salud
    "hospital": "hospital", "clinica": "hospital", "cama": "bed", "cirugia": "surgery", "operacion": "surgery",
    "cancer": "cancer", "quimio": "chemotherapy", "tratamiento": "treatment", "diagnostico": "diagnosis",
    "diagnosticaron": "diagnosis", "diagnostica": "diagnosis", "enfermedad": "sick", "enfermo": "sick",
    "enferma": "sick", "sintoma": "sick", "sintomas": "sick", "salud": "health", "medicina": "medicine",
    "medicamento": "medicine", "medicamentos": "medicine", "pastilla": "pills", "pastillas": "pills",
    "receta": "prescription", "inyeccion": "injection", "sangre": "blood", "herida": "injury", "dolor": "pain",
    "cerebro": "brain", "mente": "brain", "mental": "brain", "psicologia": "psychologist", "psicologo": "psychologist",
    "terapia": "therapy", "trastorno": "psychologist", "sindrome": "brain", "ansiedad": "anxious", "panico": "panic",
    "depresion": "sad", "miedo": "scared", "asustado": "scared", "triste": "sad", "tristeza": "sad", "llorando": "crying",
    "llora": "crying", "lloro": "crying", "llore": "crying", "grito": "arguing", "gritando": "arguing",
    "pelea": "argument", "discusion": "argument", "discutiendo": "arguing", "muerte": "funeral", "murio": "funeral",
    "funeral": "funeral", "cementerio": "cemetery", "entierro": "funeral", "embarazo": "pregnant", "embarazada": "pregnant",
    "sueno": "sleeping", "dormir": "sleeping", "duerme": "sleeping", "cansado": "tired",
    "borracho": "drunk", "alcohol": "alcohol", "cerveza": "beer", "copa": "wine glass",
    "cafe": "coffee cup", "comida": "food", "cena": "dinner", "desayuno": "breakfast", "desayunar": "breakfast",
    "almuerzo": "lunch", "cocina": "kitchen", "cocinar": "cooking", "cocino": "cooking", "comer": "eating",
    # casa y objetos
    "casa": "house", "hogar": "home", "departamento": "apartment", "apartamento": "apartment", "cabana": "cabin",
    "cuarto": "bedroom", "habitacion": "bedroom", "sala": "living room", "sofa": "sofa", "mesa": "table",
    "silla": "chair", "puerta": "door", "ventana": "window", "espejo": "mirror", "jardin": "garden",
    "patio": "backyard", "garaje": "garage", "llaves": "keys", "llave": "keys", "reloj": "clock", "calendario": "calendar",
    "telefono": "smartphone", "celular": "smartphone", "movil": "smartphone", "mensaje": "text message",
    "mensajes": "text message", "llamada": "phone call", "llamo": "phone call", "escribio": "typing",
    "escribiendo": "typing", "correo": "email inbox", "email": "email inbox", "computadora": "laptop",
    "portatil": "laptop", "laptop": "laptop", "pantalla": "screen", "television": "television", "tele": "television",
    "dinero": "money", "dolares": "money", "billetes": "money", "pago": "money", "deuda": "money", "banco": "bank",
    "tarjeta": "credit card", "cartera": "wallet", "cuenta": "bank", "factura": "invoice", "contrato": "contract",
    "documento": "documents", "documentos": "documents", "papel": "paper", "papeles": "documents", "carta": "letter",
    "foto": "photo frame", "fotos": "photo frame", "retrato": "portrait", "album": "photo album",
    "regalo": "gift", "regalos": "gift", "juguete": "toys", "juguetes": "toys", "libro": "books", "libros": "books",
    "cuaderno": "notebook", "ropa": "clothes", "abrigo": "coat", "zapatos": "shoes", "anillo": "wedding ring",
    "boda": "wedding", "casamiento": "wedding", "divorcio": "divorce", "collar": "necklace", "flores": "flowers",
    "planta": "plant", "mascota": "pet", "perro": "dog", "gato": "cat", "nevera": "refrigerator",
    "lavadora": "laundry",
    # lugares y transporte
    "trabajo": "office work", "oficina": "office", "reunion": "meeting", "empresa": "office", "coche": "car",
    "auto": "car", "carro": "car", "camioneta": "car", "autobus": "bus", "tren": "train", "avion": "airplane",
    "vuelo": "airport", "aeropuerto": "airport", "viaje": "travel", "maleta": "suitcase", "mudanza": "moving boxes",
    "mudamos": "moving boxes", "mudo": "moving boxes", "calle": "street", "camino": "road",
    "carretera": "road", "ciudad": "city", "parque": "park", "playa": "beach", "mar": "sea", "montana": "mountains",
    "bosque": "forest", "campo": "countryside", "rio": "river", "lluvia": "rain", "nieve": "snow", "sol": "sunlight",
    "noche": "night", "iglesia": "church", "escuela": "school", "colegio": "school", "universidad": "university",
    "clase": "classroom", "clases": "classroom", "examen": "exam", "tienda": "store", "super": "supermarket",
    "restaurante": "restaurant", "bar": "bar", "hotel": "hotel", "carcel": "prison", "corte": "courthouse",
    "juzgado": "courthouse", "fiesta": "party", "cumpleanos": "birthday party", "gimnasio": "gym", "piscina": "pool",
    "biblioteca": "library", "museo": "museum", "puente": "bridge", "edificio": "building", "ascensor": "elevator",
    # acciones filmables
    "silencio": "quiet", "tranquilo": "quiet", "sola": "alone", "esperando": "waiting",
    "espera": "waiting", "espero": "waiting", "abrazo": "hug", "abrazando": "hug", "beso": "kiss",
    "hablando": "talking", "hablar": "talking", "hablo": "talking", "conversando": "talking", "disculpa": "apology",
    "disculparse": "apology", "disculpe": "apology", "perdon": "apology", "excusa": "apology", "error": "mistake",
    "mentira": "lying", "mentiroso": "lying", "verdad": "truth", "confiar": "handshake", "confianza": "handshake",
    "trabajando": "working", "corriendo": "running", "caminando": "walking", "manejando": "driving",
    "leyendo": "reading", "mirando": "looking", "escondido": "hiding", "encerrado": "locked door",
}
# Passthrough de términos ingleses que ya vienen en el texto o en `buscar`.
VISUAL.update({k: k for k in (
    "hospital", "cancer", "doctor", "nurse", "wedding", "funeral", "money", "house", "home", "office",
    "family", "mother", "father", "wife", "husband", "phone", "laptop", "kitchen", "dinner", "table",
    "photo", "frame", "rain", "night", "city", "street", "car", "travel", "airport", "school", "church", "dog",
    "cat", "sad", "crying", "scared", "waiting", "hug", "apology", "argument", "arguing", "walking", "reading",
    "bed", "window", "door", "mirror", "coffee", "beer", "wine", "food", "laundry", "garden", "hands", "sunlight",
)})
VISUAL_PRIORITARIO = {   # sustantivos/objetos: mejor material de banco que un verbo
    "hospital", "cancer", "doctor", "nurse", "wedding", "funeral", "money", "house", "home", "office",
    "family", "mother", "father", "wife", "husband", "phone", "smartphone", "laptop", "kitchen", "dinner",
    "table", "photo frame", "frame", "rain", "night", "city", "street", "car", "travel", "airport", "school",
    "church", "dog", "cat", "bed", "window", "door", "mirror", "coffee cup", "beer", "wine", "food", "laundry",
    "garden", "sunlight", "pills", "medicine", "blood", "brain", "suitcase", "moving boxes", "calendar", "clock",
    "documents", "letter", "gift", "toys", "books", "flowers", "plant", "ring", "necklace", "keys", "sofa", "chair",
    "apartment", "cabin", "bedroom", "living room", "backyard", "garage", "airplane", "train", "bus", "road",
    "beach", "sea", "mountains", "forest", "countryside", "river", "snow", "park", "classroom", "store",
    "supermarket", "restaurant", "bar", "hotel", "prison", "courthouse", "party", "gym", "pool", "library",
    "museum", "bridge", "building", "elevator", "crowd", "judge", "lawyer", "police", "teacher", "student",
    "grandparents", "inlaws", "siblings", "friends", "neighbors", "coworkers", "couple", "pregnant",
}


# -----------------------------------------------------------------------------------------
# utilidades de texto
# -----------------------------------------------------------------------------------------
def _norm(texto):
    """Minúsculas y sin acentos: 'cáncer' -> 'cancer', 'Mamá' -> 'mama'."""
    base = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _palabras(texto):
    return re.findall(r"[a-z0-9]+", _norm(texto))


def _sin_asteriscos(texto):
    return re.sub(r"\*+", "", str(texto or "")).strip()


def _enfatizadas(texto):
    """Palabras marcadas con *asteriscos* en el guion: son el ancla semántica de la escena."""
    salida = []
    for trozo in re.findall(r"\*([^*]+)\*", str(texto or "")):
        for w in _palabras(trozo):
            if w not in salida:
                salida.append(w)
    return salida


def _visual(palabra):
    """Término inglés buscable para una palabra española (con plurales perezosos)."""
    if not palabra:
        return None
    if palabra in VISUAL:
        return VISUAL[palabra]
    for sufijo in ("es", "s"):
        if palabra.endswith(sufijo) and palabra[: -len(sufijo)] in VISUAL:
            return VISUAL[palabra[: -len(sufijo)]]
    return None


def _base_palabras(base, maximo=2):
    """Palabras útiles de `imagenes[i]['buscar']` (ya viene en inglés y coherente)."""
    salida = []
    for w in _palabras(base):
        if w in STOP or len(w) <= 2 or w.isdigit():
            continue
        if w not in salida:
            salida.append(w)
        if len(salida) >= maximo:
            break
    return salida


def _claves_texto(texto, maximo=2):
    """2 palabras inglesas filmables derivadas del texto, priorizando las enfatizadas."""
    enfatizadas = _enfatizadas(texto)
    orden, vistos = [], set()
    for w in enfatizadas + _palabras(texto):
        if w in vistos or w in STOP:
            continue
        vistos.add(w)
        termino = _visual(w)
        if termino:
            orden.append((termino, w in enfatizadas))
    # Primero las enfatizadas, dentro de cada grupo en orden de aparición.
    orden.sort(key=lambda par: not par[1])
    salida = []
    for termino, _ in orden:
        if termino not in salida:
            salida.append(termino)
    # Los sustantivos (objetos, lugares) dan mejor metraje que los verbos: van delante.
    salida.sort(key=lambda t: t not in VISUAL_PRIORITARIO)
    return salida[:maximo]


def _consulta(texto, base):
    """Consulta EN INGLÉS de 2-4 palabras: ancla de la imagen + palabras del texto."""
    palabras = _base_palabras(base, maximo=2)
    for termino in _claves_texto(texto, maximo=2):
        for w in termino.split():
            if len(palabras) >= 4:
                break
            if w not in palabras:
                palabras.append(w)
    if not palabras:
        palabras = _base_palabras(base, maximo=3) or _claves_texto(texto, maximo=3)
    if not palabras:
        return FALLBACK_CONSULTA
    return " ".join(palabras[:4])


def _variantes(consulta):
    """Recortes de una consulta, de la más específica a la más general."""
    w = str(consulta or "").split()
    return [" ".join(w[:n]) for n in range(len(w) - 1, 1, -1)]


# -----------------------------------------------------------------------------------------
# corte en tramos
# -----------------------------------------------------------------------------------------
def _escenas(cfg):
    escenas = (cfg or {}).get("escenas") or []
    return [s for s in escenas if isinstance(s, dict)]


def _imagenes(cfg):
    imgs = (cfg or {}).get("imagenes") or []
    return [i for i in imgs if isinstance(i, dict)]


def _base_de(cfg, indice):
    imgs = _imagenes(cfg)
    if isinstance(indice, int) and 0 <= indice < len(imgs):
        return str(imgs[indice].get("buscar") or "")
    return ""


def _alternativas_de(cfg, indice):
    imgs = _imagenes(cfg)
    if isinstance(indice, int) and 0 <= indice < len(imgs):
        alt = imgs[indice].get("alternativas") or []
        if isinstance(alt, str):
            alt = [alt]
        return [str(a) for a in alt if str(a).strip()]
    return []


def _linea_tiempo(cfg, seg_times=None):
    """Devuelve (inicios, duraciones) por escena, en la línea de tiempo del vídeo.

    `duraciones[k]` es el intervalo VISIBLE de la escena k: su voz más la pausa que la
    separa de la siguiente (que es lo que se ve en pantalla), no sólo la voz.
    """
    escenas = _escenas(cfg)
    n = len(escenas)
    pausas = []
    for s in escenas:
        try:
            pausas.append(max(0.0, float(s.get("pausa") if s.get("pausa") is not None else 0.35)))
        except (TypeError, ValueError):
            pausas.append(0.35)

    # 1) con seg_times reales de make_short (lista de (t0, t1) por escena)
    if seg_times:
        try:
            pares = [(float(a), float(b)) for a, b in seg_times]
        except (TypeError, ValueError):
            pares = []
        if len(pares) == n and n:
            inicios = [p[0] for p in pares]
            durs = []
            for k in range(n):
                fin = inicios[k + 1] if k + 1 < n else pares[k][1] + pausas[k]
                durs.append(max(0.1, fin - inicios[k]))
            return inicios, durs

    # 2) estimación propia (calibrada, ver docstring del módulo)
    inicios, durs = [], []
    t = CABECERA_S
    for k, s in enumerate(escenas):
        voz = max(MIN_ESCENA_S, PALABRA_S * len(_palabras(_sin_asteriscos(s.get("texto")))))
        d = voz + pausas[k]
        inicios.append(t)
        durs.append(d)
        t += d
    return inicios, durs


def _grupos(cfg):
    """Grupos de escenas consecutivas que comparten la misma `imagen`.

    Devuelve [(indice_imagen, [idx_escenas]), ...]. Si una escena no trae `imagen`
    utilizable se le da grupo propio (clave negativa) para no fusionar escenas distintas.
    """
    escenas = _escenas(cfg)
    n_img = len(_imagenes(cfg))
    n_esc = max(len(escenas), 1)
    grupos = []
    for k, s in enumerate(escenas):
        crudo = s.get("imagen")
        if isinstance(crudo, bool) or not isinstance(crudo, (int, float)):
            # Sin `imagen`: se imita el reparto proporcional de make_short (~línea 960) sólo
            # si el guion trae imágenes; si no, cada escena va por su cuenta.
            imagen = int(k * n_img // n_esc) if n_img else None
        else:
            imagen = max(int(crudo), 0)
            if n_img:
                imagen = min(imagen, n_img - 1)
        clave = imagen if imagen is not None else -1 - k
        if grupos and grupos[-1][0] == clave and imagen is not None:
            grupos[-1][1].append(k)
        else:
            grupos.append((clave if imagen is None else imagen, [k]))
    return grupos


def _tramo_dict(i, imagen, idxs, t0, t1, cfg, escenas, parcial=False):
    # El texto visible va sin asteriscos, pero la consulta se calcula sobre el texto CRUDO:
    # las palabras enfatizadas con *asteriscos* son el ancla semántica de la escena.
    crudos = [str(escenas[k].get("texto") or "") for k in idxs]
    texto = " ".join(t for t in (_sin_asteriscos(c) for c in crudos) if t).strip()
    base = _base_de(cfg, imagen)
    consulta = _consulta(" ".join(crudos), base)
    alternativas = []
    for a in _alternativas_de(cfg, imagen) + _variantes(consulta):
        if a and a != consulta and a not in alternativas:
            alternativas.append(a)
    return {
        "i": i,
        "t0": round(max(0.0, t0), 3),
        "t1": round(max(t0, t1), 3),
        "texto": texto,
        "escenas": list(idxs),
        "consulta": consulta,
        "alternativas": alternativas,
        # campos extra (aditivos, no rompen el contrato)
        "imagen": None if imagen is None or imagen < 0 else imagen,
        "base": base,
        "duracion": round(max(0.0, t1 - t0), 3),
        "parcial": bool(parcial),
    }


def _partir_por_tiempo(tramo, max_s):
    """Último recurso: trocea por tiempo un tramo que ya no se puede partir por escenas."""
    dur = tramo["t1"] - tramo["t0"]
    if dur <= max_s + 1e-6:
        return [tramo]
    trozos = max(2, int(math.ceil(dur / max_s)))
    salida = []
    for j in range(trozos):
        a = tramo["t0"] + dur * j / trozos
        b = tramo["t0"] + dur * (j + 1) / trozos
        copia = dict(tramo)
        copia["t0"], copia["t1"] = round(a, 3), round(b, 3)
        copia["duracion"] = round(b - a, 3)
        copia["parcial"] = True
        salida.append(copia)
    return salida


def _cortar(cfg, seg_times, max_s):
    escenas = _escenas(cfg)
    if not escenas:
        return []
    max_s = float(max_s) if isinstance(max_s, (int, float)) and max_s > 0 else MAX_TRAMO_S
    inicios, durs = _linea_tiempo(cfg, seg_times)
    salida = []
    for imagen, idxs in _grupos(cfg):
        bloque, acumulado = [], 0.0
        for k in idxs:
            d = durs[k]
            if d > max_s + 1e-9:
                # Una sola escena ya pasa del tope: no se puede repartir por escenas.
                if bloque:
                    a = inicios[bloque[0]]
                    b = inicios[bloque[-1]] + durs[bloque[-1]]
                    salida.append(_tramo_dict(len(salida), imagen, bloque, a, b, cfg, escenas))
                    bloque, acumulado = [], 0.0
                bruto = _tramo_dict(len(salida), imagen, [k], inicios[k], inicios[k] + d, cfg, escenas,
                                    parcial=True)
                for trozo in _partir_por_tiempo(bruto, max_s):
                    trozo["i"] = len(salida)
                    salida.append(trozo)
                continue
            if bloque and acumulado + d > max_s + 1e-9:
                a = inicios[bloque[0]]
                b = inicios[bloque[-1]] + durs[bloque[-1]]
                salida.append(_tramo_dict(len(salida), imagen, bloque, a, b, cfg, escenas))
                bloque, acumulado = [], 0.0
            bloque.append(k)
            acumulado += d
        if bloque:
            a = inicios[bloque[0]]
            b = inicios[bloque[-1]] + durs[bloque[-1]]
            salida.append(_tramo_dict(len(salida), imagen, bloque, a, b, cfg, escenas))

    # red de seguridad: el tope es un requisito del proyecto, no una sugerencia
    finales = []
    for t in salida:
        for trozo in _partir_por_tiempo(t, max_s):
            trozo["i"] = len(finales)
            finales.append(trozo)
    return finales


def tramos(cfg, seg_times=None):
    """Parte el guion en tramos que comparten `imagen` y no pasan de `MAX_TRAMO_S` (7 s).

    `cfg` es el dict del guion (historias/*.json). `seg_times`, si se pasa, es la lista de
    (t0, t1) por escena que ya calculó make_short; si es None se estiman las duraciones con
    `PALABRA_S` (calibrado contra mp4 reales) sin fallar nunca.

    Devuelve una lista de dicts con las claves: i, t0, t1, texto, escenas, consulta,
    alternativas, reutiliza (siempre False aquí; el marcado vive en `plan`) y, como extra,
    imagen, base, duracion y parcial.
    """
    salida = _cortar(cfg, seg_times, MAX_TRAMO_S)
    for t in salida:
        t["reutiliza"] = False
    if salida:
        peor = max(t["duracion"] for t in salida)
        print(f"   broll: {len(salida)} tramos · máx {peor:.2f}s · {len(_imagenes(cfg))} imágenes · "
              f"{len(_escenas(cfg))} escenas")
    else:
        print("   broll: el guion no trae escenas; no hay tramos")
    return salida


def plan(cfg, seg_times=None, max_s=7.0):
    """Igual que `tramos`, garantizando el tope de `max_s` segundos por tramo.

    Marca `"reutiliza": True` cuando hay más tramos que imágenes disponibles: a partir de la
    imagen `len(imagenes)`, el plan ya no tiene una imagen nueva que asignar y ese tramo
    tendrá que reutilizar el clip de otro (es lo que aprovecha `buscar_clips`).
    """
    try:
        tope = float(max_s)
    except (TypeError, ValueError):
        tope = MAX_TRAMO_S
    if not (0 < tope <= 600):
        print(f"   broll: max_s={max_s!r} no es utilizable; uso {MAX_TRAMO_S}s")
        tope = MAX_TRAMO_S

    salida = _cortar(cfg, seg_times, tope)
    n_img = len(_imagenes(cfg))
    sobra = bool(n_img) and len(salida) > n_img
    for t in salida:
        t["reutiliza"] = bool(sobra and t["i"] >= n_img)

    if salida:
        peor = max(t["duracion"] for t in salida)
        marca = "SÍ" if peor <= tope + 1e-6 else "NO"
        print(f"   broll: plan de {len(salida)} tramos · tope {tope:.1f}s · máx {peor:.2f}s ({marca} cumple) · "
              f"{sum(1 for t in salida if t['reutiliza'])} marcan reutiliza ({n_img} imágenes)")
    else:
        print("   broll: el guion no trae escenas; el plan queda vacío")
    return salida


# -----------------------------------------------------------------------------------------
# claves, caché y descarga
# -----------------------------------------------------------------------------------------
def _claves():
    """Igual que make_short._claves(): config/claves.json + variables de entorno."""
    k = {}
    f = ROOT / "config" / "claves.json"
    if f.is_file():
        try:
            datos = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(datos, dict):
                k.update({str(a): str(b) for a, b in datos.items()})
        except (OSError, ValueError, TypeError):
            pass
    k.setdefault("pexels", os.getenv("PEXELS_API_KEY", ""))
    k.setdefault("pixabay", os.getenv("PIXABAY_API_KEY", ""))
    for nombre in list(k):
        valor = str(k.get(nombre) or "").strip()
        k[nombre] = "" if valor.upper().startswith("PEGA_AQUI") else valor
    return k


def _cache(cache_dir):
    destino = Path(cache_dir) if cache_dir else (ROOT / "cache" / "broll")
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"   broll: no pude crear la caché {destino}: {e}")
    return destino


def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "_", _norm(texto)).strip("_")[:60] or "vacio"


def _buscar(fuente, key, consulta, cache):
    """Consulta el banco SIN menores: limpia la consulta y filtra los hits. Devuelve (hits, error)."""
    try:
        import seguridad_menores as SM
        consulta = SM.sin_rostros(SM.limpiar_consulta(consulta))
        hits, err = _buscar_orig(fuente, key, consulta, cache)
        return SM.filtrar_hits_video(hits), err
    except ImportError:
        return _buscar_orig(fuente, key, consulta, cache)


def _buscar_orig(fuente, key, consulta, cache):
    """Consulta el endpoint REAL del banco. Devuelve (hits, error)."""
    if requests is None:
        return [], "requests no disponible en este intérprete"
    archivo = cache / f"busqueda_{fuente}_{_slug(consulta)}.json"
    try:
        if archivo.is_file() and time.time() - archivo.stat().st_mtime < TTL_CACHE_S:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            return (datos if isinstance(datos, list) else []), None
    except (OSError, ValueError, TypeError):
        pass
    try:
        if fuente == "coverr":
            # Coverr no necesita clave, pero NO respeta los parámetros de faceta: hay que
            # filtrar en cliente los clips de pago (coverr-premium-*), porque también sirven
            # su mp4 (verificado en vivo). Y su buscador hace AND estricto: "hospital corridor"
            # da 0, así que conviene una sola palabra.
            resp = requests.get(URL_COVERR, params={"query": consulta, "hitsPerPage": PER_PAGE},
                                timeout=TIMEOUT_BUSQ)
            resp.raise_for_status()
            hits = [h for h in resp.json().get("hits", [])
                    if isinstance(h, dict) and not h.get("is_premium")]
        elif fuente == "pexels":
            resp = requests.get(URL_PEXELS, headers={"Authorization": key}, params={
                "query": consulta, "per_page": PER_PAGE, "orientation": "portrait",
            }, timeout=TIMEOUT_BUSQ)
            resp.raise_for_status()
            hits = resp.json().get("videos", [])
        else:
            resp = requests.get(URL_PIXABAY, params={
                "key": key, "q": consulta, "per_page": PER_PAGE, "safesearch": "true", "order": "popular",
                "video_type": "film",          # sólo metraje real, no animaciones (parámetro verificado en vivo)
            }, timeout=TIMEOUT_BUSQ)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
    except Exception as e:                       # red, HTTP, JSON roto: todo se reporta, nada revienta
        return [], f"{fuente} no respondió ({type(e).__name__}: {e})"
    if not isinstance(hits, list):
        hits = []
    try:
        archivo.write_text(json.dumps(hits), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        pass
    return hits, None


def _texto_hit(hit):
    partes = [str(hit.get("tags") or ""), str(hit.get("description") or ""), str(hit.get("alt") or "")]
    url = str(hit.get("url") or "")
    if url:
        partes.append(url.rsplit("/", 1)[-1].replace("-", " ").replace("_", " "))
    return _norm(" ".join(partes))


def _puntuar(hit, terminos):
    texto = _texto_hit(hit)
    return sum(1 for t in terminos if t and t in texto)


def _clase(hit):
    """0 = metraje real; 1 = dudoso (animación, IA, baja calidad o tags no filmables).

    Motivo medido: la primera prueba en vivo eligió, para un tramo de hospital, un clip de
    `type: "animation"` con un hígado dibujado, porque sus tags casaban más términos que el
    metraje real. Con la clase por delante, ese clip queda descartado salvo que no haya nada
    mejor. En Pexels no existe `type`, así que se mira `isAiGenerated`/`isLowQuality` y los
    tags (que en Pexels suelen venir vacíos, de ahí que se puntúe también el slug de 'url').
    """
    if str(hit.get("type") or "").strip().lower() == "animation":
        return 1
    for campo in ("isAiGenerated", "isLowQuality"):
        if hit.get(campo) in (True, 1, "true", "True", "1"):
            return 1
    if NO_FILMABLE.search(_texto_hit(hit)):
        return 1
    return 0


def _duracion_hit(hit):
    try:
        return float(hit.get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def _elegir(hits, terminos, usados):
    """Mejor hit no usado, sin azar.

    Orden de preferencia: metraje real antes que animación/IA/baja calidad (campos `type`,
    `isAiGenerated`, `isLowQuality` de Pixabay, verificados en las respuestas), después más
    términos de la consulta presentes en los tags, después el orden de relevancia que ya
    devolvió el banco, y sólo al final la duración más larga.
    """
    candidatos = []
    for indice, h in enumerate(hits):
        if not isinstance(h, dict):
            continue
        ident = str(h.get("id") or "")
        if not ident or ident in usados:
            continue
        clase = _clase(h)                                  # 0 metraje real, 1 dudoso
        puntos = _puntuar(h, terminos) - 2 * clase          # una animación necesita 3 términos de ventaja
        candidatos.append((-puntos, clase, indice, -_duracion_hit(h), ident, h))
    if not candidatos:
        return None
    candidatos.sort(key=lambda x: x[:5])
    validos = [c for c in candidatos if _duracion_hit(c[5]) >= CLIP_MIN_S]
    if validos:
        preferidos = [c for c in validos if _duracion_hit(c[5]) >= CLIP_PREF_S]
        return (preferidos or validos)[0][5]
    return candidatos[0][5]


def _url_de(fuente, hit):
    if fuente == "coverr":
        bf = hit.get("base_filename")
        return f"https://cdn.coverr.co/videos/{bf}/1080p.mp4" if bf else None
    if fuente == "pexels":
        archivos = [f for f in (hit.get("video_files") or [])
                    if isinstance(f, dict) and f.get("file_type") == "video/mp4" and f.get("link")]
        # OJO: en Pexels `video_files[].quality` llega NULL (verificado en vivo), así que el
        # criterio `quality == "hd"` es siempre False y no ordena nada: mandan la resolución
        # real y la verticalidad, que sí discriminan.
        archivos.sort(key=lambda f: (
            int(f.get("height") or 0) >= 720,
            int(f.get("height") or 0) / max(int(f.get("width") or 1), 1),
            int(f.get("height") or 0),
        ), reverse=True)
        return archivos[0]["link"] if archivos else None
    variantes = hit.get("videos") or {}
    for nombre in ("medium", "small", "large", "tiny"):
        info = variantes.get(nombre) if isinstance(variantes, dict) else None
        if isinstance(info, dict) and info.get("url"):
            return info["url"]
    return None


def _descargar(fuente, hit, cache):
    """Descarga el mp4 validando host y tamaño. Espejo de fondos_satisfactorios.py:60-188.

    Devuelve (ruta, error). Nunca lanza.
    """
    url = _url_de(fuente, hit)
    parsed = urlparse(url or "")
    hosts = HOSTS.get(fuente, HOSTS_PIXABAY)
    sufijo_ok = True if fuente == "pexels" else parsed.path[-4:].lower() == ".mp4"
    if not url or parsed.scheme != "https" or parsed.hostname not in hosts or not sufijo_ok:
        return None, "el hit no trae un mp4 válido del CDN esperado"
    try:
        ident = int(hit.get("id"))
    except (TypeError, ValueError):
        # Coverr (uuid) y Wikimedia (pageid) usan ids NO numéricos: se sanea antes de usarlo
        # como nombre de fichero.
        ident = _slug(str(hit.get("id") or hit.get("base_filename") or "clip")) or "clip"
    dest = cache / f"{fuente}_{ident}.mp4"
    if dest.is_file() and dest.stat().st_size > 100_000:
        return dest, None
    if requests is None:
        return None, "requests no disponible en este intérprete"
    tmp = dest.with_suffix(".download")
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT_DESC) as resp:
            resp.raise_for_status()
            tipo = resp.headers.get("content-type", "").lower()
            if tipo and "video" not in tipo and "octet-stream" not in tipo:
                return None, f"el CDN devolvió content-type {tipo}"
            total = 0
            with tmp.open("wb") as f:
                for chunk in resp.iter_content(1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_DESCARGA_B:
                        raise ValueError("clip demasiado grande")
                    f.write(chunk)
        if total > 100_000:
            tmp.replace(dest)
            return dest, None
        return None, f"descarga demasiado pequeña ({total} bytes)"
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None, f"fallo al descargar ({type(e).__name__}: {e})"


def _descargar_reutilizando_fs(fuente, hit, cache):
    """Reutiliza el descargador de fondos_satisfactorios si se puede importar."""
    try:
        import fondos_satisfactorios as FS
    except Exception:
        return None, None                      # sin FS: que decida _descargar()
    funcion = getattr(FS, "_descargar_pexels" if fuente == "pexels" else "_descargar_hit", None)
    if not callable(funcion):
        return None, None
    try:
        ruta = funcion(hit, cache)
    except Exception:
        return None, None
    if ruta:
        return Path(ruta), None
    return None, "el descargador de fondos_satisfactorios no pudo con el clip"


def _duracion(ruta):
    probe = shutil.which("ffprobe")
    if not probe:
        return 0.0
    try:
        info = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                               "-of", "default=nw=1:nk=1", str(ruta)],
                              check=True, capture_output=True, text=True, timeout=20)
        return float(info.stdout.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0.0


def _locales():
    carpeta = ROOT / "videos_fondo"
    if not carpeta.is_dir():
        return []
    try:
        return sorted(p for p in carpeta.iterdir()
                      if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"})
    except OSError:
        return []


def _local_para(terminos, usados):
    """Último recurso sin red: clip de videos_fondo cuyo nombre case con los términos."""
    mejor, puntos_mejor = None, 0
    for p in _locales():
        if str(p) in usados:
            continue
        tallo = _norm(p.stem)
        puntos = sum(1 for t in terminos if t and t in tallo)
        if puntos > puntos_mejor:
            mejor, puntos_mejor = p, puntos
    return mejor


def _escalera(tramo):
    """Consultas a probar, de la más específica a la más general (máx 8 intentos)."""
    fuentes = [tramo.get("consulta") or "", tramo.get("base") or ""] + list(tramo.get("alternativas") or [])
    salida = []
    for f in fuentes:
        palabras = str(f).split()
        for n in range(len(palabras), 1, -1):
            cand = " ".join(palabras[:n])
            if len(cand) >= 3 and cand not in salida:
                salida.append(cand)
        if len(salida) >= 8:
            break
    return salida[:8]


# -----------------------------------------------------------------------------------------
# búsqueda de clips por tramo
# -----------------------------------------------------------------------------------------
def buscar_clips(plan, fuente="pixabay", cache_dir=None, max_por_tramo=1):
    """Obtiene clips de vídeo coherentes con cada tramo de `plan`.

    - `fuente`: "pixabay" (por defecto) o "pexels"; cualquier otra cosa cae a pixabay.
    - `cache_dir`: por defecto `cache/broll`. Ahí se guardan los JSON de búsqueda (24 h) y
      los mp4 (`pixabay_<id>.mp4`, el mismo nombre que usa fondos_satisfactorios).
    - `max_por_tramo`: cuántos clips intenta reunir por tramo (1-5).

    Devuelve la lista de tramos con `"clip"` (ruta local o None), `"error"` (motivo o None) y,
    como extra, `clips`, `consulta_usada`, `dur`, `reutilizado` y `fuente_clip`. Nunca lanza:
    sin red, sin claves o sin resultados devuelve `"clip": None` con el motivo.
    """
    tramos_in = [t for t in (plan or []) if isinstance(t, dict)]
    try:
        cupo = int(max_por_tramo)
    except (TypeError, ValueError):
        cupo = 1
    cupo = max(1, min(cupo, 5))
    # Admite UNA fuente o VARIAS: "pexels", "pexels,coverr" o ["pexels", "coverr"]. Así se
    # AMPLÍA la base de consulta: si la primera no tiene nada para un tramo, se prueba la
    # siguiente. Pexels primero porque es la única con vertical real (medido: 30/30 clips
    # 1080x1920 frente a 0/30 de Pixabay en "hospital corridor").
    if isinstance(fuente, (list, tuple)):
        pedidas = [str(f).strip().lower() for f in fuente]
    else:
        pedidas = [f.strip().lower() for f in str(fuente or DEFAULT_VIDEO).split(",")]
    fuentes_ok = [f for f in pedidas if f in FUENTES_VALIDAS] or [DEFAULT_VIDEO]
    fuente = fuentes_ok[0]          # se conserva para los nombres de fichero y los avisos
    cache = _cache(cache_dir)

    claves = _claves()
    # Coverr funciona SIN clave (endpoint público del sitio, verificado en vivo).
    key = "" if fuente in SIN_CLAVE else str(claves.get(fuente) or "").strip()
    aviso_clave = "" if (key or fuente in SIN_CLAVE) else \
        f"{fuente}: sin clave de API (config/claves.json o {fuente.upper()}_API_KEY)"
    if aviso_clave:
        print(f"   broll: ⚠ {aviso_clave}; intentaré la biblioteca local videos_fondo")

    salida, usados, por_consulta, por_imagen, locales_usados = [], set(), {}, {}, set()
    nuevos = reutilizados = fallidos = locales = 0

    if tramos_in:
        print(f"   broll: buscando {len(tramos_in)} clips en {'+'.join(fuentes_ok)}…")

    for posicion, t in enumerate(tramos_in, start=1):
        item = dict(t)
        item.setdefault("i", len(salida))
        item["clips"] = []
        item["clip"] = None
        item["error"] = None
        item["consulta_usada"] = None
        item["dur"] = 0.0
        item["reutilizado"] = False
        item["fuente_clip"] = None
        item["tipo_clip"] = None
        errores = []
        try:
            consulta = str(item.get("consulta") or "").strip()
            base = str(item.get("base") or "").strip()
            if not consulta:
                consulta = _consulta(item.get("texto") or "", base)
                item["consulta"] = consulta
            imagen = item.get("imagen")

            # 1) misma consulta ya resuelta en esta corrida: cero red
            if consulta and consulta in por_consulta and por_consulta[consulta]:
                item["clip"] = por_consulta[consulta]
                item["clips"] = [por_consulta[consulta]]
                item["reutilizado"] = True
                item["consulta_usada"] = consulta
                item["tipo_clip"] = "reutilizado"
                item["dur"] = round(_duracion(item["clip"]), 3)
                reutilizados += 1
                salida.append(item)
                continue

            # 2) búsqueda real, con escalera de consultas. Con VARIAS fuentes activas se pasa a
            #    la siguiente cuando la anterior no tiene nada para esa consulta: la base de
            #    consulta efectiva es la SUMA de los catálogos (Pexels + Pixabay + Coverr).
            for cand in _escalera(item):
                if len(item["clips"]) >= cupo:
                    break
                terminos = [w for w in cand.split() if w not in STOP]
                for fte in fuentes_ok:
                    k2 = "" if fte in SIN_CLAVE else str(claves.get(fte) or "").strip()
                    if not k2 and fte not in SIN_CLAVE:
                        continue
                    hits, error = _buscar(fte, k2, cand, cache)
                    if error:
                        errores.append(error)
                        continue
                    if not hits:
                        errores.append(f"{fte}: sin resultados para '{cand}'")
                        continue
                    hit = _elegir(hits, terminos, usados)
                    if hit is None:
                        errores.append(f"{fte}: '{cand}' sólo devolvió clips ya usados")
                        continue
                    ruta, error = _descargar_reutilizando_fs(fte, hit, cache)
                    if ruta is None:
                        ruta, error = _descargar(fte, hit, cache)
                    if ruta is None:
                        usados.add(str(hit.get("id")))
                        errores.append(error or "no pude descargar el clip")
                        continue
                    usados.add(str(hit.get("id")))
                    item["clips"].append(str(ruta))
                    item["fuente_clip"] = f"{fte}:{hit.get('id')}"
                    item["tipo_clip"] = str(hit.get("type") or fte)
                    item["consulta_usada"] = cand
                    break            # ya hay clip para esta consulta: al siguiente tramo
            if not item["clips"] and not errores:
                errores.append("ninguna fuente de vídeo utilizable (¿faltan claves de API?)")

            # 3) el plan dice que este tramo reutiliza: comparte el clip de su imagen
            if not item["clips"] and item.get("reutiliza") and imagen in por_imagen:
                prestado = por_imagen[imagen]
                item["clips"] = [prestado]
                item["reutilizado"] = True
                item["fuente_clip"] = f"{fuente}:reutilizado"
                item["tipo_clip"] = "reutilizado"
                item["error"] = "reutilizo el clip del tramo de la misma imagen (" + ("; ".join(errores[-1:]) or "sin búsqueda propia") + ")"
                por_consulta[consulta] = prestado
                reutilizados += 1
                item["dur"] = round(_duracion(prestado), 3)
                salida.append(item)
                continue

            # 4) biblioteca local videos_fondo
            if not item["clips"]:
                terminos = [w for w in (_norm(item.get("consulta") or "").split()) if w not in STOP]
                local = _local_para(terminos, locales_usados)
                if local:
                    locales_usados.add(str(local))
                    item["clips"] = [str(local)]
                    item["fuente_clip"] = f"local:{local.name}"
                    locales += 1

            if item["clips"]:
                item["clip"] = item["clips"][0]
                item["dur"] = round(_duracion(item["clip"]), 3)
                if consulta and not item["reutilizado"]:
                    por_consulta.setdefault(consulta, item["clip"])
                if imagen is not None and not item["reutilizado"]:
                    por_imagen.setdefault(imagen, item["clip"])
                if item["fuente_clip"].startswith("local:"):
                    print(f"   broll: tramo {posicion}/{len(tramos_in)} · '{consulta}' → local {local.name}")
                else:
                    nuevos += 1
                    print(f"   broll: tramo {posicion}/{len(tramos_in)} · '{item['consulta_usada'] or consulta}' "
                          f"→ {Path(item['clip']).name} ({item['dur']:.1f}s, {item['tipo_clip']})")
            else:
                fallidos += 1
                item["error"] = "; ".join(errores[-2:]) or "sin clips disponibles"
                print(f"   broll: tramo {posicion}/{len(tramos_in)} · '{consulta}' → sin clip ({item['error']})")
        except Exception as e:                  # ninguna sorpresa debe tumbar la generación
            item["clip"] = None
            item["error"] = f"error inesperado en el tramo: {type(e).__name__}: {e}"
            fallidos += 1
            print(f"   broll: ⚠ {item['error']}")
        salida.append(item)

    if salida:
        print(f"   broll: {len(salida)} tramos · {nuevos} clips nuevos, {reutilizados} reutilizados, "
              f"{locales} locales, {fallidos} sin clip · fuente {fuente} · caché {cache}")
    return salida
