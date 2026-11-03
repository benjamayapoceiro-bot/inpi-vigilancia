-- Least-privilege reads for operational tables that are written by service_role.
create policy debug_logs_select_admin
on public.debug_logs
for select to authenticated
using (auth.uid() is not null and public.is_admin());

create policy boletines_procesados_select_admin
on public.boletines_procesados
for select to authenticated
using (auth.uid() is not null and public.is_admin());

create policy avisos_vencimiento_select_estudio
on public.avisos_vencimiento
for select to authenticated
using (
  auth.uid() is not null
  and (
    exists (
      select 1
      from public.marcas_vigiladas m
      join public.perfiles p on p.estudio_id = m.estudio_id
      where m.id = avisos_vencimiento.marca_vigilada_id
        and p.id = auth.uid()
    )
    or public.is_admin()
  )
);
