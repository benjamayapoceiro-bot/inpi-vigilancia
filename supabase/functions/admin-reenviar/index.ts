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
    if (!perfil || perfil.rol !== "admin") throw new Error("Solo admin puede reenviar");
    const { estudio_id } = await req.json();
    if (!estudio_id) throw new Error("estudio_id requerido");
    const pat = Deno.env.get("GITHUB_PAT");
    if (!pat) throw new Error("Falta GITHUB_PAT en secrets (PAT fine-grained con Actions:write en inpi-vigilancia)");
    const r = await fetch("https://api.github.com/repos/benjamayapoceiro-bot/inpi-vigilancia/actions/workflows/reenviar.yml/dispatches", {
      method: "POST",
      headers: { "Accept": "application/vnd.github+json", "Authorization": `Bearer ${pat}`, "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main", inputs: { estudio_id } }),
    });
    if (!r.ok) throw new Error(`GitHub dispatch falló: ${r.status} ${await r.text()}`);
    return new Response(JSON.stringify({ ok: true }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String((e as Error).message || e) }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
