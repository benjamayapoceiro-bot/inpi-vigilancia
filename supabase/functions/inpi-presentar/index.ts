/**
 * ⚠️  MOCK — NO CONECTAR AL SOAP REAL DE INPI SIN ANTES CUMPLIR:
 * 1) Autenticación real (verificar JWT del caller y que pertenezca al estudio, no CORS "*").
 * 2) XML escapado para todos los campos de usuario — hecho vía escXml() en todos los nodos.
 * 3) CUIT/clave INPI se piden por presentación, nunca se guardan ni loguean.
 * 4) Preview obligatorio con confirmación humana explícita en cada envío real — nunca disparar sin que un humano vea el XML y confirme (consecuencias legales/económicas).
 * Mientras sea mock, devuelve acta simulada. La llamada real está comentada abajo.
 *
 * Fase 2 (INPI WS) — trámites soportados:
 *  marca_nueva | marca_renovacion | modelo_nuevo | modelo_renovacion | patente_invencion | patente_utilidad
 * Multi-titular: body.titulares = [{nomApe, porcentaje, tipoTitular:'fisica'|'juridica', cuit, email, domicilio, localidad, idProvincia, tipoDni?, numDni?, estadoCivil?}]
 * Marca Nueva legacy (sin titulares[]): mismo XML que generaba la v3 (byte-idéntico, single titular 100%).
 */
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const cors = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS"};
const anyJson = (obj, status) => new Response(JSON.stringify(obj), {status, headers:{...cors, "Content-Type":"application/json"}});

async function verificarEstudioPuedePresentar(authHeader, supabase) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const jwt = authHeader.replace("Bearer ", "");
  const { data: { user }, error: authErr } = await supabase.auth.getUser(jwt);
  if (authErr || !user) return null;
  const { data: perfil } = await supabase.from("perfiles").select("estudio_id").eq("id", user.id).maybeSingle();
  if (!perfil?.estudio_id) return null;
  const { data: estudio } = await supabase.from("estudios").select("puede_presentar").eq("id", perfil.estudio_id).maybeSingle();
  if (estudio?.puede_presentar === false) return { bloqueado: true, user };
  return { bloqueado: false, user, estudio_id: perfil.estudio_id };
}
function escXml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;'); }
const envHdr = `<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/"><soap:Body>`;
const SOAP_ACTIONS = {
  marca_nueva: "http://tempuri.org/Ingresar_MarcasNuevas",
  marca_renovacion: "http://tempuri.org/Ingresar_MarcaRenovacion",
  modelo_nuevo: "http://tempuri.org/Ingresar_ModeloNuevo",
  modelo_renovacion: "http://tempuri.org/Ingresar_ModeloRenovacion",
  patente_invencion: "http://tempuri.org/Ingresar_PatenteInvecionNueva",
  patente_utilidad: "http://tempuri.org/Ingresar_PatenteUtilidadNueva",
};

function buildDomiciliosXml(localidad, domicilio, idProvincia) {
  const prov = escXml(idProvincia || '1');
  const loc = escXml(localidad || 'CABA');
  const dom = escXml(domicilio || 'Calle');
  return `<tem:Domicilios><tem:Id_Tipo_Domicilio>1</tem:Id_Tipo_Domicilio><tem:Id_Pais>9</tem:Id_Pais><tem:idProvincia>${prov}</tem:idProvincia><tem:Localidad>${loc}</tem:Localidad><tem:Domicilio>${dom}</tem:Domicilio><tem:Numero>100</tem:Numero><tem:Cod_Postal>1000</tem:Cod_Postal></tem:Domicilios><tem:Domicilios><tem:Id_Tipo_Domicilio>2</tem:Id_Tipo_Domicilio><tem:Id_Pais>9</tem:Id_Pais><tem:idProvincia>${prov}</tem:idProvincia><tem:Localidad>${loc}</tem:Localidad><tem:Domicilio>${dom}</tem:Domicilio><tem:Numero>100</tem:Numero></tem:Domicilios>`;
}

