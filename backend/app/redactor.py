"""
Rayuela - capa de redaccion asistida (API de Claude).
"""

import os
import re
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
    "gestante": (
        "vinculo afectivo prenatal, lenguaje calido dirigido al bebe en gestacion, "
        "bienestar emocional y fisico de la madre, participacion activa de la familia "
        "en el acompanamiento, fortalecimiento del vinculo materno-filial antes del "
        "nacimiento, preparacion para la llegada del bebe."
    ),
}


def _reemplazar_actividad(texto):
    """
    Filtro de seguridad: en los documentos de llamada la palabra 'actividad'
    (o 'actividades') no debe aparecer nunca - se reemplaza por 'experiencia'
    o 'experiencias', preservando mayusculas/minusculas del original.
    """
    def _reemplazo(m):
        original = m.group(0)
        es_plural = original.lower().endswith("des")
        nueva = "experiencias" if es_plural else "experiencia"
        if original.isupper():
            return nueva.upper()
        if original[0].isupper():
            return nueva.capitalize()
        return nueva

    return re.sub(r"\bactividad(es)?\b", _reemplazo, texto, flags=re.IGNORECASE)


def _prompt_sistema(banda_clave, banda_etiqueta, perspectiva="familia"):
    if perspectiva == "talento_humano":
        bloque_voz = (
            "Esta vez NO escribes como la familia. Escribes como Jimena misma, "
            "agente educativa, dando su analisis y reflexion PROFESIONAL sobre el encuentro "
            "o acompanamiento - en primera persona singular ('considero', 'observe', "
            "'para el proximo encuentro recomendaria...'). Es un texto analitico y reflexivo, "
            "de quien diseno y acompano la experiencia, NO la opinion de la familia. "
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
            "NO uses primera persona. NO describas algo en pasado. "
            "PROHIBIDO usar la palabra 'actividad' o 'actividades' en cualquier forma - "
            "usa siempre 'experiencia' o 'experiencia pedagogica' en su lugar."
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
            "acompanamiento. Que se sienta como una sola voz natural, sencilla y calida, "
            "sin sonar repetitiva ni formal en exceso.\n\n"
            "Estilo de referencia:\n" + formulas
        )

    return (
        "Eres un asistente de redaccion para Jimena, agente educativa del programa "
        "de Educacion Inicial Campesina del ICBF, en una zona rural de Yacopi, Cundinamarca.\n\n"
        "Tu unica tarea es REDACTAR Y AMPLIAR en el formato y tono del ICBF lo que ella "
        "te entrega en bruto. NO inventes actividades, materiales ni observaciones que ella "
        "no haya mencionado - solo dales forma narrativa profesional y calida.\n\n"
        "El participante de este registro esta en la banda: " + banda_etiqueta + ".\n"
        "Vocabulario y enfoque apropiados para esta banda: " + VOCABULARIO_POR_BANDA[banda_clave] + "\n\n"
        + bloque_voz + "\n\n"
        "Reglas estrictas:\n"
        "- Nunca uses lenguaje impropio para la edad.\n"
        "- Texto en espanol de Colombia, calido pero formal, en parrafos (no listas).\n"
        "- No agregues firmas, encabezados ni metadatos - solo el texto solicitado.\n"
    )


def redactar(banda_clave, banda_etiqueta, instruccion, materia_prima,
             perspectiva="familia", max_palabras=110, evitar_actividad=False):
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
    texto = "".join(block.text for block in msg.content if block.type == "text").strip()
    if evitar_actividad:
        texto = _reemplazar_actividad(texto)
    return texto


# -----------------------------------------------------------------------------
# MODULO DE PLANEACION - ENCUENTRO EN EL HOGAR
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


def generar_textos_planeacion(actividad, nombre_nino, banda_clave,
                               banda_etiqueta, nombre_ronda="", link_ronda=""):
    """
    Genera en paralelo los textos del documento de planeacion para 'hogar':
    intencionalidad, experiencias_momento_uno/dos/tres.

    (El modulo de 'llamada' usa generar_textos_planeacion_llamada, mas abajo,
    porque su estructura - dos planeaciones independientes - es distinta.)
    """
    primer_nombre = nombre_nino.strip().split()[0].title()
    info_base = (
        "Actividad planeada: " + actividad + "\n"
        "Participante: " + primer_nombre + " (banda de edad: " + banda_etiqueta + ")"
    )

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


# -----------------------------------------------------------------------------
# MODULO DE PLANEACION - ACOMPANAMIENTO POR LLAMADA (dos planeaciones)
# -----------------------------------------------------------------------------

_TEXTO_INTRO_TIEMPO_RECURSOS = (
    "Tiempo estimado: 10 minutos.\nRecursos: Talento humano, Familia, Telefono."
)


def _etiqueta_participante(tipo_participante, genero):
    """Devuelve como nombrar al participante en los textos fijos/prompts."""
    if tipo_participante == "gestante":
        return "la mujer gestante"
    if tipo_participante == "bebe":
        return "la bebe" if genero == "F" else "el bebe"
    if tipo_participante == "nina":
        return "la nina"
    return "el nino"


