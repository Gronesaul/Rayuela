"""
Rayuela — backend principal (Flask).

Flujo que implementa (módulo "voces", el primero — ya validado a fondo con
los 34 cuadernos reales de Jimena):

  1. Jimena manda: nombre del niño, fecha de nacimiento, sexo, tipo de
     cuaderno (hogar/llamada), actividad realizada, y sus observaciones
     en bruto.
  2. El backend calcula la banda de edad (no depende de que Jimena la
     recuerde — elimina justo el tipo de error que detectamos: "a Hassan
     le puso bebé y es un niño de un año").
  3. Llama a la API de Claude (capa `redactor`) para redactar cada
     respuesta en primera persona familiar, con el vocabulario correcto
     para esa banda de edad.
  4. Inserta el texto en una copia del molde .pptx oficial (capa
     `plantilla_pptx`) y entrega el archivo final.

Variables de entorno esperadas (configurar en Railway):
  ANTHROPIC_API_KEY   -> la llave de la API (la pone Alexander)
  RAYUELA_TEMPLATE_DIR -> carpeta donde están los moldes .pptx oficiales
"""

import os
import io
import uuid
from datetime import datetime

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pptx import Presentation

from . import edades
from . import redactor
from . import plantilla_pptx

app = Flask(__name__)
CORS(app)  # permite que el frontend (Netlify) llame a este backend (Railway)

TEMPLATE_DIR = os.environ.get("RAYUELA_TEMPLATE_DIR", os.path.join(
    os.path.dirname(__file__), "..", "templates"))

# Preguntas de "voces de la familia" tal como aparecen en los moldes reales del ICBF
PREGUNTAS_HOGAR = [
    "Qué les gustó y que no del encuentro",
    "sugerencias tiene la familia",
    "Lo que aprendieron de este encuentro",
    "Compromisos para el próximo encuentro",
]

PREGUNTAS_LLAMADA = [
    "Qué les gustó y que no de los acompañamientos a distancia",
    "Para qué le sirvieron los acompañamientos a distancia",
    "Cómo participó la niña, el niño o mujer gestante",
    "Qué le gustaría vivir en los próximos acompañamientos a distancia",
]

SLIDE_FAMILIA = {"hogar": 2, "llamada": 4}

# Preguntas de "voces del talento humano del servicio" (la reflexión de Jimena
# como agente educativa, NO la voz de la familia). En el molde de hogar son 5
# preguntas; en el de llamada el molde oficial solo trae 2.
PREGUNTAS_TALENTO_HOGAR = [
    "Considera que se alcanzó la intencionalidad del encuentro",
    "Cuál fue el mejor momento del encuentro",
    "Cómo participó la familia",
    "Qué recomendaciones harían para el próximo encuentro",
    "Cómo se aprovecharon los materiales propuestos",
]

PREGUNTAS_TALENTO_LLAMADA = [
    "Se cumplieron las intencionalidades propuestas",
    "Describa cómo fue la participación de la familia en el acompañamiento",
]

SLIDE_TALENTO = {"hogar": 3, "llamada": 5}


@app.get("/api/salud")
def salud():
    return jsonify({"estado": "ok", "app": "Rayuela", "hora": datetime.now().isoformat()})


@app.post("/api/calcular-edad")
def calcular_edad():
    """Utilidad para que el frontend muestre la banda de edad en vivo, sin que
    Jimena tenga que calcularla ni recordarla."""
    datos = request.get_json(force=True)
    try:
        nacimiento = datetime.strptime(datos["fecha_nacimiento"], "%Y-%m-%d").date()
    except (KeyError, ValueError):
        return jsonify({"error": "fecha_nacimiento inválida, use AAAA-MM-DD"}), 400

    meses = edades.edad_en_meses(nacimiento)
    banda = edades.banda_por_edad(meses)
    genero = datos.get("genero", "M")
    sust = edades.sustantivo(genero, banda["clave"])
    return jsonify({
        "edad_meses": meses,
        "edad_legible": edades.formato_legible(meses),
        "banda": banda,
        "sustantivo": sust,
    })


