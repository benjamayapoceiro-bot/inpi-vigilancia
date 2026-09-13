# INPI Vigilancia — Auditoría & Hoja de Ruta para OpenCode

**Generado:** 2026-09-13 (UTC)
**Por:** OpenCode (auditoría automatizada, verificada contra repo en vivo)
**Próxima acción:** Revisar bugs confirmados y realizar fixes según prioridad

---

## 📊 ESTADO ACTUAL

### Backend
- **Cron status:** 🟡 corre pero con gaps (último `debug/last_run.txt`: warnings + `Faltan INPI_CUIT o INPI_CLAVE` + `HTTP_STATUS:201`)
- **Último run:** ver `debug/last_run.txt` (warnings `fitz` deprecated + `datetime.utcnow()` deprecated x6)
- **Archivos críticos:** ✓ todos presentes (`cron_check_boletines.py`, `matcher.py`, `parse_boletin.py`, `extract_logos.py`, `.github/workflows/cron.yml`, `requirements.txt`, `schema.sql`)
- **Alertas esta semana:** pendiente query Supabase (ver Queries abajo)
- **Errores reportados:** oposición skipeada por falta de secrets; posible 0-actas silencioso

### Frontend (`inpi-vigilancia-dashboard/`, modular, único — no hay `dashboard/` huérfano)
- **Archivos:** ✓ todos (`index.html`, `js/app.js`, `api.js`, `alertas.js`, `busqueda.js`, `cartera.js`, `crm.js`, `detalle.js`, `admin.js`, `auth.js`, `tour.js`, `calendario.js`, `inpi.js`, `inpi-grilla.html`, `config.js`)
- **Login funciona:** 🟢 Supabase Auth + RLS por `estudio_id`
- **Búsqueda NIZA:** 🟢 FTS con weights (panes → Clase 30 verificado antes)
- **Admin contaminación:** 🟡 mitigado — `cartera.js:44` usa `API.getMarcasPorEstudio(estudioId)`; queda fallback hardcodeado `a3245063-...` (deuda) + vista `Todas las carteras` solo-lectura ok
- **Botón INPI-presentar:** 🟡 existe pero es MOCK — `supabase/functions/inpi-presentar/index.ts` existe, llama comentada, devuelve acta simulada. No romper hasta auth + XML escapado + credenciales por estudio

### Infraestructura
- **Supabase:** Online (writes 201 en last_run)
- **Logos en Storage:** 🔴 gap conocido — hashes se computan, `logo_url` nunca se guarda (ver Bug 2)
- **Edge Functions activas (5):** `admin-create-estudio`, `admin-create-user`, `demo-signup`, `inpi-detalle`, `inpi-presentar` (mock)

---

## 🐛 BUGS

### 1. URL-encoding `supabase_upsert` — ⚪ FALSO POSITIVO
- **Dónde:** `cron_check_boletines.py:74-79` (`?on_conflict={on_conflict}` con `marca_vigilada_id,acta_nueva,boletin_numero`)
- **Veredicto:** Las comas **NO** deben ir como `%2C` — PostgREST espera lista separada por comas. Codificarlas rompería el upsert. No tocar.
- **Riesgo real distinto:** falta unique constraint en DB para ese trío → verificar en Supabase, si no existe el upsert da 400.

### 2. Logos NO se guardan en Storage — 🔴 CRÍTICO (confirmado)
- `mantenimiento_cartera.py:17` acepta `supabase_storage_upload` pero `cron_check_boletines.py:106` lo llama **sin ese parámetro** → `logo_url` siempre `None`.
- `extract_logos.py` solo devuelve `{phash, dhash}`, descarta bytes.
- No hay evidencia de bucket `logos` ni llamadas `storage.from()` en `*.py`.
- **Fix:** crear bucket `logos-marcas` (privado, por `estudio_id`), implementar `supabase_storage_upload` real vía Storage REST con service_role, pasarla en el cron, y que `extract_logos` también suba + guarde `logo_url_acta`.

### 3. Admin "Mi Cartera" — 🟡 MITIGADO (no 🔴)
- Ya filtra por `estudio_id` (`getMarcasPorEstudio`). Queda deuda: fallback hardcodeado a `FONS LEGAL - ADMIN` en `cartera.js:336` y query de conteo de límite sin filtro por estudio en `:357`.
- **Fix:** sacar fallback, forzar `estudioId` de `Auth.getPerfilConEstudio()` y redirigir a login si es null.

### 4. Botón "Enviar directo al INPI" — 🟡 MOCK, NO ROTO PERDIDO
- La función **sí existe**. Está en modo mock a propósito hasta tener auth real + XML escapado + `credenciales_inpi` por estudio + preview obligatorio con confirmación humana. No conectar al SOAP real sin esos 4.

---

## 📋 Queries Supabase (correr en SQL Editor)

```sql
-- Q1: Últimas actas procesadas
SELECT MAX(created_at) AS ultima_acta, COUNT(*) AS total_actas FROM actas WHERE boletin_numero IS NOT NULL;
-- Q2: Alertas última semana + errores
SELECT COUNT(*) AS total_alertas FROM alertas WHERE created_at > now() - interval '7 days';
-- Q3: Logos con hash vs total
SELECT COUNT(*) FILTER (WHERE logo_phash IS NOT NULL) AS con_phash, COUNT(*) AS total FROM actas LIMIT 10;
-- Q4: Objetos en Storage
SELECT COUNT(*) AS logos_en_storage FROM storage.objects WHERE bucket_id = 'logos';
-- Q5: constraints para upsert
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'alertas'::regclass;
```

## 📋 Próximos pasos (orden sugerido)

- [ ] Fix logo storage (bucket + upload + `logo_url_acta`)
- [ ] Quitar fallback hardcodeado admin + filtrar conteo por estudio
- [ ] Agregar `INPI_CUIT`/`INPI_CLAVE` a secrets o documentar skip de oposiciones
- [ ] Migrar `datetime.utcnow()` → `datetime.now(timezone.utc)` y `import pymupdf`
- [ ] Harden `parse_boletin` contra 0-actas silencioso (si `len==0`, marcar `fallido`, no `completo`)
- [ ] Investigar TMVIEWER (requiere credenciales EUIPO, no existe hoy)
- [ ] Planes pricing (no implementado, solo flags `limite_marcas`, `puede_*`)
