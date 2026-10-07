# Interpretación del relato

Al crear un guion con IA, la app realiza una segunda evaluación del relato completo. Considera el contexto y la categoría y añade órdenes de interpretación a cada escena, con una justificación breve. No modifica la narración ni añade hechos en esa evaluación. Los ajustes de duración repiten el análisis sobre el guion revisado.

El texto convertido **sin IA** recibe sugerencias locales por señales del texto; ese modo no ofrece el mismo análisis contextual. Los guiones importados pueden incluir las mismas órdenes y se pueden revisar en Guiones → Editar y revisar JSON.

```json
"interpretacion": {
  "emocion": "suspenso",
  "motivo": "Pausa antes de revelar la decisión del narrador.",
  "velocidad": 0.91,
  "tono": 0.95,
  "intensidad": 1.0,
  "pausa_antes": 0.25,
  "pausa_despues": 0.6,
  "recalcar": ["nunca", "esa noche"]
}
```

Emociones admitidas: neutral, suspenso, tristeza, alegria, sorpresa, enfasis y calma. Las indicaciones no se pronuncian. El guion conserva `analisis_voz: ia_contextual` o `local` para identificar cómo se generaron.

## Aplicación real

- **Velocidad:** multiplicador de la velocidad global, limitado a 0,85–1,15 por escena.
- **Tono:** se solicita al motor Android dentro de 0,9–1,1. Algunos motores, incluido Piper, pueden ignorarlo.
- **Intensidad:** ganancia de la narración, limitada a 0,9–1,15, con protección de picos.
- **Pausas:** silencio antes y después de la escena, hasta 1,2 segundos por indicación. La pausa final nunca reduce una pausa explícita más larga del guion.
- **Recalcar:** palabras o frases literales del relato; se resaltan en subtítulos y reciben un refuerzo de volumen del 8 % en los intervalos calculados. Si no hay marcas de palabra del motor, esos intervalos son aproximados.

Son controles de prosodia y mezcla sobre voces locales. La etiqueta de emoción organiza las órdenes; estos motores no producen actuación emocional neuronal completa, susurros o llanto por recibir una etiqueta. Las órdenes están visibles y son editables para ajustar el resultado.

La evaluación contextual añade una llamada al proveedor de IA por generación o revisión. Si la respuesta no cubre todas las escenas o contiene índices inválidos, se informa del error en el registro y no se anuncia un análisis completado.