def _texto_intro_familia(nombre_cancion, link_cancion, etiqueta_participante):
    """
    Texto FIJO (sin IA) de la 'Experiencia pedagogica a promover con la familia':
    solo varian el nombre de la cancion, el enlace y el tipo de participante.
    """
    nombre_cancion = (nombre_cancion or "").strip()
    link_cancion = (link_cancion or "").strip()
    if nombre_cancion:
        cancion_txt = "la cancion \"" + nombre_cancion + "\""
        if link_cancion:
            cancion_txt += " (disponible en: " + link_cancion + ")"
    else:
        cancion_txt = "una cancion infantil"

    return (
        "Se inicia el acompanamiento telefonico con un saludo afectuoso a la familia, "
        "propiciando un ambiente de confianza y disposicion para participar. Se invita "
        "a la familia a escuchar y disfrutar junto a " + etiqueta_participante + " "
        + cancion_txt + ", favoreciendo un momento de conexion, alegria y vinculo "
        "afectivo antes de iniciar la experiencia pedagogica principal."
    )


def _dividir_materiales(texto):
    """Convierte el texto libre de materiales (p. ej. 'peluches, telas y semillas')
    en una lista de items individuales, uno por linea — para el formato breve
    de 'Tiempo estimado y recursos' que pidio Jimena (ver
    _texto_tiempo_recursos_principal)."""
    texto = (texto or "").strip()
    if not texto:
        return []
    partes = re.split(r",|;|/|\by\b", texto)
    return [p.strip().capitalize() for p in partes if p.strip()]


def _estimar_minutos(tema, banda_etiqueta):
    """Le pide a la IA UNICAMENTE un numero de minutos (nada de redaccion),
    para el campo breve 'Tiempo estimado y recursos' de la experiencia
    pedagogica principal (ver _texto_tiempo_recursos_principal). Si la
    respuesta no trae un numero reconocible, o falla la llamada, usa 15
    minutos por defecto."""
    try:
        client = _get_client()
        msg = client.messages.create(
            model=MODEL,
            max_tokens=10,
            system=(
                "Respondes UNICAMENTE con un numero entero de minutos (sin la "
                "palabra 'minutos', sin texto adicional, sin explicacion) que "
                "consideres razonable para desarrollar la siguiente experiencia "
                "pedagogica con un participante en banda de desarrollo: "
                + banda_etiqueta + "."
            ),
            messages=[{"role": "user", "content": "Experiencia: " + tema}],
        )
        texto = "".join(b.text for b in msg.content if b.type == "text").strip()
        numero = re.search(r"\d+", texto)
        return numero.group(0) if numero else "15"
    except Exception:
        return "15"


def _texto_tiempo_recursos_principal(minutos, materiales):
    """
    Formato breve, tipo lista (no parrafo), para 'Tiempo estimado y recursos'
    de la experiencia pedagogica PRINCIPAL.

    Jimena reporto que este campo, cuando la IA lo redactaba como parrafo,
    "detalla mucho": ella solo necesita algo como

        Talento humano
        15 minutos
        Aros
        Pelotas

    y que mencione los materiales REALMENTE usados en esa experiencia (no que
    la IA los resuma, omita o invente). Por eso este campo ya NO lo redacta la
    IA en texto libre: se construye en Python a partir de los materiales que
    Jimena registro para esta experiencia especifica (ver materiales_por_n en
    generar_textos_planeacion_llamada). La IA solo decide el numero de
    minutos (ver _estimar_minutos) — nunca la redaccion ni la lista.
    """
    lineas = ["Talento humano", str(minutos) + " minutos"]
    lineas.extend(_dividir_materiales(materiales))
    return "\n".join(lineas)


