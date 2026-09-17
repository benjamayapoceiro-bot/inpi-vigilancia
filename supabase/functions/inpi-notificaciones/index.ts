// ═══════════════════════════════════════════════════════════
//  inpi-notificaciones — ConsultaNotificaciones (op del WS INPI)
// ═══════════════════════════════════════════════════════════
// Consulta de NOTIFICACIONES del usuario INPI. A diferencia de
// inpi-consulta, esta SÍ lleva DatosUsuario (CUIT + Clave), por lo que
// requiere un estudio logueado (verify_jwt: true en el deploy) y las
// credenciales se piden en el form cada vez — nunca se guardan ni se
// loguean.
//
// Body esperado (JSON):
//   { "fechaInicial":"YYYY-MM-DD", "fechaFinal":"YYYY-MM-DD",
//     "cuit":"...", "clave":"...", "expediente":"", "direccion":"",
//     "tipoNotificacion":"" }

const INPI_WS_URL = "https://ws.inpi.gob.ar/wsinpi.asmx";
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function escapeXml(s: string): string {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

function envelopeConsultaNotificaciones(
  fechaInicial: string, fechaFinal: string, cuit: string, clave: string,
  expediente = "", direccion = "", tipoNotificacion = ""
): string {
  return `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/">
  <soap:Header/>
  <soap:Body>
    <tem:ConsultaNotificaciones>
      <tem:fechaInicial>${escapeXml(fechaInicial)}</tem:fechaInicial>
      <tem:fechafinal>${escapeXml(fechaFinal)}</tem:fechafinal>
      <tem:expediente>${escapeXml(expediente)}</tem:expediente>
      <tem:direccion>${escapeXml(direccion)}</tem:direccion>
      <tem:tipoNotificacion>${escapeXml(tipoNotificacion)}</tem:tipoNotificacion>
      <tem:datosUsuario>
        <tem:Cuit>${escapeXml(cuit)}</tem:Cuit>
        <tem:Activa>true</tem:Activa>
        <tem:Clave>${escapeXml(clave)}</tem:Clave>
      </tem:datosUsuario>
    </tem:ConsultaNotificaciones>
  </soap:Body>
</soap:Envelope>`;
}

// Extracción genérica de respaldo (para ver el XML real y ajustar después).
function extraerCampos(xml: string): Record<string, string> {
  const campos: Record<string, string> = {};
  const regex = /<(?:\\w+:)?(\\w+)>([^<]*)<\/(?:\\w+:)?\1>/g;
  let m;
  while ((m = regex.exec(xml)) !== null) {
    if (m[2] && m[2].trim()) campos[m[1]] = m[2].trim();
  }
  return campos;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const { fechaInicial, fechaFinal, cuit, clave, expediente, direccion, tipoNotificacion } = await req.json();

    if (!fechaInicial || !fechaFinal || !cuit || !clave) {
      return new Response(JSON.stringify({ ok: false, error: "Faltan fechaInicial, fechaFinal, cuit y clave en el body" }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    const envelope = envelopeConsultaNotificaciones(
      fechaInicial, fechaFinal, cuit, clave,
      expediente || "", direccion || "", tipoNotificacion || ""
    );

    const resp = await fetch(INPI_WS_URL, {
      method: "POST",
      headers: {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://tempuri.org/ConsultaNotificaciones",
      },
      body: envelope,
    });

    const xmlTexto = await resp.text();

    if (!resp.ok) {
      return new Response(JSON.stringify({
        ok: false,
        error: `INPI respondió HTTP ${resp.status}`,
        xml_crudo: xmlTexto.slice(0, 4000),
      }), { status: 502, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    const campos = extraerCampos(xmlTexto);

    return new Response(JSON.stringify({
      ok: true,
      campos,
      xml_crudo: xmlTexto.slice(0, 8000),
    }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });

  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: String(err) }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});