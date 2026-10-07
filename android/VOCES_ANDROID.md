# Voces locales para Shorts Reddit

## Incluida e instalada: Piper Daniela

Voz femenina en español de Argentina, modelo high a 22.050 Hz. La síntesis se ejecuta en CPU ARM64 dentro del teléfono. El paquete completo incluye el instalador oficial `Piper-Daniela-Argentina.apk` (Sherpa ONNX 1.13.8). No necesita internet para narrar después de instalarlo.

1. Instala la app y el APK de Piper.
2. En Shorts Reddit → Ajustes selecciona **Piper · voz local instalada** como motor del narrador.
3. Selecciona voz automática en español y guarda.
4. Para opinión puedes elegir **Piper · Claude · México** (voz masculina incluida) o **Google · voces descargadas** y una voz española local diferente. Descarga español en los ajustes de síntesis de Android si no aparece ninguna voz.
5. Usa los botones Escuchar para comparar.

Se comprobó una narración con Daniela seguida de una opinión con Google; la versión final permite también elegir Claude, sin depender de un servidor de voz. Los subtítulos de Piper usan tiempos estimados por palabra; la duración de cada escena se obtiene del audio real.

## Alternativas

- **Piper Claude, México:** voz masculina, modelo high a 22.050 Hz. Instalador oficial ofrecido por separado en la release.
- **Piper Sharvard, España:** modelo medium, disponible en el catálogo oficial.
- **Google:** opciones españolas descargables, diferentes según el dispositivo y la versión del motor. La app solo muestra voces locales que no requieren conexión.

Los instaladores oficiales usan el mismo paquete. Para mantener las dos voces instaladas, el Claude incluido fue adaptado a `com.shortsreddit.voice.claude`: cambian la identidad de instalación, las autoridades de proveedores, los permisos propios y el nombre visible; el modelo, las bibliotecas y el DEX se conservan. Daniela conserva el APK oficial original. Puedes elegir Daniela y Claude de forma independiente, o combinarlos con Google. No se han integrado los modelos de clonación de voces del PC.

## Fuentes y licencias

- [Catálogo oficial Sherpa ONNX](https://k2-fsa.github.io/sherpa/onnx/tts/apk-engine.html)
- [Modelo Daniela](https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_AR/daniela/high/MODEL_CARD): ficha del conjunto de voz, CC BY-SA 4.0.
- [Modelo Claude](https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_MX/claude/high/MODEL_CARD): ficha del conjunto de voz, Apache 2.0.
- [Motor Sherpa ONNX](https://github.com/k2-fsa/sherpa-onnx): Apache 2.0; incluye dependencias con sus licencias propias.

Daniela es el APK original del catálogo. Claude es la adaptación para coexistir, firmada localmente; el procedimiento reproducible está en `android/tools/build-claude-coexist.ps1`. La procedencia y el SHA256 quedan documentados en la entrega.
