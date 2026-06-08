"""
Rayuela - capa de redaccion asistida (API de Claude).
"""

import os
import concurrent.futures
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta ANTHROPIC_API_KEY en las variables de entorno del backend."
            )
        _client = Anthropic(api_key=api_key)
    return _client


FORMULAS_REFERENCIA = [
    "El encuentro inicia con un saludo afectuoso a la familia, propiciando un ambiente de confianza y participacion.",
    "Posteriormente, se invita a la familia a...",
    "Para finalizar, se dialoga con la familia acerca de la importancia de...",
    "Como familia, nos gusto mucho...",
    "Como familia, notamos que...",
    "Nos comprometemos como familia a...",
]

VOCABULARIO_POR_BANDA = {
    "0-6m": (
        "estimulos sensoriales, reacciones del bebe (mirar, sonreir, sostener la cabeza, "
        "calmarse con la voz, balbucear), acompanamiento afectivo. EVITAR verbos de "
        "participacion activa o exploracion voluntaria."
    ),
    "6-11m": (
        "exploracion incipiente, desplazamiento (gatear, arrastrarse), busqueda de objetos, "
        "interes y curiosidad, balbuceo intencional."
    ),
    "1-2a": (
        "autonomia, toma de decisiones, coordinacion visomanual, manipulacion libre, "
        "confianza en sus capacidades, lenguaje en formacion."
    ),
    "3-4a": (
        "lenguaje y narracion, normas y convivencia, seguimiento de instrucciones, "
        "creatividad, juego simbolico, relacion con pares y familia."
    ),
}


def _prompt_sistema(banda_clave, banda_etiqueta, perspectiva="familia"):
    if perspectiva == "talento_humano":
        bloque_voz = (
            "Esta vez NO escribes como la familia. Escribes como Jimena misma, "
            "agente educativa, dando su analisis y reflexion PROFESIONAL sobre el encuentro "
            "o acompanamiento - en primera persona singular ('considero', 'observe', "
            "'para el proximo encuentro recomendaria...'). Es un texto analitico y reflexivo, "
            "de quien diseno y acompano la actividad, NO la opinion de la familia. "
            "Evita formulas de primera persona plural familiar como 'como familia, nos gusto...'."
        )
    elif perspectiva == "planeacion":
        bloque_voz = (
            "Estas escribiendo la PLANEACION del encuentro - no un reporte de lo que "
            "ocurrio, sino la descripcion de lo que SE HARA. El texto va en TERCERA PERSONA, "
            "en tiempo presente o futuro inmediato ('se propicia', 'se desarrolla', 'se invita "
            "a la familia', 'la agente educativa presentara'), describiendo lo que ocurrira "
            "durante el encuentro planificado. "
            "Usa el estilo formal y pedagogico del ICBF, calido pero profesional. "
            "NO uses primera persona. NO describas algo en pasado."
        )
    elif perspectiva == "desarrollo_infantil":
        bloque_voz = (
            "Esta vez escribes una descripcion NARRATIVA Y PROFESIONAL, en TERCERA PERSONA, "
            "sobre el proceso de desarrollo de la nina o el nino durante el mes - "
            "nombrandolo/a por su nombre de pila tal como te lo indiquen. "
            "Es un registro de observacion pedagogica. "
            "No es la voz de la familia ni la reflexion de Jimena sobre su propio quehacer: "
            "aqui ella describe AL NINO O A LA NINA."
        )
    else:
        formulas = "\n".join("- " + f for f in FORMULAS_REFERENCIA)
        bloque_voz = (
            "Escribes en la voz de la familia, en primera persona plural "
            "('nosotros como familia'), relatando su experiencia del encuentro o "
            "acompanamiento.\n\nEstilo de referencia:\n" + formulas
        )

    return (
        "Eres un asistente de redaccion para Jimena, agente educativa del programa "
        "de Educacion Inicial Campesina del ICBF, en una zona rural de Yacopi, Cundinamarca.\n\n"
        "Tu unica tarea es REDACTAR Y AMPLIAR en el formato y tono del ICBF lo que ella "
        "te entrega en bruto. NO inventes actividades, materiales ni observaciones que ella "
        "no haya mencionado - solo dales forma narrativa profesional y calida.\n\n"
        "El nino/nina de este registro esta en la banda de desarrollo: " + banda_etiqueta + ".\n"
        "Vocabulario y enfoque apropiados para esta banda: " + VOCABULARIO_POR_BANDA[banda_clave] + "\n\n"
        + bloque_voz + "\n\n"
        "Reglas estrictas:\n"
        "- Nunca uses lenguaje impropio para la edad.\n"
        "- Texto en espanol de Colombia, calido pero formal, en parrafos (no listas).\n"
        "- No agregues firmas, encabezados ni metadatos - solo el texto solicitado.\n"
    )


