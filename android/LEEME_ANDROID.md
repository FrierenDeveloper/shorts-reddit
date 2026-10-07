# Shorts Reddit para Android

Aplicación nativa con narración, composición y exportación de video en el teléfono. No requiere un PC o un servidor para renderizar. Android 10 o posterior. Se entrega un APK firmado para instalación personal, junto con el código fuente y un instalador de voz local. La entrega final no incluye la biblioteca antigua.

## Instalación y transferencia

1. Instala `ShortsReddit-Android.apk`. Si Android pregunta, autoriza al gestor de archivos que usas para instalar aplicaciones.
2. Instala `Piper-Daniela-Argentina.apk` y `Piper-Claude-Mexico.apk`, incluidos en el paquete, para tener Daniela y Claude simultáneamente. Consulta `VOCES_ANDROID.md` para las alternativas.
3. Si quieres añadir recursos propios, usa **Guiones → Añadir archivos** o importa un ZIP con carpetas `historias`, `imagenes`, `videos_fondo`, `musica` y `voces`. No necesitas importar la biblioteca del PC.
4. En **Ajustes**, elige el motor y la voz para narrador y opinión, escucha las muestras y guarda. Daniela, Claude y Google pueden elegirse por separado para narrador y opinión.
5. Prueba **Crear → Renderizar ejemplo sin conexión**. El resultado aparece en **Videos** y en `Movies/ShortsReddit`.

El APK no contiene claves privadas, videos personales ni los modelos de escritorio. Las claves tampoco están en el ZIP de transferencia. Para usar IA, Pexels o Pixabay, introduce tus claves en Ajustes, o importa tus propios `config/llm.json` y `config/claves.json` con **Importar llm.json o claves.json**. Los ajustes quedan cifrados con Android Keystore. El ZIP exportado por la app tampoco contiene esos ajustes.

Si tu proveedor estaba en LM Studio u Ollama en el PC, cambia el endpoint a un proveedor HTTPS compatible con OpenAI. El guion puede generarse con esa API; la síntesis de voz y el render siguen siendo locales. Para trabajar sin internet, importa un guion JSON o usa **Convertir texto sin IA**, y añade recursos visuales locales.

## Uso

- **Crear:** las tres temáticas originales; enlaces de Reddit, texto pegado o temas; selección de plantilla, banco de clips, música y extras. Un enlace o un tema por línea genera un lote de hasta 20 videos. El texto sin IA conserva la narración original y divide las escenas; no inventa un guion educativo.
- **Guiones:** importar, revisar y editar JSON; re-renderizar con sus opciones; añadir fotos, videos, música y narraciones propias. El archivo que se importa se copia al proyecto privado de la app.
- **Videos:** reproducción con un reproductor instalado, compartir, exportar MP4, copiar descripciones y marcar como publicado o pendiente. La exportación del proyecto conserva estos estados.
- **Ajustes:** claves, voces y resolución. Por defecto exporta H.264 a 1080 × 1920, 30 fps, audio AAC mono a 24 kHz. La opción 720 × 1280 reduce el trabajo.
- **Trabajo actual:** registro de etapas y progreso. El render utiliza un servicio con notificación y bloqueo de suspensión de CPU. Puedes cancelarlo. Si Android finaliza el proceso, vuelve a renderizar el guion guardado; no hay reanudación a mitad de un fotograma.

La app procesa cada video por separado. Límite de 180 segundos de narración por video, hasta 100 escenas y 40 imágenes. Puede añadir tres segundos de encuesta final. Los guiones generados con IA intentan ajustar su duración real al rango de 60–70 segundos mediante hasta dos revisiones adicionales. Los guiones importados y el texto sin IA conservan su contenido y avisan si quedan fuera de ese rango.

## Compatibilidad y diferencias respecto al PC

| Función | Adaptación Android |
|---|---|
| Guiones JSON, prompts y categorías | Conservados; edición y re-render local |
| IA compatible con OpenAI | Solicitudes HTTPS desde el móvil; puede necesitar clave y acceso a internet |
| Reddit | Lectura de JSON público y RSS; pegar el texto cuando Reddit bloquea el acceso |
| Plantillas | Clásica, impacto, noche, diario, pop, tétrica y elección aleatoria; fuentes originales |
| Fotos | Archivos locales y búsquedas Pexels, Pixabay, Openverse y Wikimedia Commons |
| Clips | Fondos satisfactorios y clips temáticos de Pexels/Pixabay; biblioteca local |
| Subtítulos | Texto visible y hablado separados, resaltados y karaoke; marcas del motor de voz o tiempos estimados |
| Extras | Tarjeta, progreso, encuesta, zoom, sonidos, aviso, etiqueta de opinión y cierre |
| Música | Archivos locales o composición instrumental local, atenuación al hablar y fundidos |
| Biblioteca | Videos, descripciones, créditos, estados de publicación y exportación ZIP |
| GPU NVIDIA / NVENC | Sustituidos por EGL/OpenGL y MediaCodec del teléfono |
| Edge, Kokoro, XTTS y Chatterbox | Sustituidos por voces locales de Android o audio propio importado; no están portados los modelos originales ni la clonación de voces |
| Whisper / CLIP | No están integrados en esta edición. Los filtros de recursos usan texto y metadatos; no clasifican personas mediante un modelo visual |
| Portadas y doodles | Portada de título/pregunta y dibujo sencillo; no reproduce todos los dibujos semánticos del escritorio |

