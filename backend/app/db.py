"""
Rayuela — capa de acceso a la base de datos (Postgres en Railway).

Crea la tabla `planeaciones` al arrancar si no existe, con migraciones
seguras (ADD COLUMN IF NOT EXISTS) para no perder datos si ya existía
una versión anterior del esquema. Expone helpers para insertar,
consultar y actualizar registros.

La variable DATABASE_URL la inyecta Railway automáticamente cuando
el servicio Postgres está enlazado al backend en el mismo proyecto.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor


def _conn():
    """Abre una conexión fresca a Postgres usando la variable de entorno."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init():
    """
    Crea la tabla `planeaciones` si no existe todavía, y añade columnas
    faltantes si hay una versión anterior del esquema (ADD COLUMN IF NOT
    EXISTS — nunca destruye datos existentes).
    Se llama una vez al arrancar el servidor (desde main.py).
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            # Esquema completo — se ejecuta solo si la tabla aún no existe
            cur.execute("""
                CREATE TABLE IF NOT EXISTS planeaciones (
                    id                      SERIAL PRIMARY KEY,
                    nombre_nino             TEXT NOT NULL,
                    fecha_encuentro         DATE NOT NULL,
                    genero                  TEXT,
                    tipo_cuaderno           TEXT NOT NULL DEFAULT 'hogar',
                    banda_clave             TEXT,
                    banda_etiqueta          TEXT,
                    actividad_principal     TEXT,
                    nombre_ronda            TEXT,
                    link_ronda              TEXT,
                    objetos_paquete         TEXT,
                    textos_generados        JSONB,
                    estado                  TEXT NOT NULL DEFAULT 'pendiente_voces',
                    observaciones_encuentro TEXT,
                    fecha_creacion          TIMESTAMP NOT NULL DEFAULT NOW(),
                    fecha_completado        TIMESTAMP
                )
            """)
            # Migraciones seguras: añade columnas que puede faltar en
            # versiones anteriores del esquema, sin tocar datos existentes
            for col, definition in [
                ("genero", "TEXT"),
                ("tipo_cuaderno", "TEXT"),
                ("banda_clave", "TEXT"),
                ("banda_etiqueta", "TEXT"),
                ("textos_generados", "JSONB"),
                ("tipo_participante", "TEXT"),
                ("actividad_principal_2", "TEXT"),
                ("nombre_ronda_2", "TEXT"),
                ("link_ronda_2", "TEXT"),
                ("modalidad_acompanamiento", "TEXT"),
                ("aspectos_fortalecer", "TEXT"),
            ]:
                cur.execute(
                    f"ALTER TABLE planeaciones "
                    f"ADD COLUMN IF NOT EXISTS {col} {definition}"
                )
        conn.commit()


def guardar_planeacion(datos):
    """
    Inserta una nueva planeación y devuelve su id.

    `datos` debe contener:
      nombre_nino, fecha_encuentro, genero, tipo_cuaderno,
      banda_clave, banda_etiqueta, actividad_principal,
      nombre_ronda, link_ronda, objetos_paquete, textos_generados (dict).

    Campos opcionales (solo se usan en "llamada"; se autocompletan si
    el llamador -el flujo de "hogar"- no los envía):
      tipo_participante, actividad_principal_2, nombre_ronda_2,
      link_ronda_2, modalidad_acompanamiento, aspectos_fortalecer.
    """
    datos_db = dict(datos)
    for campo in ("tipo_participante", "actividad_principal_2",
                  "nombre_ronda_2", "link_ronda_2",
                  "modalidad_acompanamiento", "aspectos_fortalecer"):
        datos_db.setdefault(campo, None)

    # psycopg2 no serializa dicts a JSONB automáticamente
    if isinstance(datos_db.get("textos_generados"), dict):
        datos_db["textos_generados"] = json.dumps(
            datos_db["textos_generados"], ensure_ascii=False
        )

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO planeaciones
                    (nombre_nino, fecha_encuentro, genero, tipo_cuaderno,
                     tipo_participante, banda_clave, banda_etiqueta,
                     actividad_principal, actividad_principal_2,
                     nombre_ronda, link_ronda, nombre_ronda_2, link_ronda_2,
                     modalidad_acompanamiento, objetos_paquete,
                     aspectos_fortalecer, textos_generados)
                VALUES
                    (%(nombre_nino)s, %(fecha_encuentro)s, %(genero)s,
                     %(tipo_cuaderno)s, %(tipo_participante)s,
                     %(banda_clave)s, %(banda_etiqueta)s,
                     %(actividad_principal)s, %(actividad_principal_2)s,
                     %(nombre_ronda)s, %(link_ronda)s, %(nombre_ronda_2)s,
                     %(link_ronda_2)s, %(modalidad_acompanamiento)s,
                     %(objetos_paquete)s, %(aspectos_fortalecer)s,
                     %(textos_generados)s)
                RETURNING id
            """, datos_db)
            nuevo_id = cur.fetchone()[0]
        conn.commit()
    return nuevo_id


def listar_pendientes():
    """
    Devuelve todas las planeaciones con estado 'pendiente_voces',
    ordenadas de la más reciente a la más antigua.
    Solo trae los campos necesarios para la lista (no los textos completos).
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, nombre_nino, fecha_encuentro,
                       actividad_principal, tipo_cuaderno, fecha_creacion
                FROM planeaciones
                WHERE estado = 'pendiente_voces'
                ORDER BY fecha_encuentro DESC
            """)
            return [dict(row) for row in cur.fetchall()]


def obtener_planeacion(planeacion_id):
    """
    Devuelve una planeación completa (todos los campos) por su id,
    o None si no existe.
    Los textos_generados se devuelven como dict (no como string JSON).
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM planeaciones WHERE id = %s",
                (planeacion_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            result = dict(row)
            # textos_generados puede llegar como string si la columna es TEXT
            if isinstance(result.get("textos_generados"), str):
                result["textos_generados"] = json.loads(result["textos_generados"])
            return result


def completar_planeacion(planeacion_id, observaciones):
    """
    Guarda las observaciones del encuentro real y marca la planeación
    como 'completado', registrando la fecha y hora.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE planeaciones
                SET estado                  = 'completado',
                    observaciones_encuentro = %s,
                    fecha_completado        = NOW()
                WHERE id = %s
            """, (observaciones, planeacion_id))
        conn.commit()
