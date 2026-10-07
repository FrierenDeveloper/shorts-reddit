"""Transfers the project and existing API settings through a temporary ADB tunnel.

Run the ProjectTransfer instrumentation first. Credentials are never written to
the ZIP or printed. The helper APK is removed after migration.
"""
import json
import socket
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
archive = root / "entrega-android" / "Proyecto-para-importar.zip"
settings = {}
for filename in ("llm.json", "claves.json"):
    path = root / "config" / filename
    if path.exists():
        content = json.loads(path.read_text(encoding="utf-8-sig"))
        settings.update({k: content[k] for k in ("base_url", "api_key", "modelo", "pexels", "pixabay") if k in content})
payload = json.dumps(settings, ensure_ascii=False).encode("utf-8")
with socket.create_connection(("127.0.0.1", 8877), timeout=120) as stream:
    stream.sendall(struct.pack(">Q", archive.stat().st_size))
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            stream.sendall(chunk)
    stream.sendall(struct.pack(">I", len(payload)))
    stream.sendall(payload)
print("Archivos enviados por USB; Android está importando el proyecto.")