def redactar(banda_clave, banda_etiqueta, instruccion, materia_prima,
             perspectiva="familia", max_palabras=110):
    """Llama a Claude para redactar un bloque de texto del cuaderno ICBF."""
    client = _get_client()
    texto_usuario = (
        "Necesito que redactes lo siguiente: " + instruccion + "\n\n"
        "Esto es lo que escribi yo (Jimena), tal cual, sin pulir:\n"
        "'''\n" + materia_prima.strip() + "\n'''\n\n"
        "Redactalo en el tono y formato indicados, ampliandolo lo necesario "
        "para que quede como un parrafo completo del documento oficial. "
        "IMPORTANTE: el espacio del documento es limitado - el parrafo "
        "completo NO debe superar aproximadamente " + str(max_palabras) + " palabras "
        "(prefiero que sea conciso y completo a que sea largo y se corte)."
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=_prompt_sistema(banda_clave, banda_etiqueta, perspectiva),
        messages=[{"role": "user", "content": texto_usuario}],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()


# -----------------------------------------------------------------------------
# MODULO DE PLANEACION
# -----------------------------------------------------------------------------

_GUIA_MOMENTO_UNO = (
    "Al llegar al hogar, se brinda un saludo cordial a la familia y se favorece "
    "un ambiente de confianza. Se organiza un espacio comodo, seguro y libre de "
    "distractores. Se propicia un momento de interaccion afectiva con el/la nino/a/bebe "
    "para favorecer el vinculo y la disposicion de participar. La actividad se "
    "complementa con la ronda infantil indicada, incluyendo su nombre y enlace."
)

_GUIA_MOMENTO_DOS = (
    "Se desarrollan experiencias pedagogicas significativas, dinamicas, recreativas y "
    "participativas, orientadas al fortalecimiento de habilidades mediante el juego, "
    "el arte, la literatura o la exploracion del medio, pertinentes para la edad, nivel "
    "de desarrollo y contexto familiar del participante."
)

_GUIA_MOMENTO_TRES = (
    "Se dialoga con la familia acerca de la importancia de dar continuidad a los "
    "aprendizajes en el hogar. Se resaltan los beneficios de las actividades realizadas "
    "y se acuerda implementar en la cotidianidad acciones relacionadas con la experiencia, "
    "favoreciendo espacios de interaccion, juego, exploracion y afecto."
)


def generar_textos_planeacion(tipo, actividad, nombre_nino, banda_clave,
                               banda_etiqueta, nombre_ronda="", link_ronda=""):
    """
    Genera en paralelo todos los textos del documento de planeacion.

    Para 'hogar': intencionalidad, experiencias_momento_uno/dos/tres
    Para 'llamada': intencionalidad, descripcion_experiencia, tiempo_recursos
    """
    primer_nombre = nombre_nino.strip().split()[0].title()
    info_base = (
        "Actividad planeada: " + actividad + "\n"
        "Participante: " + primer_nombre + " (banda de edad: " + banda_etiqueta + ")"
    )

    if tipo == "hogar":
        info_m1 = info_base
        if nombre_ronda:
            info_m1 += "\nRonda infantil: " + nombre_ronda
        if link_ronda:
            info_m1 += "\nEnlace de la ronda: " + link_ronda

        trabajos = [
            ("intencionalidad", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion=(
                    "la intencionalidad pedagogica de este encuentro: que habilidades, "
                    "capacidades, vinculos o aprendizajes se busca fortalecer con esta "
                    "actividad. Maximo 2 oraciones concisas."
                ),
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=50,
            )),
            ("experiencias_momento_uno", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion="el texto del 'Momento uno: conectarnos'. Debe incluir: " + _GUIA_MOMENTO_UNO,
                materia_prima=info_m1,
                perspectiva="planeacion",
                max_palabras=110,
            )),
            ("experiencias_momento_dos", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion="el texto del 'Momento dos: construyendo juntos'. Debe incluir: " + _GUIA_MOMENTO_DOS,
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=120,
            )),
            ("experiencias_momento_tres", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion="el texto del 'Momento tres: comprometernos'. Debe incluir: " + _GUIA_MOMENTO_TRES,
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=100,
            )),
        ]

    else:  # llamada
        trabajos = [
            ("intencionalidad", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion=(
                    "la intencionalidad pedagogica del acompanamiento a distancia: "
                    "que habilidades o aprendizajes se busca fortalecer. Maximo 2 oraciones."
                ),
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=50,
            )),
            ("descripcion_experiencia", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion=(
                    "la descripcion de la experiencia pedagogica a promover con la familia "
                    "en el acompanamiento a distancia: como se desarrollara la actividad, "
                    "que hara la familia, que explorara el/la nino/a/bebe, "
                    "y como participara cada integrante."
                ),
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=130,
            )),
            ("tiempo_recursos", dict(
                banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
                instruccion=(
                    "el tiempo estimado y los recursos necesarios para esta actividad: "
                    "duracion aproximada de cada momento y materiales o herramientas "
                    "que necesita la familia."
                ),
                materia_prima=info_base,
                perspectiva="planeacion",
                max_palabras=70,
            )),
        ]

    resultados = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(trabajos)) as fondo:
        futuros = {
            fondo.submit(redactar, **kwargs): clave
            for clave, kwargs in trabajos
        }
        for futuro in concurrent.futures.as_completed(futuros):
            clave = futuros[futuro]
            resultados[clave] = futuro.result()

    return resultados
