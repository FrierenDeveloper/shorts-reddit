"""Elige la foto más acorde a un texto usando CLIP (en la GPU si hay CUDA).
Si CLIP no está instalado o falla, devuelve None y el programa usa el orden normal."""
import os

MODEL_ID = "openai/clip-vit-base-patch32"   # ~600 MB, se descarga una sola vez
_M = {}
UMBRAL = 0.19        # similitud mínima para considerar que la foto "calza"


def _load():
    if "ok" in _M:
        return _M["ok"]
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        dt = torch.float16 if (dev == "cuda" and os.getenv("SHORTS_CLIP_FP32") != "1") else torch.float32
        print(f"    (cargando CLIP en {dev}{' fp16' if dt == torch.float16 else ''}… solo la primera vez tarda)")
        _M["model"] = CLIPModel.from_pretrained(MODEL_ID, torch_dtype=dt).to(dev).eval()
        _M["proc"] = CLIPProcessor.from_pretrained(MODEL_ID)
        _M["dev"], _M["torch"], _M["dt"] = dev, torch, dt
        _M["ok"] = True
    except Exception as e:
        print(f"    (CLIP no disponible: {e}. Se usa el orden normal de resultados)")
        _M["ok"] = False
    return _M["ok"]


def puntuar(imagenes, textos):
    """imagenes: lista de PIL.Image; textos: lista de descripciones en inglés.
    Devuelve lista de similitudes (máximo entre los textos) o None si CLIP no está disponible."""
    if os.getenv("SHORTS_SIN_CLIP") == "1" or not imagenes or not _load():
        return None
    torch, m, p, dt = _M["torch"], _M["model"], _M["proc"], _M["dt"]
    with torch.no_grad():
        inp = p(text=[f"a photo of {t}" for t in textos], images=[im.convert("RGB") for im in imagenes],
                return_tensors="pt", padding=True)
        inp = {k: (v.to(_M["dev"]).to(dt) if v.is_floating_point() else v.to(_M["dev"])) for k, v in inp.items()}
        out = m(**inp)
        img = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
        txt = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
        sim = (img @ txt.T).max(dim=1).values
    return [float(s) for s in sim.cpu().float()]


_PROMPTS_MENOR = ["a photo of a child", "a photo of a baby", "a photo of a teenager", "a photo of kids playing",
                  "a photo of a young boy or girl"]
_PROMPTS_OTRO = ["a photo of an adult man", "a photo of an adult woman", "a photo of an elderly person",
                 "a photo of an object", "a photo of a room or building", "a photo of a landscape",
                 "a photo of a city street", "a photo of a hand", "a photo of an animal"]
UMBRAL_MENOR = 0.35   # probabilidad (softmax) acumulada de "menor" a partir de la cual se descarta


def contiene_menor(imagenes):
    """Devuelve una lista de bool (True = parece mostrar un niño, bebé o adolescente) o None si
    CLIP no está disponible. Clasificación zero-shot: la probabilidad de las etiquetas de menor
    frente a las de adultos, objetos y lugares. Es deliberadamente estricta (umbral bajo)."""
    if os.getenv("SHORTS_SIN_CLIP") == "1" or not imagenes or not _load():
        return None
    torch, m, p, dt = _M["torch"], _M["model"], _M["proc"], _M["dt"]
    textos = _PROMPTS_MENOR + _PROMPTS_OTRO
    with torch.no_grad():
        inp = p(text=textos, images=[im.convert("RGB") for im in imagenes], return_tensors="pt", padding=True)
        inp = {k: (v.to(_M["dev"]).to(dt) if v.is_floating_point() else v.to(_M["dev"])) for k, v in inp.items()}
        out = m(**inp)
        img = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
        txt = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
        prob = (100.0 * img @ txt.T).float().softmax(dim=-1)
        pm = prob[:, :len(_PROMPTS_MENOR)].sum(dim=1)
    return [bool(float(v) >= UMBRAL_MENOR) for v in pm.cpu()]


_PROMPTS_ROSTRO = ["a close-up photo of a person's face", "a portrait of a person looking at the camera",
                   "a selfie", "a headshot of a smiling person", "a photo of a face"]
_PROMPTS_SIN_ROSTRO = ["a photo of hands", "a photo of a person seen from behind", "a silhouette of a person",
                       "a photo of an object on a table", "a photo of a room or building",
                       "a photo of a landscape", "a photo of a city street at night", "a photo of a phone screen",
                       "a photo of feet walking", "a photo of an animal", "a photo of a door or window"]
UMBRAL_ROSTRO = 0.45  # probabilidad (softmax) acumulada de "rostro" a partir de la cual se descarta


def prob_rostro(imagenes):
    """Lista de probabilidades (0-1) de que cada imagen muestre un rostro visible, o None si
    CLIP no está disponible. Zero-shot: etiquetas de rostro frente a manos, espaldas, siluetas,
    objetos y lugares."""
    if os.getenv("SHORTS_SIN_CLIP") == "1" or not imagenes or not _load():
        return None
    torch, m, p, dt = _M["torch"], _M["model"], _M["proc"], _M["dt"]
    textos = _PROMPTS_ROSTRO + _PROMPTS_SIN_ROSTRO
    with torch.no_grad():
        inp = p(text=textos, images=[im.convert("RGB") for im in imagenes], return_tensors="pt", padding=True)
        inp = {k: (v.to(_M["dev"]).to(dt) if v.is_floating_point() else v.to(_M["dev"])) for k, v in inp.items()}
        out = m(**inp)
        img = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
        txt = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
        prob = (100.0 * img @ txt.T).float().softmax(dim=-1)
        pr = prob[:, :len(_PROMPTS_ROSTRO)].sum(dim=1)
    return [float(v) for v in pr.cpu()]
