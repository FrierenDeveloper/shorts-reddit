# Validación Android — 7 de octubre de 2026

## Comprobado en Xiaomi 15T Pro conectado por USB

- Instalación del APK firmado y apertura de la interfaz nativa.
- Validación de guiones, rechazo de rutas fuera del proyecto y ajustes cifrados con Android Keystore.
- Importación/exportación ZIP antes de la transferencia de la biblioteca personal.
- Render real 1080 × 1920, 30 fps, H.264 con codificador hardware `c2.mtk.avc.encoder`, audio AAC y duración comprobada.
- Render 720p con fotografía y video locales y decodificación del audio importado.
- Servicio con notificación, finalización y copia del MP4 a Movies/ShortsReddit.
- Síntesis con Daniela y Google local: 10,55 segundos. Prueba final con Daniela y Claude simultáneamente instaladas: 15,46 segundos; muestra incluida.
- Las credenciales se transfirieron directamente por USB a los ajustes cifrados. No están en los APK, paquetes ni repositorio.

## Alcance y pendientes

La app usa voces Android/Piper y MediaCodec en lugar de los motores Python. No incluye clonación XTTS/Chatterbox, modelos Whisper/CLIP ni todos los dibujos del escritorio. Los tiempos por palabra se estiman cuando la voz no entrega marcas. La IA y la búsqueda remota de recursos siguen requiriendo internet; voz y render son locales.

El Xiaomi 12 Pro no se ha conectado para una prueba real. El mismo APK usa APIs estándar y los motores incluidos son ARM64, por lo que se espera compatibilidad con Snapdragon. La velocidad y temperatura sostenidas en ese equipo están pendientes de medir.

El paquete final excluye la biblioteca antigua. La copia personal ya transferida al 15T Pro se conserva.

## Repetir las comprobaciones

Compila `android/build.ps1` y `android/tools/build-device-checks.ps1`, instala ambos APK y ejecuta las instrumentaciones `DeviceChecks`, `VoiceChecks` o `NetworkChecks` de `com.shortsreddit.mobile.tests`. El APK auxiliar comparte la firma local; no está incluido en la entrega de usuario. `NetworkChecks` usa las claves configuradas y consume llamadas de IA; no registra credenciales.

## Proveedores configurados

Se comprobó la generación de un guion JSON de 17 escenas, la síntesis local y el ajuste a 62,56 segundos. También se descargó una fotografía de un banco configurado y se obtuvieron sus créditos. Estas comprobaciones usan la configuración del teléfono; no validan todas las combinaciones posibles de proveedores.

## Últimos cambios y comprobaciones pendientes

La versión final incorpora el análisis contextual de interpretación y aplica velocidad, pausas, ganancia y énfasis por palabra. El APK final compila y su firma se verifica. La comprobación completa de ese nuevo flujo se interrumpió al desconectarse el USB; el usuario pidió terminar sin más pruebas en el teléfono. No se registra esa comprobación como aprobada. Las pruebas de voces Daniela/Claude y el render nativo anteriores sí finalizaron correctamente.

La conexión por Wi-Fi no quedó configurada: al intentar conectar a la dirección del teléfono, no había un servicio ADB de red disponible. Requiere activar Depuración inalámbrica y emparejar, o habilitar el transporte TCP mientras el USB esté conectado. La app no depende de ADB ni del PC para trabajar.

## Motor Kokoro opcional

El APK del motor Sherpa ONNX se recompila con paquete independiente `com.shortsreddit.voice.kokoro`. La inspección del artefacto confirma el servicio TTS declarado por Sherpa, sus clases originales, bibliotecas ARM64, modelo `kokoro-multi-lang-v1_0`, datos eSpeak españoles, idioma de servicio `spa`, idioma del modelo `es` y SID predeterminado 28 (`ef_dora`). La biblioteca Sherpa ONNX 1.13.8 también cargó esos mismos pesos y opciones en CPU y produjo 80.002 muestras (3,33 s a 24 kHz). El APK queda firmado y verificable. ADB no detectó el teléfono en esta sesión, así que la integración del servicio Android y la reproducción desde la app siguen pendientes de prueba en un dispositivo.
