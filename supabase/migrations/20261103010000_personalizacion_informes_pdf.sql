-- Per-study customization for client-facing trademark search reports.
alter table public.estudios_config
  add column if not exists pdf_titulo text,
  add column if not exists pdf_introduccion text,
  add column if not exists pdf_conclusion text,
  add column if not exists pdf_disclaimer text,
  add column if not exists pdf_mostrar_presupuesto boolean not null default true,
  add column if not exists pdf_mostrar_proximos_pasos boolean not null default true;
