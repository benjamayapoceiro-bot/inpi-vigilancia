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
