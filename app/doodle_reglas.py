"""Elige el DOODLE de portada según el relato del guion.

Por qué existe
--------------
La portada usaba siempre `app/assets/pensativo.jpg`: la misma cabeza pensativa con tres "?"
para una traición familiar, un duelo por cáncer o una explicación de sesgos cognitivos. Ahora
`app/doodles.py` dibuja 12 arquetipos y este módulo decide cuál toca.

Cómo funciona
-------------
Puntuación por PESO, nunca por orden de lista: se normaliza el texto (minúsculas y sin
acentos) y se cuenta cuántas raíces de cada arquetipo aparecen. `PRIORIDAD` sólo desempata.

Las palabras de `PALABRAS` están sacadas del vocabulario REAL de los guiones de
`historias/*.json` (frecuencias medidas sobre 44 guiones, agrupadas por `categoria_video`).
Entre paréntesis, el guion del que salió cada término más específico.

Sensibilidad (requisito duro)
-----------------------------
En `salud_mental` y `psicologia_diaria` el vídeo es EDUCATIVO: no se dramatiza ni se
estigmatiza. Ahí `elegir` nunca devuelve `dolido`, `indignado` ni `triste` como primera
opción, aunque el texto los puntúe alto; se pasa al siguiente arquetipo permitido.
"""
from __future__ import annotations

import re
import unicodedata

# ------------------------------------------------------------------ catálogo
ARQUETIPOS = {
    "pensativo":  "Dilema o duda: «¿me pasé?», hay que decidir algo y no está claro.",
    "dolido":     "Traición, engaño o desamor: alguien de confianza falló.",
    "indignado":  "Injusticia o falta de respeto: acusación, grosería, abuso.",
    "triste":     "Pérdida, enfermedad o duelo: algo grave y doloroso.",
    "aliviado":   "Resolución: remisión, disculpa aceptada, reconciliación.",
    "tenso":      "Confrontación o ultimátum: el conflicto está al límite.",
    "culpable":   "Remordimiento: quien narra reconoce su error o pide perdón.",
    "nostalgico": "Recuerdos y pasado: fotos, años atrás, tradiciones.",
    "ansioso":    "Ansiedad, miedo o angustia sostenida.",
    "confundido": "Contradicción o algo que no encaja ni se entiende.",
    "curioso":    "Descubrimiento o dato revelador: «resulta que...».",
    "analitico":  "Comparación, cifras, sesgos y toma de decisiones.",
}

