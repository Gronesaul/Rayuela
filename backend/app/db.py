"""
Rayuela — capa de acceso a la base de datos (Postgres en Railway).

Crea la tabla `planeaciones` al arrancar si no existe, y expone
helpers para insertar, consultar y actualizar registros.

La variable DATABASE_URL la inyecta Railway automáticamente cuando
el servicio Postgres está enlazado al backend en el mismo proyecto.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def _conn():
    """Abre una conexión fresca a Postgres usando la variable de entorno."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init():
    """
    Crea la tabla `planeaciones` si todavía no existe.
    Se llama una vez al arrancar el servidor (desde main.py).
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS planeaciones (
                    id                        SERIAL PRIMARY KEY,
                    nombre_nino               TEXT NOT NULL,
                    fecha_encuentro           DATE NOT NULL,
                    banda_edad                TEXT,
                    nombre_ronda              TEXT,
                    link_ronda                TEXT,
                    actividad_principal       TEXT,
                    experiencias_momento_uno  TEXT,
                    experiencias_momento_dos  TEXT,
                    experiencias_momento_tres TEXT,
                    recursos_momento_uno      TEXT[],
                    recursos_momento_dos      TEXT[],
                    recursos_momento_tres     TEXT[],
                    objetos_paquete           TEXT,
                    estado                    TEXT NOT NULL DEFAULT 'pendiente_voces',
                    observaciones_encuentro   TEXT,
                    fecha_creacion            TIMESTAMP NOT NULL DEFAULT NOW(),
                    fecha_completado          TIMESTAMP
                )
            """)
        conn.commit()


def guardar_planeacion(datos):
    """
    Inserta una nueva planeación y devuelve su id.

    `datos` es un dict con las mismas claves que las columnas de la tabla
    (excepto id, estado, fecha_creacion y fecha_completado, que son
    automáticos).
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO planeaciones
                    (nombre_nino, fecha_encuentro, banda_edad,
                     nombre_ronda, link_ronda, actividad_principal,
                     experiencias_momento_uno, experiencias_momento_dos,
                     experiencias_momento_tres,
                     recursos_momento_uno, recursos_momento_dos,
                     recursos_momento_tres, objetos_paquete)
                VALUES
                    (%(nombre_nino)s, %(fecha_encuentro)s, %(banda_edad)s,
                     %(nombre_ronda)s, %(link_ronda)s, %(actividad_principal)s,
                     %(experiencias_momento_uno)s, %(experiencias_momento_dos)s,
                     %(experiencias_momento_tres)s,
                     %(recursos_momento_uno)s, %(recursos_momento_dos)s,
                     %(recursos_momento_tres)s, %(objetos_paquete)s)
                RETURNING id
            """, datos)
            nuevo_id = cur.fetchone()[0]
        conn.commit()
    return nuevo_id


def listar_pendientes():
    """
    Devuelve todas las planeaciones con estado 'pendiente_voces',
    ordenadas de la más reciente a la más antigua.
    Solo trae los campos necesarios para la lista (no el texto completo).
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, nombre_nino, fecha_encuentro,
                       actividad_principal, fecha_creacion
                FROM planeaciones
                WHERE estado = 'pendiente_voces'
                ORDER BY fecha_encuentro DESC
            """)
            return [dict(row) for row in cur.fetchall()]


def obtener_planeacion(planeacion_id):
    """
    Devuelve una planeación completa (todos los campos) por su id,
    o None si no existe.
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM planeaciones WHERE id = %s",
                (planeacion_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


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
