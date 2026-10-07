# Instrucciones para crear la página «Conócenos» de PetSeñal

## Objetivo

Crear una página pública y adaptable para presentar PetSeñal a personas que aún no conocen la app. La página debe explicar su misión, la idea detrás del proyecto y cómo la comunidad puede ayudar a difundir avisos.

Implementa los cambios en el checkout real del repositorio conectado a GitHub. No asumas que una copia extraída de un ZIP está conectada a Git o a Render.

## Diseño y contenido

- Mantén una estética limpia, actual y cálida, coherente con la PWA existente.
- Reutiliza las variables de color, tipografías y estilos compartidos que ya existen; no inventes una identidad visual nueva.
- Usa el logo real de PetSeñal desde el recurso existente del proyecto. No lo redibujes ni lo sustituyas por otra marca.
- Por ahora no agregues imágenes, ilustraciones, videos, reproductores ni espacios vacíos reservados para ellos.
- Prioriza la lectura y la jerarquía del contenido. Deja suficiente espacio en blanco y evita llenar la página de tarjetas o adornos.
- Asegura que la página se vea bien en escritorio y celular.

La página debe incluir, al menos, estas secciones:

1. **Portada:** título breve y humano, una frase que explique que PetSeñal conecta a familias y comunidades para ayudar a reunir mascotas perdidas con sus familias, y un botón para abrir la app.
2. **Principios:** explicar de forma concisa que el servicio es gratuito para la comunidad, que se cuida la privacidad y que el proyecto se creó en Chile. Antes de publicar esas afirmaciones, confirma que siguen siendo exactas.
3. **Misión e idea:** explicar por qué existe el proyecto y cómo ayuda a coordinar avisos y compartir información local.
4. **Cómo funciona:** describir los pasos para publicar un aviso, difundirlo y coordinar con la familia de la mascota.
5. **Cómo ayudar:** invitar a compartir avisos y explicar brevemente qué hacer si alguien encuentra una mascota, sin sugerir acciones inseguras.
6. **Pie de página:** enlaces a la app, privacidad, términos y al contacto oficial vigente.

## Integración

- Sigue la estructura que utiliza el proyecto para páginas públicas estáticas. Comprueba cómo se sirven actualmente las páginas de privacidad y términos antes de elegir la ubicación.
- Publica la página en la ruta `/conocenos/`.
- Añade un enlace visible «Conócenos» al menú de opciones de la app, apuntando a `/conocenos/`. Mantén la navegación actual intacta.
- Revisa que la ruta estática se resuelve antes de cualquier ruta comodín que entregue la página principal de la app.
- Limita los cambios a los archivos necesarios. No cambies configuración, reglas de lint, umbrales ni el arnés de pruebas.

## Revisión de contenido y seguridad

- Comprueba la exactitud de afirmaciones sobre gratuidad, privacidad y origen del proyecto.
- Usa el correo de contacto que esté vigente en el repositorio; no copies una dirección de borradores antiguos sin confirmarla.
- No afirmes que PetSeñal garantiza reencuentros ni que sustituye a refugios, clínicas veterinarias, servicios de emergencia o autoridades.
- No prometas confidencialidad absoluta. Describe la privacidad en los mismos términos que la política vigente.
- Evita recolectar datos, añadir formularios, trackers o dependencias nuevas para esta página.

## Accesibilidad y presentación

- Usa HTML semántico, un solo encabezado principal, encabezados en orden, textos alternativos si aparecen imágenes en el futuro y etiquetas accesibles para la navegación.
- Conserva un indicador de foco visible y contraste suficiente.
- Verifica con teclado que los enlaces se pueden alcanzar y usar.
- Revisa en móvil que no haya desbordamiento horizontal y que botones y enlaces sean cómodos de pulsar.
- Confirma que los estilos globales de la app no rompen el scroll o el espaciado de la página independiente.

## Validación requerida por el proyecto

Lee y sigue `AGENTS.md` y las convenciones existentes antes de editar. Escribe primero las pruebas que correspondan según esas instrucciones y, desde `backend/`, ejecuta:

```bash
npm run verify
npm run test:mutation:changed
```

Corrige los problemas atribuibles al cambio; no reduzcas cobertura ni desactives reglas. En el resumen final, indica los archivos modificados, las comprobaciones ejecutadas y cualquier validación pendiente. No publiques ni despliegues el cambio.