# ------------------------------------------------------------------ vocabulario real
# Raíces SIN acentos (se comparan contra el texto normalizado). Extraídas de historias/*.json.
PALABRAS = {
    "dolido": [
        "traicion", "traiciono", "engan", "mentir", "mintio", "infiel", "desamor",
        "rompio", "corazon", "herida", "decepcion", "abandono", "fallo", "desprecio",
        "falsedad", "doble cara", "a espaldas", "desconfian", "usurp", "estafa",
        "no me lo esperaba", "me dolio", "me humillo", "macabro",   # 'traiciono' en 20260930_0047
    ],
    "indignado": [
        "injust", "grosero", "falta de respeto", "acuso", "insulto", "abuso",
        "aprovech", "ridicul", "humill", "rabia", "furia", "indign", "no es justo",
        "se paso", "atropell", "sin permiso", "se metio", "entromet", "exigio",
        "le grito", "descarad", "impresentable",                          # 'grosero' en cabana_ambiente
    ],
    "triste": [
        "cancer", "muri", "falleci", "muerte", "enferm", "hospital", "diagnostico",
        "perdida", "perdi", "llor", "triste", "duelo", "funeral", "grave", "sufri",
        "no pudo", "se apago", "ultimos dias", "tratamiento", "remision",
        "cuidados paliativos",                                            # 'cancer' en 20260930_0839
    ],
    "aliviado": [
        "remision", "mejoro", "se recupero", "sano", "reconcilia", "perdono",
        "acepto la disculpa", "se disculpo", "arregl", "solucion", "gracias a dios",
        "respiro", "alivio", "volvio", "paz", "saliendo adelante", "segunda oportunidad",
        "todo salio bien",                                                # 'remision' en 20260930_0839
    ],
    "tenso": [
        "ultimatum", "confront", "amenaz", "discusion", "pelea", "se enfrent",
        "tension", "le puse un limite", "exijo", "no pienso", "se acabo",
        "o ella o yo", "adverti", "estallo", "choque", "punto muerto",
        "se puso peor",                                                   # 'ultimatum' en 20260930_0839
    ],
    "culpable": [
        "disculp", "perdon", "arrepent", "culpa", "remordimiento", "fue mi error",
        "debi", "lamento", "siento mucho", "asumir mi", "me equivoque",
        "reconocio su error", "no volvera", "hice mal",                    # 'disculpa' en 20260930_0839
    ],
    "nostalgico": [
        "recuerdo", "memoria", "anos", "pasado", "antes", "foto", "album",
        "infancia", "cuando era", "antigu", "viejo", "tradicion", "costumbre",
        "thanksgiving", "navidad", "cena familiar", "mi pueblo", "la casa de",
        "anos y medio", "hace tiempo",                                     # 'anos' en todos los de reddit
    ],
    "ansioso": [
        "ansied", "miedo", "panico", "preocup", "nervios", "angustia", "terror",
        "no puedo dormir", "agobio", "estres", "inquiet", "temor", "taquicard",
        "crisis", "cada vez que", "me da miedo", "sufrir de",               # 'angustia' en 20260928_1931
    ],
    "confundido": [
        "confund", "no encaja", "contradict", "extrano", "raro", "no entiendo",
        "ilusion", "paradoja", "mezcla", "lio", "sorprend", "no me cuadra",
        "a la vez", "parece pero", "doble filo",                           # 'no encaja' en psicologia_diaria
    ],
    "curioso": [
        "descubr", "dato", "curios", "sabias que", "investiga", "experimento",
        "estudio", "revela", "secreto", "resulta que", "en realidad",
        "lo que nadie", "sorprendente", "por que", "la clave",              # 'resulta que' en varias de reddit
    ],
    "analitico": [
        "sesgo", "atencion", "tendencia", "comparar", "opciones", "decision",
        "analiz", "estadistic", "cifra", "porcentaje", "coste", "disponibilidad",
        "confirmacion", "informacion", "causa", "efecto", "probabilidad",
        "mecanismo", "hipotesis", "matiz",                                  # 'sesgo'(13), 'atencion'(12), 'confirmacion'(7) en psicologia_diaria
    ],
    "pensativo": [
        # OJO: aquí NO van "me pase", "tenia razon", "que haria", "me pregunto" ni "opinion".
        # Son la PLANTILLA del cierre de todos los guiones de Reddit ("¿Me pasé o tenía razón?")
        # y hacían que 29 de 44 guiones cayeran en `pensativo`: el doodle no se diferenciaba.
        # `pensativo` queda como duda GENUINA y, sobre todo, como arquetipo por DEFECTO.
        "duda", "dilema", "no se que hacer", "sopesar", "no estoy seguro",
        "indeciso", "dos opciones", "no me decido", "estoy entre", "no tengo claro",
        "me da vueltas", "no se si", "que hago",                       # 'no se si' en 20260928_0405
    ],
}

# Orden de desempate: primero lo emocional específico, al final lo genérico.
PRIORIDAD = [
    "dolido", "indignado", "triste", "tenso", "culpable", "ansioso",
    "aliviado", "nostalgico", "confundido", "analitico", "curioso", "pensativo",
]

# Empujón por categoría: no decide solo, pero inclina cuando hay empate.
CATEGORIA_PREFERIDA = {
    "reddit": ["pensativo", "dolido", "indignado", "tenso", "nostalgico", "triste"],
    "salud_mental": ["confundido", "ansioso", "curioso", "analitico", "pensativo"],
    "psicologia_diaria": ["analitico", "curioso", "confundido", "pensativo"],
}
BONUS_CATEGORIA = 2

# Requisito de sensibilidad: en contenido educativo no se dramatiza el doodle.
VETADOS_EDUCATIVO = ("dolido", "indignado", "triste")
CATEGORIAS_EDUCATIVAS = ("salud_mental", "psicologia_diaria")

