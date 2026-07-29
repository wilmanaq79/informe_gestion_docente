# -*- coding: utf-8 -*-
"""Migracion puntual: agrega soporte real de multi-programa academico.

Antes de esta migracion, el sistema asumia un solo programa academico
("Ingenieria de Sistemas" quedaba escrito como texto libre en varios
lugares, sin ninguna tabla ni filtro real). Esta migracion:

1. Crea la tabla `programas` (Base.metadata.create_all ya la crea sola
   por ser tabla nueva) y siembra el programa piloto actual.
2. Agrega `programa_id` a usuarios, asignaciones_academicas,
   repositorio_asignaturas y entregas, y hace backfill de todos los
   datos existentes -- hoy TODOS son del programa piloto.
3. Convierte `asignaciones_academicas.programa` (texto libre) en una FK
   real, y `repositorio_asignaturas.asignatura` (unique GLOBAL) en un
   unique COMPUESTO por programa (dos programas ya pueden tener una
   materia con el mismo nombre, p.ej. "Cálculo I").

Idempotente: se puede correr varias veces sin duplicar ni romper nada.
El alta de los 14 programas nuevos (con su Director inicial cada uno)
es un paso POSTERIOR y separado -- solo debe hacerse despues de
confirmar que el programa piloto sigue funcionando identico tras esta
migracion.

Uso:
    python -m scripts.migrar_multi_programa
"""
from sqlalchemy import text

from db.database import engine
from db.models import Base

PROGRAMA_PILOTO_NOMBRE = "Ingeniería de Sistemas"
PROGRAMA_PILOTO_CODIGO = "ing-sistemas"


def migrar():
    Base.metadata.create_all(engine)  # crea la tabla `programas` si no existe

    with engine.begin() as conn:
        # 1) Programa piloto (el unico que existe hasta que se den de
        #    alta los 14 nuevos, en un paso posterior y separado).
        conn.execute(
            text(
                "INSERT INTO programas (nombre, codigo, activo) "
                "VALUES (:nombre, :codigo, true) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"nombre": PROGRAMA_PILOTO_NOMBRE, "codigo": PROGRAMA_PILOTO_CODIGO},
        )
        programa_piloto_id = conn.execute(
            text("SELECT id FROM programas WHERE codigo = :codigo"),
            {"codigo": PROGRAMA_PILOTO_CODIGO},
        ).scalar_one()

        # 2) usuarios.programa_id -- todo usuario real (no la cuenta
        #    bootstrap 'admin' de db/seed.py) es hoy del programa piloto.
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas(id)"))
        conn.execute(
            text(
                "UPDATE usuarios SET programa_id = :pid "
                "WHERE programa_id IS NULL AND username <> 'admin'"
            ),
            {"pid": programa_piloto_id},
        )

        # 3) asignaciones_academicas: agrega programa_id real, backfill
        #    desde el docente, y SOLO al final borra la columna vieja de
        #    texto libre ('programa') -- nunca antes de confirmar el
        #    backfill.
        conn.execute(
            text("ALTER TABLE asignaciones_academicas ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas(id)")
        )
        conn.execute(
            text(
                "UPDATE asignaciones_academicas a SET programa_id = u.programa_id "
                "FROM usuarios u WHERE a.docente_id = u.id AND a.programa_id IS NULL"
            )
        )
        sin_programa_asignacion = conn.execute(
            text("SELECT count(*) FROM asignaciones_academicas WHERE programa_id IS NULL")
        ).scalar_one()
        if sin_programa_asignacion == 0:
            conn.execute(text("ALTER TABLE asignaciones_academicas ALTER COLUMN programa_id SET NOT NULL"))
            conn.execute(text("ALTER TABLE asignaciones_academicas DROP COLUMN IF EXISTS programa"))
        else:
            print(
                f"  AVISO: quedaron {sin_programa_asignacion} asignaciones sin programa_id "
                "(docente sin programa_id) -- revisa antes de volver a correr esta migracion."
            )

        # 4) repositorio_asignaturas: agrega programa_id, backfill al
        #    programa piloto (todas las filas existentes son de ese
        #    programa), y reemplaza el unique GLOBAL de 'asignatura' por
        #    uno compuesto (programa_id, asignatura).
        conn.execute(
            text("ALTER TABLE repositorio_asignaturas ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas(id)")
        )
        conn.execute(
            text("UPDATE repositorio_asignaturas SET programa_id = :pid WHERE programa_id IS NULL"),
            {"pid": programa_piloto_id},
        )
        conn.execute(text("ALTER TABLE repositorio_asignaturas ALTER COLUMN programa_id SET NOT NULL"))
        conn.execute(text("ALTER TABLE repositorio_asignaturas DROP CONSTRAINT IF EXISTS repositorio_asignaturas_asignatura_key"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_repositorio_programa_asignatura "
                "ON repositorio_asignaturas (programa_id, asignatura)"
            )
        )

        # 5) entregas: agrega programa_id desnormalizado desde el
        #    docente (evita un JOIN en listar_entregas).
        conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS programa_id INTEGER REFERENCES programas(id)"))
        conn.execute(
            text(
                "UPDATE entregas e SET programa_id = u.programa_id "
                "FROM usuarios u WHERE e.docente_id = u.id AND e.programa_id IS NULL"
            )
        )
        sin_programa_entrega = conn.execute(
            text("SELECT count(*) FROM entregas WHERE programa_id IS NULL")
        ).scalar_one()
        if sin_programa_entrega == 0:
            conn.execute(text("ALTER TABLE entregas ALTER COLUMN programa_id SET NOT NULL"))
        else:
            print(
                f"  AVISO: quedaron {sin_programa_entrega} entregas sin programa_id -- "
                "revisa antes de volver a correr esta migracion."
            )

        # Indices explicitos (Postgres no los crea solo por ser FK).
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_usuarios_programa_id ON usuarios (programa_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_asignaciones_academicas_programa_id ON asignaciones_academicas (programa_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_repositorio_asignaturas_programa_id ON repositorio_asignaturas (programa_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entregas_programa_id ON entregas (programa_id)"))

        conteos = conn.execute(
            text(
                "SELECT "
                "(SELECT count(*) FROM programas), "
                "(SELECT count(*) FROM usuarios WHERE programa_id IS NOT NULL), "
                "(SELECT count(*) FROM asignaciones_academicas WHERE programa_id IS NOT NULL), "
                "(SELECT count(*) FROM repositorio_asignaturas WHERE programa_id IS NOT NULL), "
                "(SELECT count(*) FROM entregas WHERE programa_id IS NOT NULL)"
            )
        ).one()

    print(
        f"Listo: {conteos[0]} programa(s), {conteos[1]} usuarios, {conteos[2]} asignaciones, "
        f"{conteos[3]} entradas de repositorio y {conteos[4]} entregas con programa_id asignado."
    )


if __name__ == "__main__":
    migrar()
