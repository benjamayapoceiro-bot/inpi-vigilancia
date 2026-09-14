-- Logo storage: bucket privado + columnas para logos lado a lado
-- Correr en Supabase SQL Editor (idempotente)

-- 1. Columnas (si no existen)
alter table public.marcas_vigiladas add column if not exists logo_url text;
alter table public.marcas_vigiladas add column if not exists logo_phash text;
alter table public.marcas_vigiladas add column if not exists logo_dhash text;
alter table public.marcas_vigiladas add column if not exists logo_pendiente text;
alter table public.alertas add column if not exists logo_url_acta text;
alter table public.alertas add column if not exists logo_url_cartera text;

-- 2. Bucket privado (vía storage API o dashboard; SQL directo como fallback)
insert into storage.buckets (id, name, public)
values ('logos-marcas', 'logos-marcas', false)
on conflict (id) do nothing;

-- 3. Policies Storage: solo authenticated puede leer sus propios objetos
-- (el path es logos/{marca_id}.png ; el service_role del cron saltea RLS para escribir)
drop policy if exists "logos lectura authenticated" on storage.objects;
create policy "logos lectura authenticated"
  on storage.objects for select
  using (bucket_id = 'logos-marcas' and auth.role() = 'authenticated');

drop policy if exists "logos escritura service_role" on storage.objects;
create policy "logos escritura service_role"
  on storage.objects for insert
  with check (bucket_id = 'logos-marcas');

-- 4. Unique para el upsert del cron (si no existe)
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'alertas_marca_acta_boletin_uniq') then
    alter table public.alertas
      add constraint alertas_marca_acta_boletin_uniq
      unique (marca_vigilada_id, acta_nueva, boletin_numero);
  end if;
end $$;
