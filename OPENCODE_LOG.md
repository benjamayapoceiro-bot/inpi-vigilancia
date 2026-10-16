# OPENCODE_LOG.md

Registro centralizado de auditorías y cambios.

---

## 📋 Auditoría Inicial — 2026-09-13

**Ejecutada por:** OpenCode
**Duración:** ~15 minutos
**Resultado:** Backend corre con gaps, frontend único modular ok, 1 crítico real (logos), 2 mitigados, 1 falso positivo

### Checklist completado

- [x] Archivos críticos verificados (backend 7/7, frontend 15/15)
- [x] Cron status confirmado (`last_run.txt`: warnings + skip oposiciones + 201)
- [x] Bugs identificados (4 del prompt, reverificados contra código vivo)
- [ ] Queries Supabase ejecutadas (pendiente: pegar Q1-Q5 en SQL Editor, sin claves acá)
- [x] Frontend testeado (estructura + filtro estudio + edge presentar existe)
- [x] Storage verificado (sin llamadas a Storage en `*.py` → gap confirmado)
- [x] Edge functions listadas (5 activas)

### Hallazgos principales

| Funcionalidad | Estado | Último Check | Notas |
|---|---|---|---|
| Cron activo | 🟡 | `last_run.txt` + HTTP 201 | corre, oposiciones skipeadas |
| Parser boletines | 🟡 | regex frágil `(21)/(51)` | riesgo 0-actas silencioso |
| Matching texto | 🟢 | `matcher.py` + benchmark | fonética recall alto ok |
| Logo hashing | 🟢 | phash+dhash se computan | — |
| Logo storage | 🔴 | 0 llamadas Storage | GAP CONOCIDO |
| INPI SOAP proxy | 🟢 | `inpi-detalle` + NIZA | `inpi-presentar` mock a propósito |
| Auth & RLS | 🟢 | login + `getMarcasPorEstudio` | queda fallback hardcodeado |
| Admin "Mi Cartera" | 🟡 | filtra por estudio | CONTAMINACIÓN MITIGADA |
| Edge Functions | 🟢 | 5 up | `inpi-presentar` mock, no rota perdida |
| TMVIEWER | 🔴 | no | NO EXISTE |
| Planes pricing | ⚫ | flags sí, UI no | NO IMPLEMENTADO |

### Bugs

1. URL-encoding: ⚪ falso positivo (comas correctas, no codificar)
2. Logo storage: 🔴 confirmado
3. Admin contaminación: 🟡 mitigado, falta quitar fallback
4. Botón INPI: 🟡 mock intencional, no perdido

### Siguiente

Esperando instrucciones de Timmy para:
1. Implementar logo storage
2. Quitar fallback admin
3. Pasar `INPI_CUIT`/`CLAVE` o documentar skip
4. Investigar TMVIEWER (requiere cuenta EUIPO)
5. Armar planes de pricing

---

### 2026-09-13 — Auditoría Inicial

**Estado:** Completado

**Qué se hizo:**
- Audit cron status (`last_run.txt`, workflow, secrets)
- Verificación de archivos críticos (backend + frontend)
- Identificación de bugs (4 del prompt, reverificados)
- Creación de OPENCODE_AUDIT.md + OPENCODE_LOG.md

**Hallazgos:**
- 1 crítico real (logos), 1 mitigado (admin), 1 mock intencional (presentar), 1 falso positivo (URL-encoding)

**Archivos creados/modificados:**
- OPENCODE_AUDIT.md (nuevo)
- OPENCODE_LOG.md (nuevo)

**Resultado:** 🟢 Auditoría lista para fixes

**Próxima acción:** Esperando OK de Timmy para procedimiento de fixes

---

## 2026-09-17 — Fase 2: Presentaciones (6 trámites) + Auditoría

**Estado:** Backend completo y desplegado (mock); frontend reescrito; testes en vivo OK

**Qué se hizo:**
- Leídos los manuales INPI (HTML exportado) y extraído el SOAP exacto de los 6 trámites
- `inpi-presentar` generalizado: `tramite` + multi-titular via `titulares[]` (marca nueva, marca renovación, modelo nuevo, modelo renovación, patente invención, modelo de utilidad)
- Camino legacy (sin `titulares[]`) byte-idéntico para Marca Nueva
- Validaciones: suma porcentajes = 100, CUIT no repetidos, clase modelo 1–32, documentos obligatorios en modelos (idIndice 9/10 dibujos + 1037 figura uno)
- Auditoría en tabla nueva `presentaciones_inpi` (payload filtrado: sin `cuitInpi`/`claveInpi`)
- `demo-signup` usado para crear usuario de prueba y validar flujo completo (login JWT → 6 trámites → actas simuladas → filas de auditoría)
- Frontend `www/js/presentar.js` reescrito: selector de trámite, mini-componente multi-titular con suma 100%, checkbox legal + `UI.confirm()` en los 6 trámites

