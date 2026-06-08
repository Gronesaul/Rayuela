"""
Rayuela — motor de plantillas PPTX.

NO genera PowerPoints desde cero: abre una COPIA del molde oficial del ICBF
(la misma plantilla que Jimena ya usa y tiene aprobada) y reemplaza únicamente
el texto dentro de los contenedores de respuesta correctos, dejando intactos
diseño, fuentes, colores, logos y posiciones.

Esta es exactamente la técnica que validamos y usamos para corregir y
completar los 34 cuadernos reales de Jimena (ver find_question /
find_answer_table / write_answer del proyecto original).
"""

from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE

TAG = ""
TEXT_COLOR = RGBColor(0x00, 0x00, 0x00)


def find_question(slide, contains):
    """Busca el cuadro de texto de una pregunta por una subcadena de su texto."""
    contains_low = contains.lower()
    for shape in slide.shapes:
        if shape.has_text_frame and contains_low in shape.text_frame.text.lower():
            return shape
    return None


def _bbox(shape):
    return (shape.left, shape.top, shape.left + shape.width, shape.top + shape.height)


def find_answer_table(slide, qshape, tol=0.35):
    """
    Encuentra el contenedor de respuesta espacialmente más cercano/alineado
    con la pregunta dada (tabla 1x1, freeform o agrupado).

    OJO: usamos el borde SUPERIOR de la pregunta (qy0) como referencia, no el
    inferior — muchos cuadros de texto de preguntas en los moldes del ICBF
    tienen una altura "de diseño" mucho mayor que el texto real (quedan con
    bastante espacio vacío debajo), así que su borde inferior puede estar más
    cerca de la casilla de la SIGUIENTE pregunta que de la suya propia. Eso
    fue justo lo que causaba que algunas respuestas se escribieran en la
    casilla equivocada (y otras se sobreescribieran entre sí).

    Priorizamos la alineación horizontal (misma columna) sobre la cercanía
    vertical, y solo consideramos contenedores que empiezan en o debajo del
    inicio de la pregunta.
    """
    if qshape is None:
        return None
    qx0, qy0, qx1, qy1 = _bbox(qshape)
    margen = Pt(tol * 72)
    candidates = []
    for shape in slide.shapes:
        if shape.shape_id == qshape.shape_id:
            continue
        if shape.shape_type in (19, 5, 6):  # TABLE, FREEFORM, GROUP
            sx0, sy0, sx1, sy1 = _bbox(shape)
            if sy0 < qy0 - margen:
                continue  # está por encima de la pregunta: no puede ser su respuesta
            dist = abs(sx0 - qx0) * 3 + abs(sy0 - qy0)
            candidates.append((dist, shape))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


def find_shape_by_id(slide_or_group, shape_id):
    for shape in slide_or_group.shapes:
        if shape.shape_id == shape_id:
            return shape
        if shape.shape_type == 6:  # GROUP
            found = find_shape_by_id(shape, shape_id)
            if found is not None:
                return found
    return None


def write_answer(container, text, size=12):
    """Escribe `text` (precedido del TAG de borrador) dentro del contenedor."""
    if container is None:
        return False
    if container.shape_type == 19:  # TABLE
        tf = container.table.cell(0, 0).text_frame
    else:
        if not container.has_text_frame:
            return False
        tf = container.text_frame
        # Antes usábamos NONE (tamaño fijo). Pero los textos de "voces del
        # talento humano" suelen ser más largos que los de la familia y el
        # cuadro de esa diapositiva es más pequeño: con tamaño fijo el texto
        # se desbordaba y se montaba sobre las casillas vecinas (lo que vio
        # Alexander en el pantallazo). TEXT_TO_FIT_SHAPE le dice a PowerPoint
        # que reduzca automáticamente el tamaño de letra hasta que el texto
        # quepa dentro del cuadro — así nunca se desborda, sin importar cuánto
        # redacte la IA.
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.word_wrap = True
    for p in list(tf.paragraphs[1:] if len(tf.paragraphs) > 1 else []):
        p._p.getparent().remove(p._p)
    p = tf.paragraphs[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    r = p.add_run()
    r.text = TAG + text
    r.font.size = Pt(size)
    r.font.italic = False
    r.font.color.rgb = TEXT_COLOR
    return True


def llenar_respuestas(slide, mapa_pregunta_a_texto, tol=0.35, size=12):
    """
    Recorre un mapa {subcadena_de_pregunta: texto_redactado} y escribe cada
    respuesta en el contenedor correspondiente de la diapositiva.

    Devuelve un reporte {pregunta: True/False} para registrar éxito/fallo
    (esto es justo lo que nos permitió detectar y corregir los problemas
    reales en el proyecto de los 34 cuadernos).
    """
    reporte = {}
    for pregunta, texto in mapa_pregunta_a_texto.items():
        q = find_question(slide, pregunta)
        contenedor = find_answer_table(slide, q, tol=tol)
        ok = write_answer(contenedor, texto, size=size)
        reporte[pregunta] = ok
    return reporte
