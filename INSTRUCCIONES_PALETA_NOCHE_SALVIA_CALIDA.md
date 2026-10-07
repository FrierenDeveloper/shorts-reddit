# Instrucciones: modo noche «Salvia cálida» para PetSeñal

Implementa la paleta **Salvia cálida** en el modo noche de la interfaz de la app PetSeñal. Esta opción ya fue elegida por la persona usuaria como compañera del nuevo modo día.

Trabaja sobre el checkout actual conectado a GitHub. Antes de editar, lee `AGENTS.md` y revisa cómo se definen y aplican hoy los temas claro y oscuro. Limita el cambio al tema oscuro: conserva la paleta diurna elegida y no rediseñes la página pública «Conócenos».

## Dirección visual elegida

Usa estos valores como punto de partida para el tema oscuro:

| Uso | Color |
| --- | --- |
| Fondo principal | `#172C29` |
| Tarjetas | `#243B35` |
| Superficie del mapa y controles elevados | `#2E4942` |
| Acento salvia principal | `#A7C8B8` |
| Acento cálido secundario, uso moderado | `#D67963` |
| Texto principal | `#F4EFE3` |
| Texto secundario | `#A7C4BD` |

La sensación debe ser nocturna, cálida y serena: verde profundo, superficies diferenciadas, texto legible, salvia para acciones y estados activos, y coral suave para llamadas secundarias o estados que ya usan ese significado. Evita neones, negros puros y grandes áreas coral.

## Alcance

- Actualiza las variables o tokens existentes del tema oscuro; no dupliques reglas si ya hay una fuente central de colores.
- Aplica el sistema de forma consistente a la app: fondo, tarjetas, campos, botones, navegación inferior, drawer, modales, avisos y estados activos.
- Adapta el mapa al tema nocturno sin ocultar calles, etiquetas, ríos, marcadores de mascotas, controles ni atribución del proveedor de mapas.
- Mantén distinguibles los marcadores de mascotas perdidas y encontradas; conserva sus significados semánticos y comprueba que se lean sobre el nuevo mapa.
- Conserva iconos, espaciado, tipografía, textos y comportamiento actual. Esta tarea cambia la paleta y los ajustes visuales estrictamente necesarios para mantener legibilidad.
- No añadas dependencias ni cambies configuración, umbrales o reglas de lint.

## Revisión visual y accesibilidad

- Compara claro y oscuro en las pantallas principales: mapa, búsqueda/listado, ficha de aviso, formularios, chats, menú de opciones y modales.
- Comprueba que tarjetas y fondo se distingan, que el foco de teclado sea visible y que los estados hover, activo, deshabilitado y error sigan siendo claros.
- Revisa contraste de texto principal y secundario, botones, bordes, iconos y marcadores; ajusta tonos derivados si los valores iniciales no alcanzan legibilidad suficiente.
- Confirma que el mapa conserva contraste útil y que el tema no convierte superficies extensas en un bloque uniforme.
- Verifica la activación del modo noche, el cambio entre modos y la persistencia de la preferencia del usuario.
- Revisa escritorio y celular, incluyendo navegación inferior y áreas seguras del dispositivo.

## Validación del proyecto

Sigue primero los requisitos de `AGENTS.md`, incluidas las pruebas que correspondan. Desde `backend/`, ejecuta:

```bash
npm run verify
npm run test:mutation:changed
```

Corrige fallos atribuibles al cambio; no desactives reglas ni reduzcas cobertura. No publiques ni despliegues el cambio. En la respuesta final, enumera archivos modificados, validaciones ejecutadas y cualquier asunto pendiente.
