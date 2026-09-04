import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const { acta } = await req.json();
    if (!acta) return new Response(JSON.stringify({ ok: false, error: "acta requerida" }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const { data: cached } = await supabase.from("detalle_actas_inpi").select("*").eq("acta", String(acta)).limit(1).maybeSingle();
    if (cached && cached.fetched_at) {
      const ageMs = Date.now() - new Date(cached.fetched_at).getTime();
      if (ageMs < 30 * 24 * 3600 * 1000) {
        return new Response(JSON.stringify({ ok: true, data: cached, cached: true }), { headers: { ...cors, "Content-Type": "application/json" } });
      }
    }
    let grilla = null;
    try {
      const grillaResp = await fetch("https://portaltramites.inpi.gob.ar/MarcasConsultas/GrillaMarcasPuntual", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0" },
        body: `search=&sort=&order=asc&offset=0&limit=10&acta=${encodeURIComponent(acta)}`,
      });
      const grillaJson = await grillaResp.json();
      if (grillaJson && Array.isArray(grillaJson.rows) && grillaJson.rows[0]) {
        const r = grillaJson.rows[0];
        grilla = {
          acta: String(r.Acta || acta),
          titulares: r.Titulares,
          fecha_ingreso: r.Fecha_Ingreso ? new Date(parseInt(r.Fecha_Ingreso.replace(/\D/g, ""))).toISOString() : null,
          clase: String(r.Clase || ""),
          denominacion: r.Denominacion,
          tipo_marca: r.Tipo_Marca,
          numero_resolucion: String(r.Numero_Resolucion || ""),
          estado: r.Estado,
          vencimiento: r.Fecha_Vencimiento ? new Date(parseInt(r.Fecha_Vencimiento.replace(/\D/g, ""))).toISOString() : null,
        };
      }
    } catch {}
    const resp = await fetch(`https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado?acta=${encodeURIComponent(acta)}`, { headers: { "User-Agent": "Mozilla/5.0" } });
    const html = await resp.text();
    const get = (re: RegExp) => { const m = html.match(re); return m ? m[1].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 4000) : null; };
    const denominacion = grilla?.denominacion || get(/id="ContentPlaceHolder1_lblDenominacion"[^>]*>([^<]+)</i) || get(/Denominaci[oó]n[^<]*<\/[^>]+>\s*([^<]+)</i);
    const titular = grilla?.titulares || get(/id="ContentPlaceHolder1_lblTitular"[^>]*>([^<]+)</i);
    const claseRaw = grilla?.clase || get(/id="ContentPlaceHolder1_lblClase"[^>]*>([^<]+)</i);
    const clase = claseRaw ? parseInt(String(claseRaw).match(/\d+/)?.[0] || "") || null : null;
    const estado = grilla?.estado || get(/id="ContentPlaceHolder1_lblEstado"[^>]*>([^<]+)</i);
    const reivindicaciones = get(/id="ContentPlaceHolder1_lblProductos"[^>]*>([\s\S]*?)<\/span>/i)?.slice(0, 4000) || null;
    const logoMatch = html.match(/id="ContentPlaceHolder1_imgLogo"[^>]*src="([^"]+)"/i) || html.match(/<img[^>]*class="[^"]*logo[^"]*"[^>]*src="([^"]+)"/i);
    const logo_url = logoMatch ? (logoMatch[1].startsWith("http") ? logoMatch[1] : "https://portaltramites.inpi.gob.ar/" + logoMatch[1].replace(/^\//, "")) : null;
    const data = { acta: String(acta), denominacion, titular, clase, estado, reivindicaciones, logo_url, expediente_url: `https://portaltramites.inpi.gob.ar/MarcasConsultas/Grilla?acta=${acta}`, grilla, fetched_at: new Date().toISOString() };
    await supabase.from("detalle_actas_inpi").upsert(data, { onConflict: "acta" });
    return new Response(JSON.stringify({ ok: true, data, cached: false }), { headers: { ...cors, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: String(e) }), { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
  }
});
