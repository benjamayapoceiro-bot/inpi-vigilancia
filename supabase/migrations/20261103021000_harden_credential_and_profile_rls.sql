-- Protect encrypted INPI credentials and profile ownership against tenant changes.
alter policy credenciales_write_own on public.credenciales_inpi
  with check (
    auth.uid() is not null
    and (
      auth.uid() in (
        select p.id from public.perfiles p
        where p.estudio_id = credenciales_inpi.estudio_id
      )
      or public.is_admin()
    )
  );

alter policy perfiles_update_own on public.perfiles
  with check (auth.uid() = id or public.is_admin());