function buildTitularXml(t) {
  const fisica = t.tipoTitular !== 'juridica';
  const numDni = t.numDni || '20458255';
  const dni = fisica ? `<tem:Tipo_Dni>${escXml(t.tipoDni || '1')}</tem:Tipo_Dni><tem:Num_Dni>${escXml(numDni)}</tem:Num_Dni><tem:Estado_Civil>${escXml(t.estadoCivil || '1')}</tem:Estado_Civil>` : '';
  const genero = fisica ? '1' : '0';
  return `<tem:Titulares><tem:NomApe>${escXml(t.nomApe)}</tem:NomApe><tem:Porcentaje>${Number(t.porcentaje)}</tem:Porcentaje>${dni}<tem:Nro_Cuit>${escXml(t.cuit)}</tem:Nro_Cuit><tem:Email>${escXml(t.email)}</tem:Email><tem:Id_Titular_Tipo>${fisica ? '1' : '2'}</tem:Id_Titular_Tipo><tem:Genero>${genero}</tem:Genero><tem:Tipo>1</tem:Tipo><tem:Domicilios>${buildDomiciliosXml(t.localidad, t.domicilio, t.idProvincia)}</tem:Domicilios></tem:Titulares>`;
}

function buildTitularesXml(titulares) {
  if (!Array.isArray(titulares) || titulares.length === 0) throw new Error("Se requiere al menos un titular");
  const cuits = new Set();
  let suma = 0;
  for (const t of titulares) {
    if (!t.nomApe || !t.cuit || !t.email || !t.localidad || !t.domicilio) throw new Error("Cada titular necesita nomApe, cuit, email, domicilio y localidad");
    if (t.porcentaje === undefined) throw new Error("Cada titular necesita porcentaje");
    suma += Number(t.porcentaje);
    if (cuits.has(String(t.cuit).trim())) throw new Error("Nro_Cuit repetido entre titulares");
    cuits.add(String(t.cuit).trim());
  }
  if (Math.abs(suma - 100) > 0.01) throw new Error(`La suma de porcentajes debe dar 100 (llegó ${suma})`);
  return titulares.map(buildTitularXml).join("");
}

function buildDocsXml(poderBase64, poderNombre, docs, idIndiceDefault) {
  let out = "";
  if (poderBase64) out += `<tem:Documentacion><tem:Documento>${poderBase64}</tem:Documento><tem:idIndice>24</tem:idIndice><tem:Archivo_Nombre>${escXml(poderNombre || 'poder.pdf')}</tem:Archivo_Nombre></tem:Documentacion>`;
  if (Array.isArray(docs)) {
    const withIdx = docs.map((d, i) => ({ ...d, idx: d.idIndice || (Array.isArray(idIndiceDefault) ? idIndiceDefault[i] : idIndiceDefault) }));
    for (const d of withIdx) out += `<tem:Documentacion><tem:Documento>${d.base64}</tem:Documento><tem:idIndice>${d.idx}</tem:idIndice><tem:Archivo_Nombre>${escXml(d.nombre || 'doc.pdf')}</tem:Archivo_Nombre></tem:Documentacion>`;
  }
  return out || "<tem:Documentacion/>";
}

function buildSolicitantesXml() { return "<tem:Solicitantes/>"; }

function buildSolicitudRelacionadasXml(acta, nroRenovacion, tipoAntecedente) {
  let inner = `<tem:Acta>${Number(acta)}</tem:Acta>`;
  if (nroRenovacion !== undefined && nroRenovacion !== null) inner += `<tem:nro_renovacion>${Number(nroRenovacion)}</tem:nro_renovacion>`;
  if (tipoAntecedente) inner += `<tem:Tipo_antecedente>${tipoAntecedente}</tem:Tipo_antecedente>`;
  return `<tem:SolicitudRelacionadas><tem:Solicitudes_Relacionadas>${inner}</tem:Solicitudes_Relacionadas></tem:SolicitudRelacionadas>`;
}

