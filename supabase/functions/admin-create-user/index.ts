import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Access-Control-Allow-Methods": "POST, OPTIONS" };
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) throw new Error("No auth");
    const supabaseAdmin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const supabaseUser = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: authHeader } } });
    const { data: { user } } = await supabaseUser.auth.getUser();
    if (!user) throw new Error("No autenticado");
    const { data: perfil } = await supabaseAdmin.from("perfiles").select("rol").eq("id", user.id).single();
    if (!perfil || perfil.rol !== "admin") throw new Error("Solo admin puede crear usuarios");
    const { email, password, estudio_id, limite_marcas } = await req.json();
    if (!email || !password || !estudio_id) throw new Error("email, password y estudio_id requeridos");
    const { data: newUser, error: errCreate } = await supabaseAdmin.auth.admin.createUser({ email, password, email_confirm: true });
    if (errCreate) throw errCreate;
    const { error: errPerfil } = await supabaseAdmin.from("perfiles").insert({ id: newUser.user.id, email, rol: "estudio", estudio_id, limite_marcas_override: limite_marcas || null });
    if (errPerfil) throw errPerfil;
    return new Response(JSON.stringify({ ok: true, user_id: newUser.user.id }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String(e.message || e) }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