La composición móvil adapta el aspecto de las plantillas; no garantiza que cada fotograma sea idéntico al del render de Python. Los clips de fondo se muestrean a 15 imágenes por segundo, y el MP4 se exporta a 30 fps. No se anuncia una velocidad de render universal: depende del fondo, la duración y la temperatura del equipo.

## Archivos propios en un guion

Las rutas son relativas al proyecto importado, con `/`. Por ejemplo:

```json
{
  "titulo": "Mi historia",
  "categoria_video": "reddit",
  "plantilla": "clasica",
  "motor_voz": "android",
  "musica": "musica/pista.mp3",
  "imagenes": [{"archivo": "imagenes/foto.jpg"}],
  "escenas": [
    {
      "texto": "Una frase para mostrar en pantalla.",
      "audio": "voces/narracion.wav",
      "imagen": 0,
      "pausa": 0.25
    }
  ]
}
```

`audio` es la narración completa de esa escena, no un ejemplo para clonar una voz. El límite de audio importado es 180 segundos; se decodifica y mezcla localmente. Si faltan recursos referenciados, importa los archivos antes de renderizar. Las rutas absolutas de Windows necesitan convertirse en rutas del proyecto.

Para tiempos exactos en audio propio, cada escena admite:

```json
"palabras": [
  {"texto": "Una", "inicio": 0.0, "fin": 0.25, "resalte": false},
  {"texto": "frase", "inicio": 0.25, "fin": 0.70, "resalte": true}
]
```

Los tiempos son segundos desde el inicio del audio de esa escena. Sin marcas del motor o marcas importadas, la app estima la duración de cada palabra a partir de la duración real de la escena e indica que los tiempos son aproximados.

La importación ZIP conserva archivos existentes. Si hay un archivo diferente con el mismo nombre, guarda una copia con prefijo `importado_` y adapta las referencias de los guiones importados. Los archivos idénticos se reutilizan.

## Compilar y empaquetar

En Windows, con JDK 17, SDK de Android con plataforma 36 y Build Tools 35:

```powershell
powershell -ExecutionPolicy Bypass -File android/build.ps1
powershell -ExecutionPolicy Bypass -File android/EMPAQUETAR.ps1
```

También puedes indicar `-AndroidSdk` y `-JavaHome`. El script reconoce `ANDROID_HOME` y `JAVA_HOME`. La compilación usa directamente las herramientas oficiales del SDK y no depende de Gradle ni de descargas de librerías.

La clave privada de firma se conserva únicamente en `android/.signing/`. Respalda esa carpeta de forma privada: se necesita para que futuras versiones puedan actualizar la instalación existente. No está en los paquetes de entrega. Compilar el código fuente en otro PC genera otra firma si no se restaura esa clave.

`EMPAQUETAR.ps1` prepara el APK, el ZIP de código, la voz Daniela, las muestras verificadas y la documentación dentro de `entrega-android/ShortsReddit-Android-Completo.zip`. La biblioteca antigua queda fuera. Solo con `-IncluirTransferencia` se añade un `Proyecto-para-importar.zip` que exista en la carpeta de entrega. El código de las comprobaciones en un dispositivo está en `android/tools/device-test/`; su APK es independiente del APK principal.

La validación realizada se documenta en `VALIDACION_ANDROID.md`. Consulta el informe para conocer los proveedores comprobados y los casos todavía pendientes.

## Xiaomi 12 Pro / Snapdragon

El mismo APK usa APIs estándar de Android, EGL y el codificador H.264 disponible en el dispositivo. No depende de MediaTek ni de un NPU específico. El Xiaomi 12 Pro usa Snapdragon 8 Gen 1 ([ficha oficial](https://www.mi.com/global/product/xiaomi-12-pro/)); su arquitectura ARM64 admite el instalador de Piper incluido. La compatibilidad se espera por estas interfaces, pero ese teléfono todavía no se ha conectado ni probado. Empieza con 720p y aumenta a 1080p si el rendimiento sostenido es adecuado.

## Interpretación contextual

Al generar con IA, una evaluación adicional del relato guarda emoción, suspenso, énfasis y pausas por escena. Se aplican controles de velocidad, pausas y ganancia; el tono depende del motor. Revisa las órdenes en el JSON. Consulta `INTERPRETACION_VOZ.md` para sus límites y el formato editable.