DEFECTO = "pensativo"


def _norm(texto):
    """Minúsculas y sin acentos: 'CÁNCER' -> 'cancer'."""
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _puntos(texto, categoria=None):
    """Puntuación por arquetipo y lista de coincidencias, para poder explicarlo.

    El empujón de categoría NO se suma aquí: si se sumara, `pensativo` arrancaría con 2 puntos
    en todos los guiones de Reddit y ganaría casi siempre (medido: 29 de 44 guiones). La
    preferencia de categoría se usa sólo para DESEMPATAR, en `elegir`."""
    t = _norm(texto)
    puntos, coincidencias = {}, {}
    for nombre, raices in PALABRAS.items():
        halladas = [r for r in raices if r and r in t]
        puntos[nombre] = len(halladas)
        coincidencias[nombre] = halladas
    return puntos, coincidencias


def elegir(texto, categoria=None):
    """Devuelve el nombre del arquetipo de doodle que corresponde al relato.

    Orden: más coincidencias primero; a igualdad, los preferidos de la categoría; a igualdad,
    `PRIORIDAD`. Respeta el veto educativo: en salud mental y psicología nunca devuelve
    `dolido`, `indignado` ni `triste` como primera opción.
    """
    puntos, _ = _puntos(texto, categoria)
    educativa = categoria in CATEGORIAS_EDUCATIVAS
    pref = CATEGORIA_PREFERIDA.get(categoria, [])

    def clave(n):
        return (-puntos[n], 0 if n in pref else 1, PRIORIDAD.index(n) if n in PRIORIDAD else 99)

    for nombre in sorted(puntos, key=clave):
        if educativa and nombre in VETADOS_EDUCATIVO:
            continue                                  # vetado en contenido educativo
        if puntos[nombre] > 0:
            return nombre
    return DEFECTO


def explicar(texto, categoria=None):
    """Igual que `elegir`, pero devuelve el detalle para poder depurarlo."""
    puntos, coincidencias = _puntos(texto, categoria)
    elegido = elegir(texto, categoria)
    return {
        "elegido": elegido,
        "categoria": categoria,
        "puntos": dict(sorted(puntos.items(), key=lambda kv: -kv[1])),
        "coincidencias": {k: v for k, v in coincidencias.items() if v},
        "preferidos_categoria": CATEGORIA_PREFERIDA.get(categoria, []),
        "vetados_por_categoria": list(VETADOS_EDUCATIVO) if categoria in CATEGORIAS_EDUCATIVAS else [],
    }


if __name__ == "__main__":
    pruebas = [
        ("Mi mamá insinuó que mi esposa fingió el cáncer y nunca se disculpó. "
         "Incluso insinuó que la enfermedad no era real. Gracias a Dios entró en remisión. "
         "¿Me pasé o tenía razón?", "reddit"),
        ("Hoy en salud mental: erotomanía. La persona cree que alguien importante está "
         "enamorada de ella, aunque la realidad no lo confirme. ¿Qué tema te gustaría ver?", "salud_mental"),
        ("Hoy en psicología: el sesgo de confirmación. Tendemos a buscar información que "
         "confirma lo que ya creemos. ¿Qué tema quieres para el próximo episodio?", "psicologia_diaria"),
        ("Mi novio me fue infiel con mi hermana y encima me lo contó riéndose.", "reddit"),
        ("Mi hija murió en el hospital tras un diagnóstico tardío.", "reddit"),
        ("Le puse un ultimátum a mi hermano: o se disculpa o no habrá relación.", "reddit"),
        ("Fui grosero con el camarero y me avergüenzo. ¿Cómo arreglo esto?", "reddit"),
        ("Hace años mi abuela cocinaba en thanksgiving; ahora solo quedan las fotos.", "reddit"),
    ]
    for texto, cat in pruebas:
        e = explicar(texto, cat)
        top = list(e["puntos"].items())[:3]
        print(f"  [{cat or '-':17s}] -> {e['elegido']:11s} | top: " +
              ", ".join(f"{k}={v}" for k, v in top))
        print(f"        casa: {e['coincidencias'].get(e['elegido'], [])[:6]}")