def generar_textos_planeacion_llamada(
    tema_1, tema_2, nombre_participante, tipo_participante, genero,
    banda_clave, banda_etiqueta,
    nombre_cancion_1="", link_cancion_1="", nombre_cancion_2="", link_cancion_2="",
    modalidad_acompanamiento="Llamada telefonica",
    materiales_disponibles_1="", materiales_disponibles_2="", aspectos_fortalecer="",
):
    """
    Genera los textos de las DOS planeaciones del acompanamiento por llamada.

    Cada planeacion (1 y 2) tiene su propia:
      - intencionalidad (un solo verbo principal, minimo tres lineas)
      - experiencia pedagogica principal: descripcion + tiempo y recursos
      - materiales_disponibles (ver mas abajo)

    La 'experiencia pedagogica a promover con la familia' (el saludo + cancion
    inicial) es texto FIJO, generado por plantilla en Python (no llama a la IA),
    para que solo varien el nombre de la cancion, el enlace y el participante.

    IMPORTANTE sobre materiales_disponibles_1/2: antes existia un solo
    parametro "materiales_disponibles" compartido entre las dos planeaciones,
    y la IA decidia por su cuenta, para cada tema, si lo mencionaba o no.
    Eso producia inconsistencias como la que reporto Jimena: la pagina 4
    (planeacion 2) decia "no se utilizaron materiales" cuando en la pagina 1
    (planeacion 1) si se habian registrado y usado peluches. Ahora cada
    planeacion recibe SOLO su propia lista de materiales, y si esta vacia se
    le dice explicitamente a la IA que no invente ni mencione materiales para
    esa experiencia en particular.

    IMPORTANTE sobre 'Tiempo estimado y recursos' de la experiencia PRINCIPAL:
    Jimena tambien reporto que este campo, redactado por la IA como parrafo,
    quedaba demasiado detallado para lo que necesita (ver
    _texto_tiempo_recursos_principal). Por eso ya NO se redacta como texto
    libre: se arma como una lista breve (Talento humano / minutos /
    materiales) usando los materiales reales de esa experiencia y un numero
    de minutos que la IA solo estima, sin redactar nada mas.
    """
    primer_nombre = nombre_participante.strip().split()[0].title() if nombre_participante.strip() else ""
    etiqueta = _etiqueta_participante(tipo_participante, genero)

    info_extra_comun = "\nModalidad de acompanamiento: " + modalidad_acompanamiento
    if aspectos_fortalecer.strip():
        info_extra_comun += "\nAspectos especificos a fortalecer: " + aspectos_fortalecer.strip()

    materiales_por_n = {"1": materiales_disponibles_1, "2": materiales_disponibles_2}

    def _info(tema, n):
        base = "Tema o experiencia priorizada: " + tema + "\nParticipante: " + (primer_nombre or etiqueta)
        if tipo_participante == "gestante":
            base += " (mujer gestante)"
        else:
            base += " (banda de desarrollo: " + banda_etiqueta + ")"
        base += info_extra_comun
        materiales = materiales_por_n.get(n, "").strip()
        if materiales:
            base += "\nMateriales disponibles en el hogar para ESTA experiencia: " + materiales
        else:
            base += ("\nNo se registraron materiales adicionales del paquete didactico "
                     "para ESTA experiencia especifica: no menciones materiales usados.")
        return base

    trabajos = []
    for n, tema in [("1", tema_1), ("2", tema_2)]:
        trabajos.append(("intencionalidad_" + n, dict(
            banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
            instruccion=(
                "la intencionalidad pedagogica de esta experiencia del acompanamiento "
                "telefonico. Debe ser UNA SOLA ORACION construida alrededor de UN UNICO "
                "VERBO PRINCIPAL (no enumeres varias acciones con verbos distintos); "
                "extiendela con complementos, conectores y clausulas explicativas para "
                "que sea una oracion completa y desarrollada, de minimo tres lineas de "
                "extension en una caja de texto pequena (no la fragmentes en varias "
                "oraciones cortas)."
            ),
            materia_prima=_info(tema, n),
            perspectiva="planeacion",
            max_palabras=55,
            evitar_actividad=True,
        )))
        trabajos.append(("experiencia_principal_descripcion_" + n, dict(
            banda_clave=banda_clave, banda_etiqueta=banda_etiqueta,
            instruccion=(
                "la descripcion completa de la EXPERIENCIA PEDAGOGICA PRINCIPAL de este "
                "acompanamiento telefonico: como se desarrolla paso a paso, que orienta "
                "la agente educativa por telefono, que hace la familia, y que explora o "
                "vivencia " + etiqueta + "."
            ),
            materia_prima=_info(tema, n),
            perspectiva="planeacion",
            max_palabras=140,
            evitar_actividad=True,
        )))

    resultados = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(trabajos) + 2) as fondo:
        futuros = {
            fondo.submit(redactar, **kwargs): clave
            for clave, kwargs in trabajos
        }
        futuros_minutos = {
            fondo.submit(_estimar_minutos, tema, banda_etiqueta): n
            for n, tema in [("1", tema_1), ("2", tema_2)]
        }
        for futuro in concurrent.futures.as_completed(futuros):
            clave = futuros[futuro]
            resultados[clave] = futuro.result()
        minutos_por_n = {}
        for futuro in concurrent.futures.as_completed(futuros_minutos):
            n = futuros_minutos[futuro]
            minutos_por_n[n] = futuro.result()

    for n in ("1", "2"):
        resultados["experiencia_principal_tiempo_recursos_" + n] = _texto_tiempo_recursos_principal(
            minutos_por_n.get(n, "15"), materiales_por_n.get(n, "")
        )

    resultados["intro_descripcion_1"] = _texto_intro_familia(nombre_cancion_1, link_cancion_1, etiqueta)
    resultados["intro_descripcion_2"] = _texto_intro_familia(nombre_cancion_2, link_cancion_2, etiqueta)
    resultados["intro_tiempo_recursos"] = _TEXTO_INTRO_TIEMPO_RECURSOS

    return resultados
