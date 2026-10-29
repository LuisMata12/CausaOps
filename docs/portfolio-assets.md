# Material para portafolio

Capturas tomadas del stack real corriendo en Docker, con un incidente generado por el
escenario controlado de la Fase 3 y un diagnóstico real de `openai/gpt-oss-120b`.
Ningún dato de estas imágenes es simulado o maquetado.

## Capturas — `docs/screenshots/`

| Archivo | Qué muestra | Pie sugerido |
|---|---|---|
| `01-overview.png` | Dashboard con estado del sistema e incidentes recientes | Estado en vivo de los tres servicios e incidentes abiertos, todo calculado en el backend. |
| `02-incidents-list.png` | Historial filtrable por estado, severidad y servicio | Los incidentes se agrupan por servicio: una degradación abierta por servicio, nunca alertas paralelas. |
| `03-incident-detail.png` | **La captura principal.** Hechos verificados, diagnóstico Groq, timeline de evidencia y correlación | Los hechos deterministas y la inferencia de IA se muestran por separado. El diagnóstico cita tres evidencias, todas verificadas contra la base de datos. |
| `04-api-docs.png` | OpenAPI 3.1 generado por FastAPI | Ingesta, detección y diagnóstico expuestos como una API versionada. |

Incidente capturado: 42.9 % de error rate, p95 de 2506 ms, severidad `high` por correlación
con el deploy `1.1.0-timeout`. Diagnóstico `completed` en 3890 ms, 2630 tokens de entrada,
confianza 0.9, tres evidencias citadas y validadas.

## Diagramas — `docs/architecture/diagrams/`

Cada uno en `.svg` (editable, nítido a cualquier tamaño) y `.png` (2x, para plataformas
que no aceptan SVG). Paleta tomada de `apps/web/app/globals.css`, así que combinan con
las capturas.

| Archivo | Explica |
|---|---|
| `01-arquitectura` | Los cinco servicios y quién habla con quién. La frontera de confianza deja claro que el navegador nunca toca PostgreSQL ni el LLM. |
| `02-ciclo-incidente` | Las ocho etapas del incidente, qué está implementado y qué espera a la Fase 5. El bucle se cierra: el detector reevalúa cada 30 s. |
| `03-evidencia` | El mecanismo que impide que el modelo invente: snapshot con IDs persistidos, respuesta en schema estricto, y tres comprobaciones del backend antes de aceptar. |

## Reproducir las capturas

```bash
docker compose up --build -d
curl -X POST http://localhost:8100/admin/mode -H 'content-type: application/json' -d '{"mode":"timeout"}'
for i in $(seq 1 6); do curl -s -o /dev/null -X POST http://localhost:8100/payments \
  -H 'content-type: application/json' -d '{"amount":25,"currency":"USD"}'; done
curl -X POST http://localhost:8000/api/v1/detection/run
```

Luego abrir <http://localhost:3000/incidents> y pedir un diagnóstico desde el detalle del
incidente. Requiere `GROQ_API_KEY` en `.env`.

## Qué contar en el portafolio

El ángulo diferencial no es "observabilidad con IA" — es **cómo se impide que la IA
invente**. Tres decisiones concretas que se pueden defender en una entrevista:

1. **Los hechos se persisten antes que cualquier inferencia.** Si Groq está caído, la
   detección sigue funcionando. La IA es una capa opcional sobre datos que ya existen.
2. **El backend verifica cada cita.** Un JSON perfectamente válido que referencia una
   evidencia que no se envió se rechaza y se guarda como intento auditable.
3. **El silencio no es recuperación.** Un incidente solo se cierra cuando llega telemetría
   nueva que demuestra salud, no cuando dejan de llegar errores.
