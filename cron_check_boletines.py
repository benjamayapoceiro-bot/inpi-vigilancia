"""
Cron semanal — correr con GitHub Actions.

Flujo:
1. Lee https://portaltramites.inpi.gob.ar/Boletines?Tipo_Item=3
2. Filtra boletines "MARCAS NUEVAS" no procesados (chequea contra Supabase)
3. Descarga y parsea cada PDF nuevo (texto + logos)
4. Corre el matcher contra la cartera de marcas_vigiladas en Supabase
5. Inserta alertas y marca el boletín como procesado

Variables de entorno necesarias:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Cualquier error, incluso de import o de variables de entorno faltantes,
se reporta a la tabla debug_logs de Supabase (si es posible) para poder
diagnosticar sin depender de los logs de GitHub Actions.
"""
import os
import sys
import time
import traceback
import requests

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def reportar_a_supabase(mensaje: str):
    """Best-effort: si esto también falla, no rompe nada más."""
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("No hay SUPABASE_URL/KEY seteados, no puedo reportar a debug_logs")
            return
        requests.post(
            f"{SUPABASE_URL}/rest/v1/debug_logs",
            headers=HEADERS,
            json=[{"mensaje": mensaje[:4000]}],
            timeout=15,
        )
    except Exception as e:
        print("no se pudo reportar a debug_logs:", e)