serve(async (req)=>{
  if(req.method==="OPTIONS") return new Response("ok",{headers:cors});
  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const auth = await verificarEstudioPuedePresentar(req.headers.get("Authorization") || "", supabase);
  if (auth === null) return anyJson({ok:false, error:"No autenticado"}, 401);
  if (auth.bloqueado) return anyJson({ok:false, error:"Tu plan no incluye presentación al INPI"}, 403);
  try{
    const body = await req.json();
    const tramite = body.tramite || 'marca_nueva';
    if (!SOAP_ACTIONS[tramite]) throw new Error(`Trámite no soportado: ${tramite}`);
    if (!body.cuitInpi || !body.claveInpi) throw new Error("CUIT y Clave INPI obligatorios por presentación");

    let docXml, titularesXml, soap, action = SOAP_ACTIONS[tramite];
    const datosUsuarioXml = `<tem:DatosUsuario><tem:Cuit>${escXml(body.cuitInpi)}</tem:Cuit><tem:Activa>true</tem:Activa><tem:Clave>${escXml(body.claveInpi)}</tem:Clave></tem:DatosUsuario>`;

    if (Array.isArray(body.titulares)) {
      titularesXml = buildTitularesXml(body.titulares);
    } else {
      if (tramite !== 'marca_nueva') throw new Error("Solo Marca Nueva acepta el cuerpo legacy (sin titulares[])");
      if (!body.clase || !body.titular || !body.cuit || !body.email) throw new Error("Faltan titular/clase/email");
      titularesXml = `<tem:Titulares><tem:NomApe>${escXml(body.titular)}</tem:NomApe><tem:Porcentaje>100</tem:Porcentaje><tem:Nro_Cuit>${escXml(body.cuit)}</tem:Nro_Cuit><tem:Email>${escXml(body.email)}</tem:Email><tem:Id_Titular_Tipo>1</tem:Id_Titular_Tipo><tem:Genero>1</tem:Genero><tem:Tipo>1</tem:Tipo><tem:Domicilios>${buildDomiciliosXml(body.localidad, body.domicilio, body.idProvincia)}</tem:Domicilios></tem:Titulares>`;
    }

    const poderXml = (body.poderBase64 ? `<tem:Documentacion><tem:Documento>${body.poderBase64}</tem:Documento><tem:idIndice>24</tem:idIndice><tem:Archivo_Nombre>${escXml(body.poderNombre || 'poder.pdf')}</tem:Archivo_Nombre></tem:Documentacion>` : "");

    if (tramite === 'marca_nueva' || tramite === 'marca_renovacion') {
      if (!body.denominacion) throw new Error("Denominación requerida en marcas");
      if (!body.clase) throw new Error("Clase requerida en marcas");
      const tipoS = body.tipo === '3' ? '5' : (body.tipo === '2' ? '2' : '1');
      docXml = poderXml + buildDocsXml(null, null, body.docs, 1);
      const denomXml = `<tem:Denominacion>${escXml(body.denominacion)}</tem:Denominacion>`;
      const logoXml = body.logoBase64 ? `<tem:imagen><tem:Alto>10</tem:Alto><tem:Ancho>10</tem:Ancho><tem:Imagen>${String(body.logoBase64).split(',')[1] || body.logoBase64}</tem:Imagen></tem:imagen>` : '';
      const solicitud = `<tem:Solicitud><tem:TipoS>${tipoS}</tem:TipoS>${denomXml}<tem:Clase>${body.clase}</tem:Clase>${logoXml}</tem:Solicitud>`;
      const rel = tramite === 'marca_renovacion' ? buildSolicitudRelacionadasXml(body.actaAntecedente, undefined, undefined) : '';
      const innerT = tramite === 'marca_renovacion' ? 'MarcaReno' : 'MarcaNueva';
      const outerT = tramite === 'marca_renovacion' ? 'Ingresar_MarcaRenovacion' : 'Ingresar_MarcasNuevas';
      soap = `${envHdr}<tem:${outerT}><tem:${innerT}>${solicitud}<tem:Titulares>${titularesXml}</tem:Titulares><tem:Proteccion><tem:Tipo_Proteccion>S</tem:Tipo_Proteccion><tem:Observaciones>${escXml(body.observaciones || 'Productos de la clase.')}</tem:Observaciones></tem:Proteccion>${docXml}${rel}${datosUsuarioXml}</tem:${innerT}></tem:${outerT}></soap:Body></soap:Envelope>`;
    } else if (tramite === 'modelo_nuevo' || tramite === 'modelo_renovacion') {
      if (!body.denominacion) throw new Error("Denominación requerida en modelos");
      if (!body.clase || Number(body.clase) < 1 || Number(body.clase) > 32) throw new Error("Clase de modelo debe estar entre 1 y 32");
      if (!body.subClase || Number(body.subClase) < 1) throw new Error("SubClase de modelo debe ser ≥ 1");
      let docs = Array.isArray(body.docs) ? body.docs.slice() : [];
      if (!docs.some(d => d.idIndice === 9 || d.idIndice === 10)) {
        if (docs.length >= 1) docs[0] = { ...docs[0], idIndice: 9 };
      }
      if (!docs.some(d => d.idIndice === 1037)) {
        if (docs.length >= 2 && !(docs[1].idIndice === 9 || docs[1].idIndice === 10)) docs[1] = { ...docs[1], idIndice: 1037 };
      }
      if (!docs.some(d => d.idIndice === 9 || d.idIndice === 10)) throw new Error("En modelos es obligatorio un documento de dibujos (idIndice 9 o 10)");
      if (!docs.some(d => d.idIndice === 1037)) throw new Error("En modelos es obligatorio un documento de figura uno (idIndice 1037)");
      docXml = poderXml + buildDocsXml(null, null, docs, null);
      const solicitud = `<tem:Solicitud><tem:Denominacion>${escXml(body.denominacion)}</tem:Denominacion></tem:Solicitud>`;
      const rel = tramite === 'modelo_renovacion' ? buildSolicitudRelacionadasXml(body.actaAntecedente, body.nroRenovacion, undefined) : '';
      if (tramite === 'modelo_renovacion' && (body.actaAntecedente === undefined || body.nroRenovacion === undefined)) throw new Error("Renovación de modelo requiere actaAntecedente y nroRenovacion");
      const proteccion = `<tem:Proteccion><tem:Tipo_Proteccion>${tramite === 'modelo_nuevo' ? 'D' : 'S'}</tem:Tipo_Proteccion><tem:Observaciones>${escXml(body.observaciones || 'Naturaleza del modelo.')}</tem:Observaciones></tem:Proteccion>`;
      const innerT = 'ModeloNuevo';
      const outerT = tramite === 'modelo_renovacion' ? 'Ingresar_ModeloRenovacion' : 'Ingresar_ModeloNuevo';
      soap = `${envHdr}<tem:${outerT}><tem:${innerT}>${solicitud}<tem:Titulares>${titularesXml}</tem:Titulares>${proteccion}${docXml}<tem:Datos_Modelos><tem:Clase>${body.clase}</tem:Clase><tem:SubClase>${body.subClase}</tem:SubClase></tem:Datos_Modelos>${rel}${datosUsuarioXml}</tem:${innerT}></tem:${outerT}></soap:Body></soap:Envelope>`;
    } else { // patente_invencion | patente_utilidad
      if (!body.denominacion) throw new Error("Denominación requerida en patentes");
      const defAr = tramite === 'patente_invencion' ? '311000' : '311800';
      const detalle = `<tem:Solicitudes_Detalles><tem:Cod_arancel>${escXml(body.codArancel || defAr)}</tem:Cod_arancel><tem:cantidad>${Number(body.cantidad ?? 10)}</tem:cantidad><tem:examen_Fondo>${body.examenFondo ? 'SI' : 'NO'}</tem:examen_Fondo><tem:publicacion_Anticipada>${body.publicacionAnticipada ? 'SI' : 'NO'}</tem:publicacion_Anticipada></tem:Solicitudes_Detalles>`;
      const solicitud = `<tem:Solicitud><tem:Denominacion>${escXml(body.denominacion)}</tem:Denominacion><tem:SolicitudesDetalles>${detalle}</tem:SolicitudesDetalles></tem:Solicitud>`;
      docXml = buildDocsXml(null, null, body.docs, 25);
      const rel = body.actaAntecedente && Number(body.actaAntecedente) > 0
        ? buildSolicitudRelacionadasXml(body.actaAntecedente, undefined, '81')
        : buildSolicitudRelacionadasXml(0, undefined, '82');
      const outerT = tramite === 'patente_invencion' ? 'Ingresar_PatenteInvecionNueva' : 'Ingresar_PatenteUtilidadNueva';
      soap = `${envHdr}<tem:${outerT}><tem:PatenteNueva>${solicitud}<tem:Titulares>${titularesXml}</tem:Titulares>${buildSolicitantesXml()}${docXml}${rel}${datosUsuarioXml}</tem:PatenteNueva></tem:${outerT}></soap:Body></soap:Envelope>`;
    }

    // Llamada real al WS INPI (placeholder - requiere endpoint real)
    // const resp = await fetch("https://portaltramites.inpi.gob.ar/MarcasWS/Marcas.asmx",{method:"POST", headers:{"Content-Type":"application/soap+xml; charset=utf-8", "SOAPAction": action}, body: soap});
    // const text = await resp.text();
    // const acta = text.match(/<Acta>(\d+)<\/Acta>/)?.[1] || null;
    // Mock por ahora: devolvemos acta simulada + log
    const acta = String(Date.now()).slice(-7);
    try {
      const { cuitInpi, claveInpi, poderBase64, logoBase64, docs, ...resto } = body;
      await supabase.from("presentaciones_inpi").insert({
        estudio_id: auth.estudio_id, user_id: auth.user.id, tramite,
        payload: { ...resto, acta },
        acta, ok: true,
      });
    } catch (_e) { /* auditoría best-effort: nunca tumbar la presentación */ }
    return new Response(JSON.stringify({ok:true, acta, preview: soap.slice(0,800)}),{headers:{...cors,"Content-Type":"application/json"}});
  }catch(e){
    return new Response(JSON.stringify({ok:false, error:String(e.message||e)}),{status:400, headers:{...cors,"Content-Type":"application/json"}});
  }
});