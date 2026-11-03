-- The profile protection routine is trigger-only, not a public RPC.
revoke all on function public.proteger_perfil_rol() from public;
revoke all on function public.proteger_perfil_rol() from anon, authenticated;
