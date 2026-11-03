-- Enforce tenant ownership on the new row as well as the old row.
-- Prevents authenticated users from moving records into another study or
-- inserting records with a foreign estudio_id through permissive WITH CHECK.
alter policy marcas_update_own on public.marcas_vigiladas
  with check (
    auth.uid() is not null
    and (
      estudio_id in (select p.estudio_id from public.perfiles p where p.id = auth.uid())
      or public.is_admin()
    )
  );

alter policy alertas_update_estudio on public.alertas
  with check (
    auth.uid() is not null
    and (
      exists (
        select 1 from public.marcas_vigiladas m
        join public.perfiles p on p.estudio_id = m.estudio_id
        where m.id = alertas.marca_vigilada_id and p.id = auth.uid()
      )
      or public.is_admin()
    )
  );

alter policy plazos_update_estudio on public.plazos_legales
  with check (
    auth.uid() is not null
    and (
      exists (
        select 1 from public.marcas_vigiladas m
        join public.perfiles p on p.estudio_id = m.estudio_id
        where m.id = plazos_legales.marca_vigilada_id and p.id = auth.uid()
      )
      or public.is_admin()
    )
  );

alter policy clientes_write_own on public.clientes
  with check (
    auth.uid() is not null
    and (
      estudio_id in (select p.estudio_id from public.perfiles p where p.id = auth.uid())
      or public.is_admin()
    )
  );

alter policy eventos_write_own on public.eventos_manuales
  with check (
    auth.uid() is not null
    and (
      estudio_id in (select p.estudio_id from public.perfiles p where p.id = auth.uid())
      or public.is_admin()
    )
  );

alter policy config_write_own on public.estudios_config
  with check (
    auth.uid() is not null
    and (
      estudio_id in (select p.estudio_id from public.perfiles p where p.id = auth.uid())
      or public.is_admin()
    )
  );
