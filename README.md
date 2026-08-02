# Vigilancia de marcas INPI

Cron semanal que:
1. Chequea boletines nuevos de "MARCAS NUEVAS" en portaltramites.inpi.gob.ar
2. Los descarga y parsea (texto + logos de marcas mixtas)
3. Compara contra la cartera de `marcas_vigiladas` en Supabase (similitud
   ortográfica/fonética para denominativas, perceptual hash para logos)
4. Inserta alertas en Supabase

## Archivos
- `parse_boletin.py` — extrae actas del texto del PDF (probado sobre 1910 actas reales)
- `extract_logos.py` — asocia logos a sus actas y calcula pHash (94% cobertura probada)
- `matcher.py` — motor de similitud (texto + logo)
- `cron_check_boletines.py` — orquesta todo, corre semanalmente vía GitHub Actions
- `schema.sql` — schema de Supabase (ya aplicado)

## Setup
Secrets necesarios en GitHub (Settings → Secrets and variables → Actions):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
