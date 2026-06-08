"""
Rayuela — lógica de bandas de edad y desarrollo.

Convención derivada de la lista real de Jimena (niños de Posprimaria Guadualito):
- 0 a 5 meses, 29 días  -> banda "0-6 meses"   (gender label "bebé", vocabulario sensorial-receptivo)
- 6 a 11 meses, 29 días -> banda "6-11 meses"  (gender label "bebé", vocabulario exploratorio-activo)
- 1 a 2 años, 11 meses  -> banda "1-2 años"    (gender label "niño"/"niña", vocabulario de autonomía)
- 3 a 4 años, 11 meses  -> banda "3-4 años"    (gender label "niño"/"niña", vocabulario de convivencia/lenguaje)

IMPORTANTE: la "banda de desarrollo" determina el banco de frases que se usa
para redactar; el "gender" (niño/niña/bebé) determina solo el sustantivo.
Esto es justo lo que falló en la primera ronda manual (ver feedback de Jimena:
"a los 6-11 meses sí se puede decir 'participó activamente', de 0 a 6 no").
"""

from datetime import date


BANDAS = [
    # (edad_min_meses, edad_max_meses, clave, etiqueta)
    (0, 6, "0-6m", "0 a 6 meses"),
    (6, 12, "6-11m", "6 a 11 meses"),
    (12, 36, "1-2a", "1 a 2 años"),
    (36, 60, "3-4a", "3 a 4 años, 11 meses"),
]


def edad_en_meses(fecha_nacimiento: date, fecha_referencia: date = None) -> int:
    """Calcula la edad en meses completos a la fecha de referencia (hoy si no se da)."""
    if fecha_referencia is None:
        fecha_referencia = date.today()
    meses = (fecha_referencia.year - fecha_nacimiento.year) * 12 \
        + (fecha_referencia.month - fecha_nacimiento.month)
    if fecha_referencia.day < fecha_nacimiento.day:
        meses -= 1
    return max(meses, 0)


def banda_por_edad(meses: int) -> dict:
    """Devuelve la banda de desarrollo correspondiente a una edad en meses."""
    for lo, hi, clave, etiqueta in BANDAS:
        if lo <= meses < hi:
            return {"clave": clave, "etiqueta": etiqueta, "meses": meses}
    # Si se sale del rango esperado (no debería pasar en este programa), usamos la última banda
    lo, hi, clave, etiqueta = BANDAS[-1]
    return {"clave": clave, "etiqueta": etiqueta, "meses": meses}


def sustantivo(genero: str, banda_clave: str) -> str:
    """
    Devuelve el sustantivo correcto a usar según el sexo del niño/niña Y su banda
    de edad — porque en 0-11 meses el ICBF y Jimena usan "bebé"
    independientemente del sexo biológico, y de 1 año en adelante se usa
    "niño"/"niña".

    `genero` esperado: "M" o "F" (sexo biológico, dato fijo del registro del niño)
    """
    if banda_clave in ("0-6m", "6-11m"):
        return "bebé"
    return "niño" if genero == "M" else "niña"


def articulo(sustantivo_: str, genero: str) -> str:
    if sustantivo_ == "bebé":
        return "el bebé"
    return "el niño" if genero == "M" else "la niña"