def run():
    import re
    import subprocess
    from datetime import datetime, timedelta

    from parse_boletin import parse_boletin
    from matcher import buscar_coincidencias
    from extract_logos import extraer_logos
    from mantenimiento_cartera import procesar_logos_pendientes, generar_avisos_vencimiento
    from notificar_email import enviar_resumen
    from consultar_notificaciones_inpi import consultar_oposiciones_nuevas

    INPI_LISTADO = "https://portaltramites.inpi.gob.ar/Boletines?Tipo_Item=3"

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            f"Faltan variables de entorno. SUPABASE_URL presente: {bool(SUPABASE_URL)}, "
            f"SUPABASE_SERVICE_ROLE_KEY presente: {bool(SUPABASE_KEY)}"
        )

    def supabase_get(tabla, params=""):
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()

    def supabase_upsert(tabla, rows, on_conflict):
        if not rows:
            return
        headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{tabla}?on_conflict={on_conflict}",
            headers=headers, json=rows, timeout=60,
        )
        r.raise_for_status()
        return r.json()

    def supabase_insert(tabla, rows):
        if not rows:
            return
        r = requests.post(f"{SUPABASE_URL}/rest/v1/{tabla}", headers=HEADERS, json=rows, timeout=30)
        r.raise_for_status()

    def supabase_patch(tabla, id_, campos):
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/{tabla}?id=eq.{id_}", headers=HEADERS, json=campos, timeout=30)
        r.raise_for_status()

    def supabase_patch_boletin(numero, campos):
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/boletines_procesados?numero_boletin=eq.{numero}",
            headers={**HEADERS, "Prefer": "return=representation"}, json=campos, timeout=30,
        )
        r.raise_for_status()
        if not r.json():
            raise RuntimeError(f"No se pudo actualizar el estado del boletín {numero}")

    # Mantenimiento de cartera: procesa logos subidos desde el dashboard y
    # genera avisos de vencimiento — se hace en cada corrida, haya o no boletines nuevos.
    procesar_logos_pendientes(
        supabase_get, supabase_patch, supabase_insert,
    )
    avisos_venc = generar_avisos_vencimiento(
        supabase_get, supabase_insert,
    )

    def listar_boletines_marcas_nuevas():
        r = requests.get(INPI_LISTADO, timeout=30)
        r.raise_for_status()
        html = r.text
        filas = re.findall(
            r'(\d{4,5})\s*</td>\s*<td[^>]*>\s*Boletines\s*</td>\s*<td[^>]*>\s*Marcas\s*</td>\s*'
            r'<td[^>]*>\s*([\d/]+)[^<]*</td>\s*<td[^>]*>.*?href="([^"]+\.pdf)".*?</td>\s*'
            r'<td[^>]*>\s*MARCAS NUEVAS',
            html, re.DOTALL | re.IGNORECASE,
        )
        return [{"numero": n, "fecha": f, "url": u if u.startswith("http") else f"https://portaltramites.inpi.gob.ar{u}"}
                for n, f, u in filas]

    ya_procesados = {
        b["numero_boletin"] for b in supabase_get(
            "boletines_procesados", "select=numero_boletin&estado=eq.completo"
        )
    }

    boletines = listar_boletines_marcas_nuevas()
    reportar_a_supabase(f"Listado INPI: {len(boletines)} boletines encontrados en la página")

    nuevos = [b for b in boletines if b["numero"] not in ya_procesados]
    nuevos = sorted(nuevos, key=lambda b: b["numero"])
    reportar_a_supabase(f"Pendientes o reintentables: {len(nuevos)} boletines")

    cartera = supabase_get("marcas_vigiladas", "select=id,nombre,clase,cliente,tipo,logo_phash,logo_dhash,numero_acta")
    cartera = [{"id": m["id"], "nombre": m["nombre"], "clase": m["clase"],
                "cliente": m.get("cliente", ""), "tipo": m.get("tipo", "D"),
                "logo_phash": m.get("logo_phash"), "logo_dhash": m.get("logo_dhash"),
                "numero_acta": m.get("numero_acta")} for m in cartera]

    todas_las_alertas_fuertes = []
    
    # ── CHECK OPOSICIONES RECIBIDAS (API SOAP) ──
    oposiciones = consultar_oposiciones_nuevas(cartera, dias_atras=7)
    if oposiciones:
        # Se insertan en la base con un boletin_numero ficticio (0) para las oposiciones
        for op in oposiciones:
            op["boletin_numero"] = 0
            op["fecha_publicacion"] = datetime.utcnow().date().isoformat()
            op["nivel_riesgo"] = "alto"
            op["similitud_score"] = 1.0
            
        try:
            # Usar acta_nueva como clave única secundaria
            supabase_upsert("alertas", oposiciones, "marca_vigilada_id,acta_nueva,boletin_numero")
            todas_las_alertas_fuertes.extend(oposiciones)
            reportar_a_supabase(f"Oposiciones recibidas y guardadas: {len(oposiciones)}")
        except Exception as e:
            reportar_a_supabase(f"Error guardando oposiciones: {e}")

    if not nuevos:
        enviar_resumen(todas_las_alertas_fuertes, avisos_venc)
        reportar_a_supabase("OK: corrida completa, sin boletines nuevos")
        return
    inicio = time.time()
    PRESUPUESTO_SEGUNDOS = 12 * 60  # deja margen dentro del límite de GitHub Actions
    procesados_esta_corrida = 0

    for b in nuevos:
        if time.time() - inicio > PRESUPUESTO_SEGUNDOS:
            reportar_a_supabase(
                f"Presupuesto de tiempo agotado: {procesados_esta_corrida}/{len(nuevos)} procesados esta corrida, "
                f"el resto sigue en la próxima."
            )
            break

        try:
            fecha_publicacion = datetime.strptime(b["fecha"], "%d/%m/%Y").date()
            # Queda pendiente hasta que las alertas se hayan persistido correctamente.
            supabase_upsert("boletines_procesados", [{
                "numero_boletin": b["numero"],
                "fecha_boletin": fecha_publicacion.isoformat(),
                "tipo": "MARCAS NUEVAS",
                "actas_encontradas": 0,
                "estado": "pendiente",
                "ultimo_error": None,
            }], "numero_boletin")

            pdf_bytes = requests.get(b["url"], timeout=60)
            pdf_bytes.raise_for_status()
            pdf_path = f"/tmp/{b['numero']}.pdf"
            txt_path = f"/tmp/{b['numero']}.txt"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes.content)
            subprocess.run(["pdftotext", "-layout", pdf_path, txt_path], timeout=60, check=True)

            actas = parse_boletin(txt_path)

            logos = extraer_logos(pdf_path)
            for acta in actas:
                if acta["tipo"] == "M" and acta["acta"] in logos:
                    acta["logo_phash"] = logos[acta["acta"]]["phash"]
                    acta["logo_dhash"] = logos[acta["acta"]]["dhash"]

            try:
                historico_rows = [{"acta": a["acta"], "clase": a["clase"], "tipo": a["tipo"], "denominacion": a["denominacion"] or None, "titulares": a["titulares"], "boletin_numero": b["numero"], "fecha_publicacion": fecha_publicacion.isoformat()} for a in actas if a.get("acta")]
                if historico_rows:
                    supabase_upsert("actas_historicas", historico_rows, "acta")
            except Exception as e:
                reportar_a_supabase(f"boletin {b['numero']} WARN actas_historicas upsert falló: {e}")

            alertas = buscar_coincidencias(cartera, actas, umbral=0.60, umbral_logo=0.75)

            fecha_limite = fecha_publicacion + timedelta(days=30)
            rows = []
            plazos_rows = []
            for al in alertas:
                score = al["similitud"]["score"]
                rows.append({
                    "marca_vigilada_id": al["marca_vigilada_id"],
                    "tipo_match": al["tipo_match"],
                    "acta_nueva": al["acta_nueva"],
                    "denominacion_nueva": al["denominacion_nueva"],
                    "clase": al["clase"],
                    "clase_acta": al.get("clase_acta", al["clase"]),
                    "relacion_clases": al.get("relacion_clases", "misma"),
                    "titular_nuevo": al["titular_nuevo"],
                    "boletin_numero": b["numero"],
                    "similitud_ortografica": al["similitud"]["ortografica"],
                    "similitud_fonetica": al["similitud"]["fonetica"],
                    "similitud_logo": score if al["tipo_match"] == "logo" else None,
                    "similitud_score": score,
                    "score_ajustado": al.get("score_ajustado", score),
                    "requiere_oposicion": al.get("requiere_oposicion", al["requiere_atencion"]),
                    "borrador_oposicion": al["borrador_oposicion"],
                    "fecha_publicacion": fecha_publicacion.isoformat(),
                    "fecha_limite_oposicion": fecha_limite.isoformat(),
                    "enlace_inpi": f"https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado?acta={al['acta_nueva']}",
                    "nivel_riesgo": al.get("nivel_riesgo", "alto" if score >= 0.85 else "medio" if score >= 0.72 else "bajo"),
                    "evidencia": [{
                        "metodo": al["tipo_match"], "score": score, "score_ajustado": al.get("score_ajustado", score),
                        "ortografica": al["similitud"]["ortografica"],
                        "fonetica": al["similitud"]["fonetica"],
                        "relacion_clases": al.get("relacion_clases", "misma"),
                    }],
                })
                
                if al["requiere_atencion"]:
                    titulo_plazo = f"Oposición a acta {al['acta_nueva']} ({al['denominacion_nueva'] or 'logo'})"
                    if not any(p["titulo"] == titulo_plazo for p in plazos_rows):
                        plazos_rows.append({
                            "marca_vigilada_id": al["marca_vigilada_id"],
                            "tipo": "oposicion",
                            "titulo": titulo_plazo,
                            "fecha_origen": fecha_publicacion.isoformat(),
                            "fecha_vencimiento": fecha_limite.isoformat(),
                            "estado": "pendiente",
                            "fuente": "automatica"
                        })

            # Upsert por clave de origen: seguro ante reintentos del mismo boletín.
            supabase_upsert("alertas", rows, "marca_vigilada_id,acta_nueva,boletin_numero")
            
            if plazos_rows:
                # Evitar duplicados ante reintentos consultando los plazos ya creados en esta fecha
                existentes = supabase_get("plazos_legales", f"select=titulo&fuente=eq.automatica&fecha_origen=eq.{fecha_publicacion.isoformat()}")
                titulos_existentes = {p["titulo"] for p in existentes}
                plazos_a_insertar = [p for p in plazos_rows if p["titulo"] not in titulos_existentes]
                if plazos_a_insertar:
                    supabase_insert("plazos_legales", plazos_a_insertar)
                    
            supabase_patch_boletin(b["numero"], {
                "actas_encontradas": len(actas), "estado": "completo",
                "ultimo_error": None, "actualizado_at": datetime.utcnow().isoformat() + "Z",
            })
            reportar_a_supabase(f"boletin {b['numero']} OK: {len(actas)} actas, {len(alertas)} alertas")
            procesados_esta_corrida += 1
            todas_las_alertas_fuertes.extend(al for al in alertas if al["similitud"]["score"] >= 0.85)
        except Exception as e:
            try:
                supabase_patch_boletin(b["numero"], {
                    "estado": "fallido", "ultimo_error": str(e)[:3500],
                    "actualizado_at": datetime.utcnow().isoformat() + "Z",
                })
            except Exception:
                pass
            reportar_a_supabase(f"boletin {b['numero']} FALLO, se reintentará: {e}")
            continue

    enviar_resumen(todas_las_alertas_fuertes, avisos_venc)
    reportar_a_supabase(f"OK: corrida completa, {procesados_esta_corrida} de {len(nuevos)} boletines procesados")


if __name__ == "__main__":
    reportar_a_supabase("heartbeat: arrancó el script")
    try:
        reportar_a_supabase("heartbeat: entrando a run()")
        run()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        reportar_a_supabase(tb)
        sys.exit(1)
