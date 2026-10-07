import urllib.request
from html.parser import HTMLParser

found = {}
class Links(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        link = attrs.get("href", "")
        if "arm64-v8a" in link and ".apk" in link:
            for voice in ("es_MX-claude-high", "es_AR-daniela-high", "es_ES-sharvard-medium"):
                if voice in link and voice not in found:
                    found[voice] = link

with urllib.request.urlopen("https://k2-fsa.github.io/sherpa/onnx/tts/apk-engine.html", timeout=30) as response:
    Links().feed(response.read().decode())
for voice, link in found.items():
    print(voice + "\n" + link)
    target = __import__("pathlib").Path(__file__).resolve().parents[1] / "build" / (voice + ".apk")
    if not target.exists():
        urllib.request.urlretrieve(link, target)
    print("Descargado: " + str(target))
