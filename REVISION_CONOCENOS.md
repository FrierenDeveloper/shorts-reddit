# Revisión de la página «Conócenos» de PetSeñal

Este documento resume los cambios preparados en la copia del proyecto extraída del ZIP y señala qué debería comprobar otro agente antes de llevarlos al repositorio conectado a GitHub.

## Cambios realizados

### `frontend/conocenos/index.html`

- Añade una página estática en `/conocenos/`, coherente con la estructura de páginas legales existentes.
- Presenta el propósito de PetSeñal, una explicación breve de cómo funciona, sus principios y formas concretas de ayudar difundiendo avisos.
- No incluye ilustraciones ni video por ahora.
- Reutiliza el icono existente en `/icons/icon.svg` para el logo y enlaza a la app, privacidad, términos y contacto.
- Incluye metadatos básicos en español para viewport, tema y descripción.

### `frontend/conocenos/conocenos.css`

- Define una presentación adaptable para escritorio y celular con variables, tipografías y paleta de `frontend/styles.css`.
- Usa nombres de clase con prefijo `about-` para reducir interferencias con la interfaz de la aplicación.
- Restablece en `.about-main` el padding y el comportamiento de scroll heredados de la regla global `main`.
- Mantiene estados `hover` y foco visibles según los estilos globales.

### `frontend/index.html`

- Añade el enlace «Conócenos» al menú lateral de opciones, apuntando a `/conocenos/`.

## Lista de revisión para el agente

### Integración

- [ ] Aplicar estos cambios sobre el checkout actual del repositorio GitHub; esta copia ZIP no tiene metadatos `.git` ni despliega a Render.
- [ ] Confirmar que Render sirve `frontend/` como contenido estático y que `https://petsenal.com/conocenos/` abre `frontend/conocenos/index.html` en producción.
- [ ] Confirmar que `/conocenos/` no cae en la ruta comodín de `backend/server.js` que entrega `frontend/index.html`.
- [ ] Revisar que la página funciona desde una URL directa, al recargar y al volver a la app.

### Presentación y responsive

- [ ] Revisar en escritorio y celular que no aparecen imágenes o espacios vacíos reservados para imágenes.
- [ ] Revisar que el título, CTA, bloques de principios y pasos tienen jerarquía visual clara y no se desbordan en pantallas estrechas.
- [ ] Confirmar que el logo carga desde `/icons/icon.svg` y que sus proporciones se ven bien en cabecera y pie.
- [ ] Comprobar contraste, navegación por teclado, foco visible, enlaces descriptivos y estructura de encabezados.
- [ ] Comprobar que el `main` de esta página desplaza el documento completo y que los estilos globales de la app no limitan el scroll.

### Contenido y exactitud

- [ ] Verificar que «Gratis para la comunidad», «Privacidad cuidada» y «Hecha en Chile» describen correctamente el estado y compromiso real del proyecto.
- [ ] Revisar la recomendación de permanecer en un lugar seguro al encontrar una mascota para que no implique manipular o trasladar un animal sin necesidad.
- [ ] Confirmar que el correo `contacto@petsenal.com` es la dirección de contacto que se quiere publicar.
- [ ] Asegurar que no se presenta PetSeñal como refugio, servicio de emergencia, autoridad o garantía de reencuentro.
- [ ] Revisar que misión y descripciones coinciden con el funcionamiento actual de la app y su política de privacidad.

### Validación del proyecto

- [ ] Desde `backend/`, ejecutar `npm run verify` y resolver cualquier fallo atribuible a los cambios.
- [ ] Desde `backend/`, ejecutar `npm run test:mutation:changed` y revisar el resultado según las reglas del proyecto.
- [ ] No modificar reglas, umbrales o configuración del arnés para hacer pasar la validación.
- [ ] Confirmar que el cambio final contiene solamente los archivos necesarios para la página y su enlace.

## Alcance pendiente

La página está preparada sin imágenes. La ilustración del mapa comunitario generada durante la conversación no se añadió al proyecto. Tampoco se agregó una sección de video: se había pedido quitar las referencias a video del concepto.
