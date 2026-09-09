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
    let { email, username, password, estudio_id, limite_marcas, isDemo } = await req.json();
    // Permitir demo con solo username (sin email real) — genera email fake @demo.fons.legal
    if (!email && username) {
      const clean = String(username).toLowerCase().replace(/[^a-z0-9._-]/g, '').slice(0, 30) || 'demo';
      email = `${clean}@demo.fons.legal`;
      isDemo = true;
    }
    // Permitir email de mentira tipo demo@demo.test — normalizar y validar formato
    if (email && !email.includes('@')) throw new Error("email inválido (debe tener @) o usá username para demo");
    if (!email || !password || !estudio_id) throw new Error("email/username, password y estudio_id requeridos");
    // Si es demo, asegura que el email demo no choque con validación de Supabase
    const { data: newUser, error: errCreate } = await supabaseAdmin.auth.admin.createUser({ email, password, email_confirm: true, user_metadata: { isDemo: !!isDemo, username: username || null } });
    if (errCreate) throw errCreate;
    const { error: errPerfil } = await supabaseAdmin.from("perfiles").insert({ id: newUser.user.id, email, rol: "estudio", estudio_id, limite_marcas_override: limite_marcas || null });
    if (errPerfil) throw errPerfil;
    return new Response(JSON.stringify({ ok: true, user_id: newUser.user.id }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String(e.message || e) }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
