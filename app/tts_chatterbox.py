"""Ayudante de voz con Chatterbox Multilingual (Resemble AI, licencia MIT).
Se ejecuta en su propio entorno (.venv_cb, Python 3.11) para no mezclar dependencias.

Modos:
  --serve            proceso persistente: carga el modelo UNA vez, escribe "READY" y luego atiende
                     trabajos (un JSON por línea en stdin) respondiendo {"ok": true} por línea.
  trabajo.json       modo antiguo: un solo trabajo y termina.
Trabajo = {"lang": "es", "items": [{"text": "...", "out": "x.wav", "ref": "voces/narrador.wav" | null,
           "exaggeration": 0.5, "cfg_weight": 0.5}]}
"""
import json, os, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS


def cargar():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Chatterbox: cargando modelo en {dev}…", flush=True)
    try:   # si el modelo ya está descargado, no consultar internet (arranque más rápido y sin avisos)
        os.environ["HF_HUB_OFFLINE"] = "1"
        return ChatterboxMultilingualTTS.from_pretrained(device=dev, t3_model="v3")
    except Exception:
        os.environ["HF_HUB_OFFLINE"] = "0"
        return ChatterboxMultilingualTTS.from_pretrained(device=dev, t3_model="v3")


def procesar(model, job):
    with torch.inference_mode():
        for i, it in enumerate(job["items"], 1):
            kw = dict(language_id=job.get("lang", "es"),
                      exaggeration=it.get("exaggeration", 0.5), cfg_weight=it.get("cfg_weight", 0.5))
            if it.get("ref"):
                kw["audio_prompt_path"] = it["ref"]
            wav = model.generate(it["text"], **kw)
            ta.save(it["out"], wav.cpu(), model.sr)
            print(f"voz {i}/{len(job['items'])}", flush=True)


def servir():
    model = cargar()
    print("READY", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            procesar(model, json.loads(line))
            print(json.dumps({"ok": True}), flush=True)
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}), flush=True)


def main(trabajo):
    procesar(cargar(), json.loads(Path(trabajo).read_text(encoding="utf-8")))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        servir()
    else:
        main(sys.argv[1])