**Verificado:**
- XML de los 6 trámites contra el manual (SolicitudRelacionadas/Acta, `nro_renovacion`, Datos_Modelos, `<tem:Solicitantes/>` vacío, idIndice 9/1037/25, Tipo_antecedente 82)
- En vivo: 401 sin sesión, 6 trámites → `{ok, acta, preview}`, errores de validación (suma != 100, modelo sin docs), legacy sigue funcionando, filas de auditoría sin credenciales
- `presentar.js`: payloads por trámite verificados con harness Node (node --check OK)

**Archivos creados/modificados:**
- `supabase/functions/inpi-presentar/index.ts` (v4 desplegada, verify_jwt true)
- `supabase/migrations/20260917_presentaciones_inpi.sql` (tabla auditoría + RLS)
- `www/js/presentar.js` (reescrito) — en repo del dashboard
- `OPENCODE_LOG.md` (esta entrada)

**Pendientes (no Fase 2):**
- Calendario: ajuste visual modo oscuro/claro
- Decidir dominio (sub-dominio dashboard + landing Netlify)

**Próxima acción:** Revisión de Timmy; merge de Fase 2

---

## 2026-10-16 — Loop matching + mails + cron + frontend + agentes auditoría

**Estado:** Implementado y pusheado (ambos repos). Pendiente: GITHUB_PAT de Timmy, aprobación de hallazgos de auditoría.

**Qué se hizo:**
- `matcher.py`: M/F también corren texto (fix "casa cumbre"), normalización saneada (sin E→I/O→U/R→L, conserva dígitos, stopwords, singular), `token_set`, bonus prefijo, umbral siglas 0.90, contención atenuada en distinta, `requiere_oposicion` incluye afín, CLASES_AFINES simétrica + ampliada, `rapidfuzz` con fallback difflib.
- `extract_logos.py`: filtro por área (no ancho), tolerancia relativa, incluye F, `whash`; `distancia_logo_combinada` ensemble ph/dh/wh; `mantenimiento_cartera.py` + migración `20261016_logo_whash.sql` (aplicada); retry storage 3x; cron/rescan traen `logo_whash`; rescan unificado a 0.60/0.75.
- `notificar_email.py` + cron: resumen SIEMPRE (admin + estudios, con contexto de boletines); presupuesto 12→20 min.
- `admin-reenviar` (edge, verify_jwt, desplegada v1) + `reenviar.yml` + `reenviar_estudio.py` + botón ✉ por estudio en admin.js.
- Dashboard: heartbeat "Cotejo activo" en panel (debug_logs), filtro severidad + leyenda en alertas, tokens dark en detalle/app, resto de hardcodeados (logos en #fff se dejan a propósito).
- `.opencode/agent/`: 8 agentes (auditoria, dev, 5 auditores, juez) con modelos reales.
- `requirements.txt` + `cron.yml`/`rescan.yml`: agregado `rapidfuzz`.

**Verificado:**
- `tests/test_matcher_benchmark.py` verde + 2 tests nuevos (siglas no alertan, M matchea texto). Caso "casa cumbre" simulado: 2 alertas alto donde antes había 0, sin FPs en CASA ARISTEGUI/NEGRO/PROCASA.
- `py_compile` + `node --check` OK. Sin secretos en diffs (solo refs `${{ secrets.* }}`).

**Acción de Timmy fuera del repo:**
- Crear PAT fine-grained (Actions:write en inpi-vigilancia) y setearlo como secret `GITHUB_PAT` en Supabase (edge functions) para que funcione el botón reenviar.
- Dominio (mañana, como pediste).

**Próxima acción:** Auditoría Fase 1 con los 5 auditores → tabla de hallazgos para tu aprobación.

---

## 2026-10-16 (noche) — Auditoría loop + fixes código seguros

**Estado:** Auditado (5 auditores), juez consolidó. Aplicados solo fixes de código que no requieren confirmación (sin RLS/thresholds/legal). Resto en tabla para aprobación de Timmy.

**Aplicados y pusheados:**
- CRON-16: `reenviar_estudio.py` `avisado` → `notificado` (el reenvío estaba roto siempre).
- CRON-17: `estado` agregado al select de cartera (resoluciones fantasma).
- CRON-03/04: sentinel `boletines_procesados "0"` SISTEMA + `boletin_numero "0"` string; resoluciones/oposiciones entran al mail aunque falle el upsert.
- CRON-20: `supabase_upsert` loguea `r.text` en el error (adiós 400 ciego, caso boletín 11116).
- SEG-17/CRON-15: validación UUID de ESTUDIO_ID en `reenviar_estudio.py`.
- MAT-39/40/41: parse tolerante (guion/corte de línea, denominación multilínea, fallback titular crudo) + `parse_boletin.stats` reportado al cron.
- FRT-23: `escapeHtml` escapa comillas; `toast` escapa mensaje.
- FRT-26: botón reenviar explica `GITHUB_PAT` faltante y usa `Auth.getSession()`.

**Verificado:** `py_compile` + `node --check` OK; parse sintético (multilínea, titular sin `*`, corte de línea) OK; benchmark matcher verde.

**Tabla del juez (pendiente aprobación de Timmy):** ver reporte en chat 2026-10-16 noche.
