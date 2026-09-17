// ═══════════════════════════════════════════════════════════
//  inpi-consulta — Proxy SOAP hacia ws.inpi.gob.ar/wsinpi.asmx
// ═══════════════════════════════════════════════════════════
// Consultas de SOLO LECTURA del Servicio Web de ingreso de trámites
// del INPI. No presenta trámites ni usa credenciales de usuario —
// ConsultaDenominacion y ConsultaCuitOTitular son públicas según el
// manual oficial (no llevan nodo DatosUsuario).
//
// Body esperado (JSON):
//   { "tipo": "denominacion", "valor": "MARCA A BUSCAR" }
//   { "tipo": "cuit", "valor": "20458255297" }

const INPI_WS_URL = "https://ws.inpi.gob.ar/wsinpi.asmx";
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function envelopeConsultaDenominacion(denominacion: string): string {
  return `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/">
  <soap:Header/>
  <soap:Body>
    <tem:ConsultaDenominacion>
      <tem:Denominacion>${escapeXml(denominacion)}</tem:Denominacion>
    </tem:ConsultaDenominacion>
  </soap:Body>
</soap:Envelope>`;
}

function envelopeConsultaCuitOTitular(cuit: string, titular = ""): string {
  return `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/">
  <soap:Header/>
  <soap:Body>
    <tem:ConsultaCuitOTitular>
      <tem:cuit>${escapeXml(cuit)}</tem:cuit>
      <tem:titular>${escapeXml(titular)}</tem:titular>
    </tem:ConsultaCuitOTitular>
  </soap:Body>
</soap:Envelope>`;
}

function escapeXml(s: string): string {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

// Parseo específico de la respuesta real de ConsultaDenominacion:
// <ConsultaDenominacionResult><total>N</total><estado>...</estado>
//   <rows><GrillaMarcas>...campos...</GrillaMarcas><GrillaMarcas>...</GrillaMarcas>...</rows>
// </ConsultaDenominacionResult>
// Nota: <estado> a nivel resultado es un flag de estado del SERVICIO, no de
// la marca — cada <GrillaMarcas> tiene su propio <Estado> (código de la marca).
function extraerCampoSimple(xml: string, tag: string): string | null {
  const m = xml.match(new RegExp(`<${tag}>([^<]*)<\\/${tag}>`));
  return m ? m[1].trim() : null;
}

function parsearConsultaDenominacion(xml: string) {
  const total = extraerCampoSimple(xml, "total");
  const estadoServicio = extraerCampoSimple(xml, "estado");

  const bloques = [...xml.matchAll(/<GrillaMarcas>([\s\S]*?)<\/GrillaMarcas>/g)].map(m => m[1]);
  const resultados = bloques.map(b => ({
    acta: extraerCampoSimple(b, "Acta"),
    titulares: extraerCampoSimple(b, "Titulares"),
    fecha_ingreso: extraerCampoSimple(b, "Fecha_Ingreso"),
    clase: extraerCampoSimple(b, "Clase"),
    denominacion: extraerCampoSimple(b, "Denominacion"),
    tipo_marca: extraerCampoSimple(b, "Tipo_Marca"),
    numero_resolucion: extraerCampoSimple(b, "Numero_Resolucion"),
    estado: extraerCampoSimple(b, "Estado"),
  }));

  return { total: total ? parseInt(total, 10) : resultados.length, estado_servicio: estadoServicio, resultados };
}

// Extracción genérica de respaldo (para tipo "cuit" u otras consultas de
// registro único, sin listas repetidas) — sin asumir esquema exacto.
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
    const { tipo, valor, titular } = await req.json();

    if (!tipo || !valor) {
      return new Response(JSON.stringify({ ok: false, error: "Faltan 'tipo' y 'valor' en el body" }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    let soapAction: string;
    let envelope: string;

    if (tipo === "denominacion") {
      soapAction = "http://tempuri.org/ConsultaDenominacion";
      envelope = envelopeConsultaDenominacion(valor);
    } else if (tipo === "cuit") {
      soapAction = "http://tempuri.org/ConsultaCuitOTitular";
      envelope = envelopeConsultaCuitOTitular(valor, titular || "");
    } else {
      return new Response(JSON.stringify({ ok: false, error: `tipo desconocido: ${tipo}` }), {
        status: 400,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }

    const resp = await fetch(INPI_WS_URL, {
      method: "POST",
      headers: {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soapAction,
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

    if (tipo === "denominacion") {
      const { total, estado_servicio, resultados } = parsearConsultaDenominacion(xmlTexto);
      return new Response(JSON.stringify({
        ok: true,
        tipo,
        valor,
        total,
        estado_servicio,
        resultados,
        xml_crudo: xmlTexto.slice(0, 6000),
      }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });
    }

    return new Response(JSON.stringify({
      ok: true,
      tipo,
      valor,
      campos,
      xml_crudo: xmlTexto.slice(0, 6000),
    }), { headers: { ...CORS_HEADERS, "Content-Type": "application/json" } });

  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: String(err) }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});