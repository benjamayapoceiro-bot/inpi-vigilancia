-- logo_whash: tercer hash (wavelet) para el ensemble visual phash/dhash/whash.
-- Los logos viejos sin whash siguen funcionando (ensemble usa los que haya).

alter table public.marcas_vigiladas
  add column if not exists logo_whash text null;

comment on column public.marcas_vigiladas.logo_whash is 'Hash wavelet (imagehash.whash) del logo. NULL = no calculado aún.';
