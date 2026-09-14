# TMVIEWER — Plan de integración (sin romper INPI)

**Fecha:** 2026-09-14
**Estado:** investigación hecha, sin código aún

## Opción A (recomendada Fase 1): TMview público `tmdn.org` — solo lectura
- Endpoint: `POST https://www.tmdn.org/tmview/api/search/results`
- Body: `{"page":"1","pageSize":"30","criteria":"C","basicSearch":"<marca>"}`
- Auth: ninguna. **Ojo:** tumba conexiones sin `User-Agent` de browser → mandar `Mozilla/5.0`.
- Paginado fijo 30 por página (`page` param).
- Devuelve: nombre marca, oficina, titular, clase Niza, estado, n° solicitud/registro, fechas.
- Uso propuesto: botón "Búsqueda internacional" en Búsqueda Previa, separado del INPI en vivo. Cache 30d en `detalle_actas_inpi` (columna `fuente='tmview'`).
- Riesgo: endpoint no oficial, puede cambiar sin aviso → envolver en try/catch + fallback a mensaje.

## Opción B (Fase 2): EUIPO eSearch Plus oficial
- Requiere: app en `dev.euipo.europa.eu` + docs de identidad para producción + `EUIPO_CLIENT_ID`/`EUIPO_CLIENT_SECRET` como secrets.
- OAuth2 `client_credentials`, token 7200s, 25k llamadas/día, RSQL (`wordMarkSpecification.verbalElement==*X* and status==REGISTERED`).
- Endpoints: `GET /trademarks`, `/trademarks/{nro}`, `/image`, `/thumbnail`.
- Uso propuesto: edge `tmview-consulta` con refresh automático de token, solo cuando el estudio lo pida (no para todos).

## Decisión
Fase 1 primero (sin credenciales, sin costo). Fase 2 solo si un estudio paga internacional.
