"""Seguridad: NUNCA usar fotos ni videos de niños, bebés o adolescentes, y evitar rostros.

Tres capas, todas best-effort y sin romper el render si algo falla:
  1) limpiar_consulta(): quita de la búsqueda las palabras de menores (child, kid, baby, boy, girl...).
  2) texto_con_menor(): descarta resultados cuyo título/tags/url mencionen menores.
  3) clip_con_menor(): con CLIP (si está instalado) mira la propia imagen y descarta las que
     parecen mostrar un menor, aunque el banco no lo diga en los metadatos.
Los videos se revisan con los mismos filtros (metadatos + miniatura)."""
import re
import json

_EN = (r"child|children|childs|kid|kids|baby|babies|toddler|toddlers|infant|infants|newborn|newborns|"
       r"boy|boys|girl|girls|teen|teens|teenager|teenagers|teenage|adolescent|adolescents|minor|minors|"
       r"preteen|tween|schoolboy|schoolgirl|schoolchildren|preschool|kindergarten|nursery|toddlers|"
       r"daughter|daughters|son|sons|nephew|niece|grandson|granddaughter|youngster|youth|juvenile|"
       r"little\s+(?:boy|girl|one|ones)|young\s+(?:boy|girl)|pupil|pupils|student\s+girl|playground")
_ES = (r"ni[nñ]o|ni[nñ]a|ni[nñ]os|ni[nñ]as|beb[eé]|beb[eé]s|infante|infantes|menor|menores|chico|chica|"
       r"chicos|chicas|adolescente|adolescentes|joven|j[oó]venes|hijo|hija|hijos|hijas|sobrino|sobrina|"
       r"nieto|nieta|escolar|escolares|colegial|colegiales|p[aá]rvulo|p[aá]rvulos|guardería|guarderia")
RX = re.compile(r"\b(?:%s|%s)\b" % (_EN, _ES), re.I)

SUSTITUTO = "empty room"      # si la consulta queda vacía tras limpiarla


def limpiar_consulta(q):
    """Quita las palabras de menores. 'sad child dinner table' -> 'sad dinner table'."""
    q = str(q or "")
    limpia = re.sub(r"\s+", " ", RX.sub(" ", q)).strip()
    if not limpia:
        return SUSTITUTO
    return limpia


def texto_con_menor(*partes):
    txt = " ".join(str(p or "") for p in partes)
    return bool(RX.search(txt.replace("-", " ").replace("_", " ")))


def resultado_con_menor(x):
    """x: dict de un resultado de imagen (title, tags, url...)."""
    return texto_con_menor(x.get("title"), x.get("tags"), x.get("alt"), x.get("description"),
                           str(x.get("page") or "").rsplit("/", 1)[-1])


def hit_video_con_menor(h):
    """h: dict de un hit de video de Pexels/Pixabay/Coverr."""
    if not isinstance(h, dict):
        return False
    slug = str(h.get("url") or h.get("pageURL") or "").rstrip("/").rsplit("/", 1)[-1]
    return texto_con_menor(h.get("tags"), h.get("alt"), h.get("description"), h.get("title"), slug)


def _thumb_video(h):
    for k in ("image", "picture"):
        if isinstance(h.get(k), str) and h[k].startswith("http"):
            return h[k]
    pid = h.get("picture_id")
    if pid:
        return f"https://i.vimeocdn.com/video/{pid}_640x360.jpg"
    vp = h.get("video_pictures")
    if isinstance(vp, list) and vp and isinstance(vp[0], dict):
        return vp[0].get("picture")
    return None


def filtrar_hits_video(hits, usar_clip=True):
    """Quita los hits de video con menores (metadatos y, si se puede, miniatura con CLIP)."""
    if not isinstance(hits, list):
        return hits
    ok = [h for h in hits if not hit_video_con_menor(h)
          and not texto_con_rostro(h.get("tags"), h.get("alt"), h.get("description"), h.get("title"),
                                   str(h.get("url") or h.get("pageURL") or "").rstrip("/").rsplit("/", 1)[-1])]
    quitados = len(hits) - len(ok)
    if usar_clip and ok:
        try:
            import requests
            from io import BytesIO
            from PIL import Image
            import clip_rank
            ims, idx = [], []
            for i, h in enumerate(ok):
                u = _thumb_video(h)
                if not u:
                    continue
                try:
                    r = requests.get(u, timeout=15)
                    ims.append(Image.open(BytesIO(r.content)).convert("RGB")); idx.append(i)
                except Exception:
                    pass
            flags = clip_rank.contiene_menor(ims) if ims else None
            pr = clip_rank.prob_rostro(ims) if ims else None
            if flags:
                malos = {idx[j] for j, f in enumerate(flags) if f}
                if pr:
                    malos |= {idx[j] for j, v in enumerate(pr) if v >= clip_rank.UMBRAL_ROSTRO}
                quitados += len(malos)
                ok = [h for i, h in enumerate(ok) if i not in malos]
            elif pr:
                malos = {idx[j] for j, v in enumerate(pr) if v >= clip_rank.UMBRAL_ROSTRO}
                quitados += len(malos)
                ok = [h for i, h in enumerate(ok) if i not in malos]
        except Exception:
            pass
    if quitados:
        print(f"   seguridad: {quitados} video(s) descartados por posibles menores o rostros")
    return ok


# ------------------------------------------------------------------ SIN ROSTROS
# El canal no muestra caras de personas: se prefieren manos, siluetas, espaldas, objetos y acciones.
_ROSTRO = re.compile(r"\b(?:face|faces|faced|portrait|portraits|selfie|selfies|headshot|headshots|smiling|smile|"
                     r"close[\s-]?up\s+face|facial|eyes|looking\s+at\s+camera|cara|caras|rostro|rostros|retrato|"
                     r"sonriendo|sonrisa)\b", re.I)
_PERSONA = re.compile(r"\b(?:man|men|woman|women|person|people|guy|girlfriend|boyfriend|couple|wife|husband|"
                      r"mother|father|mom|dad|friend|friends|sister|brother|doctor|nurse|worker|businessman|"
                      r"businesswoman|lady|gentleman)\b", re.I)
_YA_SIN_CARA = re.compile(r"\b(?:hand|hands|silhouette|silhouettes|back\s+view|from\s+behind|shadow|shadows|"
                          r"feet|legs|walking|fist|fingers)\b", re.I)


def sin_rostros(q):
    """Quita palabras que traen rostros (face, portrait, selfie...). Si la búsqueda habla de personas
    y no pide manos/siluetas/espaldas, añade 'hands' para que salgan planos de manos y acciones."""
    q = re.sub(r"\s+", " ", _ROSTRO.sub(" ", str(q or ""))).strip() or SUSTITUTO
    if _PERSONA.search(q) and not _YA_SIN_CARA.search(q):
        q += " hands"
    return q


def texto_con_rostro(*partes):
    txt = " ".join(str(p or "") for p in partes)
    return bool(_ROSTRO.search(txt.replace("-", " ").replace("_", " ")))


def resultado_con_rostro(x):
    return texto_con_rostro(x.get("title"), x.get("tags"), x.get("alt"), x.get("description"),
                            str(x.get("page") or "").rsplit("/", 1)[-1])