@app.post("/api/generar-voces")
def generar_voces():
    """
    Genera el documento de 'voces de familia' ya diligenciado.

    Cuerpo esperado (JSON):
    {
      "nombre": "Hassan Melo Hueso",
      "fecha_nacimiento": "2024-09-09",
      "genero": "M",
      "tipo_cuaderno": "hogar" | "llamada",
      "actividad": "exploración sensorial con texturas",
      "observaciones": "le gustó tocar las telas, se rio mucho, ..."
    }
    """
    datos = request.get_json(force=True)
    requeridos = ["nombre", "fecha_nacimiento", "genero", "tipo_cuaderno",
                  "actividad", "observaciones"]
    faltantes = [c for c in requeridos if not datos.get(c)]
    if faltantes:
        return jsonify({"error": f"faltan campos: {', '.join(faltantes)}"}), 400

    tipo = datos["tipo_cuaderno"].strip().lower()
    if tipo not in SLIDE_FAMILIA:
        return jsonify({"error": "tipo_cuaderno debe ser 'hogar' o 'llamada'"}), 400

    try:
        nacimiento = datetime.strptime(datos["fecha_nacimiento"], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "fecha_nacimiento inválida, use AAAA-MM-DD"}), 400

    # 1. Calculamos la banda de edad — sin depender de la memoria de Jimena
    meses = edades.edad_en_meses(nacimiento)
    banda = edades.banda_por_edad(meses)

    # 2. Redactamos cada respuesta con la API de Claude, en el tono correcto
    preguntas = PREGUNTAS_HOGAR if tipo == "hogar" else PREGUNTAS_LLAMADA
    materia_prima = (
        f"Actividad realizada: {datos['actividad']}\n"
        f"Lo que observé / lo que pasó: {datos['observaciones']}"
    )

    instrucciones = {
        preguntas[0]: "la respuesta de la familia en primera persona ('nosotros como "
                      "familia') sobre qué les gustó y qué no del encuentro/acompañamiento",
        preguntas[1]: "la respuesta de la familia en primera persona sobre sugerencias "
                      "para próximas experiencias",
        preguntas[2]: "la respuesta de la familia en primera persona sobre lo que "
                      "aprendieron de este encuentro/acompañamiento",
        preguntas[3]: "la respuesta de la familia en primera persona sobre los "
                      "compromisos para el próximo encuentro",
    }

    mapa_textos = {}
    for pregunta in preguntas:
        mapa_textos[pregunta] = redactor.redactar(
            banda_clave=banda["clave"],
            banda_etiqueta=banda["etiqueta"],
            instruccion=instrucciones[pregunta],
            materia_prima=materia_prima,
        )

    # 2b. Redactamos también las "voces del talento humano del servicio"
    # (la reflexión profesional de Jimena como agente educativa — tono
    # analítico, en primera persona singular, NO la voz de la familia).
    preguntas_talento = (PREGUNTAS_TALENTO_HOGAR if tipo == "hogar"
                         else PREGUNTAS_TALENTO_LLAMADA)

    instrucciones_talento = {
        preguntas_talento[0]: "mi reflexión como agente educativa, en primera persona "
                              "singular ('considero', 'observé'), sobre si se alcanzó "
                              "la intencionalidad pedagógica propuesta para este "
                              "encuentro/acompañamiento, con base en lo que ocurrió",
        preguntas_talento[1]: "mi reflexión como agente educativa, en primera persona "
                              "singular, sobre cuál fue el mejor momento del encuentro/"
                              "acompañamiento y por qué, desde mi mirada profesional",
    }
    if tipo == "hogar":
        instrucciones_talento.update({
            preguntas_talento[2]: "mi análisis como agente educativa, en primera "
                                  "persona singular, sobre cómo participó la familia "
                                  "y quiénes participaron en el encuentro",
            preguntas_talento[3]: "mis recomendaciones profesionales, en primera "
                                  "persona singular, para tener en cuenta en el "
                                  "próximo encuentro",
            preguntas_talento[4]: "mi valoración como agente educativa, en primera "
                                  "persona singular, sobre cómo se aprovecharon los "
                                  "materiales propuestos durante el encuentro",
        })
    else:
        instrucciones_talento[preguntas_talento[1]] = (
            "mi descripción y análisis, como agente educativa y en primera persona "
            "singular, de cómo fue la participación de la familia durante el "
            "acompañamiento a distancia"
        )

    mapa_textos_talento = {}
    for pregunta in preguntas_talento:
        mapa_textos_talento[pregunta] = redactor.redactar(
            banda_clave=banda["clave"],
            banda_etiqueta=banda["etiqueta"],
            instruccion=instrucciones_talento[pregunta],
            materia_prima=materia_prima,
            perspectiva="talento_humano",
        )

    # 3. Insertamos el texto en una copia del molde oficial
    molde_path = os.path.join(TEMPLATE_DIR, f"molde_{tipo}.pptx")
    if not os.path.exists(molde_path):
        return jsonify({"error": f"no se encontró el molde oficial: molde_{tipo}.pptx "
                                 f"(colóquelo en {TEMPLATE_DIR})"}), 500

    prs = Presentation(molde_path)
    slide = prs.slides[SLIDE_FAMILIA[tipo]]
    reporte = plantilla_pptx.llenar_respuestas(slide, mapa_textos)

    slide_talento = prs.slides[SLIDE_TALENTO[tipo]]
    reporte_talento = plantilla_pptx.llenar_respuestas(slide_talento, mapa_textos_talento)
    reporte.update({f"[talento] {k}": v for k, v in reporte_talento.items()})

    # 4. Entregamos el archivo
    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"{datos['nombre'].strip().upper()} - voces - {uuid.uuid4().hex[:6]}.pptx"
    respuesta = send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    respuesta.headers["X-Rayuela-Banda"] = banda["clave"]
    respuesta.headers["X-Rayuela-Reporte"] = str(reporte)
    return respuesta


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
