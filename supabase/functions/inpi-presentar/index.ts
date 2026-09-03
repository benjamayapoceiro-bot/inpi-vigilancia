import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
const cors = {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS"};
serve(async (req)=>{
  if(req.method==="OPTIONS") return new Response("ok",{headers:cors});
  try{
    const {denominacion,clase,titular,cuit,email,domicilio,localidad,observaciones,tipo,cuitInpi,claveInpi,logoBase64,poderBase64,poderNombre,docs} = await req.json();
    if(!clase||!titular||!cuit||!email) throw new Error("Faltan titular/clase/email");
    if(tipo!=='3' && !denominacion) throw new Error("Denominación requerida salvo Figurativa");
    if(!cuitInpi||!claveInpi) throw new Error("CUIT y Clave INPI obligatorios por presentación");
    // Construir Documentacion: poder idIndice 24, otros idIndice 1 (genérico) - ver manual pág 7
    let docXml = "";
    if(poderBase64){
      docXml += `<tem:Documentacion><tem:Documento>${poderBase64}</tem:Documento><tem:idIndice>24</tem:idIndice><tem:Archivo_Nombre>${poderNombre||'poder.pdf'}</tem:Archivo_Nombre></tem:Documentacion>`;
    }
    if(Array.isArray(docs)){
      for(const d of docs){
        docXml += `<tem:Documentacion><tem:Documento>${d.base64}</tem:Documento><tem:idIndice>1</tem:idIndice><tem:Archivo_Nombre>${d.nombre||'doc.pdf'}</tem:Archivo_Nombre></tem:Documentacion>`;
      }
    }
    if(!docXml) docXml = "<tem:Documentacion/>";
    const tipoS = tipo==='3'?'5':(tipo==='2'?'2':'1');
    const denomXml = denominacion?`<tem:Denominacion>${denominacion}</tem:Denominacion>`:'';
    const logoXml = logoBase64?`<tem:imagen><tem:Alto>10</tem:Alto><tem:Ancho>10</tem:Ancho><tem:Imagen>${logoBase64.split(',')[1]||logoBase64}</tem:Imagen></tem:imagen>`:'';
    const soap = `<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/"><soap:Body><tem:Ingresar_MarcasNuevas><tem:MarcaNueva><tem:Solicitud><tem:TipoS>${tipoS}</tem:TipoS>${denomXml}<tem:Clase>${clase}</tem:Clase>${logoXml}</tem:Solicitud><tem:Titulares><tem:Titulares><tem:NomApe>${titular}</tem:NomApe><tem:Porcentaje>100</tem:Porcentaje><tem:Nro_Cuit>${cuit}</tem:Nro_Cuit><tem:Email>${email}</tem:Email><tem:Id_Titular_Tipo>1</tem:Id_Titular_Tipo><tem:Genero>1</tem:Genero><tem:Tipo>1</tem:Tipo><tem:Domicilios><tem:Domicilios><tem:Id_Tipo_Domicilio>1</tem:Id_Tipo_Domicilio><tem:Id_Pais>9</tem:Id_Pais><tem:idProvincia>1</tem:idProvincia><tem:Localidad>${localidad||'CABA'}</tem:Localidad><tem:Domicilio>${domicilio||'Calle'}</tem:Domicilio><tem:Numero>100</tem:Numero><tem:Cod_Postal>1000</tem:Cod_Postal></tem:Domicilios><tem:Domicilios><tem:Id_Tipo_Domicilio>2</tem:Id_Tipo_Domicilio><tem:Id_Pais>9</tem:Id_Pais><tem:idProvincia>1</tem:idProvincia><tem:Localidad>${localidad||'CABA'}</tem:Localidad><tem:Domicilio>${domicilio||'Calle'}</tem:Domicilio><tem:Numero>100</tem:Numero></tem:Domicilios></tem:Domicilios></tem:Titulares></tem:Titulares><tem:Proteccion><tem:Tipo_Proteccion>S</tem:Tipo_Proteccion><tem:Observaciones>${observaciones||'Productos de la clase.'}</tem:Observaciones></tem:Proteccion>${docXml}<tem:DatosUsuario><tem:Cuit>${cuitInpi}</tem:Cuit><tem:Activa>true</tem:Activa><tem:Clave>${claveInpi}</tem:Clave></tem:DatosUsuario></tem:MarcaNueva></tem:Ingresar_MarcasNuevas></soap:Body></soap:Envelope>`;
    // Llamada real al WS INPI (placeholder - requiere endpoint real)
    // const resp = await fetch("https://portaltramites.inpi.gob.ar/MarcasWS/Marcas.asmx",{method:"POST", headers:{"Content-Type":"application/soap+xml; charset=utf-8", "SOAPAction":"http://tempuri.org/Ingresar_MarcasNuevas"}, body: soap});
    // const text = await resp.text();
    // const acta = text.match(/<Acta>(\d+)<\/Acta>/)?.[1] || null;
    // Mock por ahora: devolvemos acta simulada + log
    const acta = String(Date.now()).slice(-7);
    return new Response(JSON.stringify({ok:true, acta, preview: soap.slice(0,800)}),{headers:{...cors,"Content-Type":"application/json"}});
  }catch(e){
    return new Response(JSON.stringify({ok:false, error:String(e.message||e)}),{status:400, headers:{...cors,"Content-Type":"application/json"}});
  }
});
