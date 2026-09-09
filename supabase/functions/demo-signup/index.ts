import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Access-Control-Allow-Methods": "POST, OPTIONS" };
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const { email, password, estudio_nombre } = await req.json();
    if (!email || !password || !estudio_nombre) throw new Error("email, password y estudio_nombre requeridos");
    if (!email.includes('@') || password.length < 6) throw new Error("email inválido o clave muy corta (mín 6)");
    const supabaseAdmin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    // Crear estudio demo con límite 1, sin INPI/presentar para que no abuse
    const { data: estudio, error: errEst } = await supabaseAdmin.from("estudios").insert({
      nombre: estudio_nombre.slice(0,60),
      email_contacto: email,
      limite_marcas: 1,
      plan: "demo",
      puede_conectar_inpi: false,
      puede_presentar: false,
      puede_ver_alertas: true
    }).select("id").single();
    if (errEst) throw errEst;
    const { data: newUser, error: errCreate } = await supabaseAdmin.auth.admin.createUser({ email, password, email_confirm: true });
    if (errCreate) throw errCreate;
    const { error: errPerfil } = await supabaseAdmin.from("perfiles").insert({ id: newUser.user.id, email, rol: "estudio", estudio_id: estudio.id });
    if (errPerfil) throw errPerfil;
    return new Response(JSON.stringify({ ok: true, estudio_id: estudio.id, user_id: newUser.user.id }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String(e.message || e) }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
