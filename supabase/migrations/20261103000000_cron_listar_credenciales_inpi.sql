-- Restricted RPC for GitHub Actions cron to read per-study INPI credentials.
-- Credentials are decrypted only inside PostgreSQL and returned only to service_role.
create or replace function public.cron_listar_credenciales_inpi()
returns table (
  estudio_id uuid,
  cuit text,
  clave text,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_role text;
  v_key text;
begin
  v_role := coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    nullif((nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'), '')
  );

  if v_role is distinct from 'service_role' then
    raise exception 'No autorizado';
  end if;

  select decrypted_secret into v_key
  from vault.decrypted_secrets
  where name = 'vault_key'
  limit 1;

  if v_key is null or btrim(v_key) = '' then
    raise exception 'vault_key no configurada';
  end if;

  return query
    select c.estudio_id,
           c.cuit,
           extensions.pgp_sym_decrypt(c.clave_cifrada::bytea, v_key),
           c.updated_at
    from public.credenciales_inpi c
    where c.cuit is not null
      and btrim(c.cuit) <> ''
      and c.clave_cifrada is not null
    order by c.estudio_id;
end;
$function$;

revoke all on function public.cron_listar_credenciales_inpi() from public;
revoke all on function public.cron_listar_credenciales_inpi() from anon, authenticated;
grant execute on function public.cron_listar_credenciales_inpi() to service_role;

notify pgrst, 'reload schema';
