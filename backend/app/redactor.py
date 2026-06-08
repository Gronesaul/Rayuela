"""
Rayuela — capa de redacción asistida (API de Claude).

PRINCIPIO DE DISEÑO (no negociable, viene de la lección aprendida con los 34
cuadernos de Jimena): la IA NO inventa la actividad ni la observación. Solo
amplía y redacta en el tono/formato del ICBF lo que Jimena ya escribió en
bruto. El insumo real siempre viene de ella; Claude multiplica su tiempo,
no reemplaza su criterio.

Esto también evita el error de fondo que detectamos: texto genérico que no
encaja con la edad real del niño (p. ej. "participó activamente" en un bebé
de 2 meses).
"""

import os
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


# Banco de estilo: fórmulas reales tomadas de las planeaciones y voces de Jimena.
# Esto es lo que hace que el resultado "suene a ella" y no a un genérico de internet.
FORMULAS_REFERENCIA = [
    "El encuentro inicia con un saludo afectuoso a la familia, propiciando un ambiente de confianza y participación.",
    "Posteriormente, se invita a la familia a...",
    "Para finalizar, se dialoga con la familia acerca de la importancia de...",
    "Como familia, nos gustó mucho...",
    "Como familia, notamos que...",
    "Nos comprometemos como familia a...",
]

VOCABULARIO_POR_BANDA = {
    "0-6m": "estímulos sensoriales, reacciones del bebé (mirar, sonreír, sostener la cabeza, "
            "calmarse con la voz, balbucear), acompañamiento afectivo. EVITAR verbos de "
            "participación activa o exploración voluntaria (el bebé de esta edad reacciona, no "
            "decide ni explora a propósito).",
    "6-11m": "exploración incipiente, desplazamiento (gatear, arrastrarse), búsqueda de objetos, "
             "interés y curiosidad, balbuceo intencional. Aquí SÍ es válido decir que el bebé "
             "'participó', 'se interesó' o 'exploró'.",
    "1-2a": "autonomía, toma de decisiones, coordinación visomanual, manipulación libre, "
            "confianza en sus capacidades, lenguaje en formación.",
    "3-4a": "lenguaje y narración, normas y convivencia, seguimiento de instrucciones, "
            "creatividad, juego simbólico, relación con pares y familia.",
}


def _prompt_sistema(banda_clave: str, banda_etiqueta: str, perspectiva: str = "familia") -> str:
    if perspectiva == "talento_humano":
        bloque_voz = """Esta vez NO escribes como la familia. Escribes como Jimena misma,
agente educativa, dando su análisis y reflexión PROFESIONAL sobre el encuentro
o acompañamiento — en primera persona singular ("considero", "observé", "para
el próximo encuentro recomendaría..."). Es un texto analítico y reflexivo, de
quien diseñó y acompañó la actividad, NO la opinión de la familia.

Evita fórmulas de primera persona plural familiar como "como familia, nos
gustó..." — esas son para la sección de voces de la familia, no para esta."""
    else:
        bloque_voz = f"""Escribes en la voz de la familia, en primera persona plural
("nosotros como familia"), relatando su experiencia del encuentro o
acompañamiento.

Estilo de referencia (imita estas fórmulas y este tono, no las copies literalmente):
{chr(10).join('- ' + f for f in FORMULAS_REFERENCIA)}"""

    return f"""Eres un asistente de redacción para Jimena, agente educativa del programa
de Educación Inicial Campesina del ICBF, en una zona rural de Yacopí, Cundinamarca.

Tu única tarea es REDACTAR Y AMPLIAR en el formato y tono del ICBF lo que ella
te entrega en bruto (ideas sueltas, observaciones, bullets). NO inventes
actividades, materiales ni observaciones que ella no haya mencionado — solo
dales forma narrativa profesional y cálida.

El niño/niña de este registro está en la banda de desarrollo: {banda_etiqueta}.
Vocabulario y enfoque apropiados para esta banda: {VOCABULARIO_POR_BANDA[banda_clave]}

{bloque_voz}

Reglas estrictas:
- Nunca uses lenguaje impropio para la edad (p. ej. "participó activamente" para un bebé de 0-6 meses).
- Texto en español de Colombia, cálido pero formal, en párrafos (no listas) salvo que se pida lo contrario.
- No agregues firmas, encabezados ni metadatos — solo el texto solicitado.
"""


def redactar(banda_clave: str, banda_etiqueta: str, instruccion: str, materia_prima: str,
             perspectiva: str = "familia", max_palabras: int = 110) -> str:
    """
    Llama a la API de Claude para redactar un bloque de texto.

    `instruccion`: qué se necesita redactar (p.ej. "la intencionalidad pedagógica")
    `materia_prima`: lo que Jimena escribió en bruto sobre ese punto
    `perspectiva`: "familia" (voz de la familia, primera persona plural) o
                   "talento_humano" (reflexión de Jimena como educadora, primera
                   persona singular)
    `max_palabras`: tope aproximado de extensión del párrafo. Los cuadros de
                    "voces del talento humano" son más pequeños (caben 5
                    preguntas en el mismo espacio donde la familia solo tiene
                    4), así que ahí pedimos un texto más corto para que quepa
                    sin desbordarse — en vez de confiar en que PowerPoint
                    encoja la letra solo (no lo hace en archivos generados
                    por programa, solo cuando alguien edita el cuadro a mano).
    """
    client = _get_client()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=_prompt_sistema(banda_clave, banda_etiqueta, perspectiva),
        messages=[{
            "role": "user",
            "content": (
                f"Necesito que redactes lo siguiente: {instruccion}\n\n"
                f"Esto es lo que escribí yo (Jimena), tal cual, sin pulir:\n"
                f"\"\"\"\n{materia_prima.strip()}\n\"\"\"\n\n"
                f"Redáctalo en el tono y formato indicados, ampliándolo lo necesario "
                f"para que quede como un párrafo completo del documento oficial. "
                f"IMPORTANTE: el espacio del documento es limitado — el párrafo "
                f"completo NO debe superar aproximadamente {max_palabras} palabras "
                f"(prefiero que sea conciso y completo a que sea largo y se corte)."
            ),
        }],
    )
    return "".join(block.text for block in msg.content if block.type == "text").strip()
