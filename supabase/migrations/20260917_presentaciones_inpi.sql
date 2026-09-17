-- presentaciones_inpi: auditoría de presentaciones al INPI (Fase 2.4)
-- RLS: el usuario ve solo las presentaciones de su estudio; el insert lo hace el service_role.
-- IMPORTANTE: nunca guardar cuitInpi/claveInpi en esta tabla (se filtran en la edge function).

create table if not exists public.presentaciones_inpi (
  id uuid primary key default gen_random_uuid(),
  estudio_id uuid not null references public.estudios(id) on delete cascade,
  user_id uuid null references auth.users(id) on delete set null,
  tramite text not null,
  payload jsonb not null default '{}'::jsonb,
  acta text null,
  ok boolean not null default true,
  error text null,
  created_at timestamptz not null default now()
);

comment on table public.presentaciones_inpi is 'Bitácora de presentaciones al INPI (mock). El payload nunca contiene cuitInpi/claveInpi.';

alter table public.presentaciones_inpi enable row level security;

drop policy if exists "presentaciones select_own" on public.presentaciones_inpi;
create policy "presentaciones select_own"
  on public.presentaciones_inpi for select
  using (
    estudio_id in (
      select p.estudio_id
      from public.perfiles p
      where p.id = auth.uid()
    )
  );

drop policy if exists "presentaciones insert service_role" on public.presentaciones_inpi;
create policy "presentaciones insert service_role"
  on public.presentaciones_inpi for insert
  with check (auth.role() = 'service_role');