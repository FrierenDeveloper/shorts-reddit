# Componentes de terceros

Las fuentes Anton, Archivo Black, Bebas Neue, Lora, Montserrat y Poppins proceden del proyecto original. Sus licencias SIL Open Font License se incluyen en `android/assets/fonts/licenses` y dentro del APK.

Los motores de voz son distribuciones Sherpa ONNX 1.13.8 ARM64 con modelos Piper. Daniela conserva el APK oficial. Claude contiene los mismos DEX, bibliotecas y modelo del APK oficial, con identidad de instalación, autoridades de proveedores, permisos y etiqueta adaptados para coexistir. El procedimiento reproducible está en `android/tools/build-claude-coexist.ps1`.

Fuentes de los componentes y condiciones:

- Sherpa ONNX (Apache 2.0): https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8
- ONNX Runtime (MIT): https://github.com/microsoft/onnxruntime
- eSpeak NG (GPL 3.0): https://github.com/espeak-ng/espeak-ng
- Piper voices y fichas de modelos: https://huggingface.co/rhasspy/piper-voices
- Daniela, conjunto de datos CC BY-SA 4.0: https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_AR/daniela/high/MODEL_CARD
- Claude, conjunto de datos Apache 2.0: https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_MX/claude/high/MODEL_CARD
- Distribución original de APK: https://huggingface.co/csukuangfj2/sherpa-onnx-apk/tree/main/tts-engine-new/1.13.8

Las atribuciones de fotografías y videos descargados se guardan junto al MP4 generado.
