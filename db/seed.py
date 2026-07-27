"""
Crea las tablas (si no existen) y siembra los datos de referencia minimos:
roles, cortes (con sus pesos 30/30/40) y el periodo academico actual.

Tambien crea UNA cuenta inicial de Director (usuario 'admin') para poder
entrar por primera vez y, desde la pantalla de Administracion de usuarios,
crear las cuentas reales del Director, el Secretario Academico y los 27
docentes -- este script no inventa esos nombres porque no son datos que
el agente conozca.

Uso:
    python -m db.seed
"""
from sqlalchemy import select

from db.auth import hash_password
from db.database import engine, get_session
from db.models import Base, Corte, PeriodoAcademico, Rol, Usuario
from db.repository import parsear_periodo

ROLES = ["docente", "director", "secretario", "secretaria_programa"]
CORTES = [
    (1, "Corte 1", 0.30),
    (2, "Corte 2", 0.30),
    (3, "Corte 3 / Final", 0.40),
]
PERIODO_ACTUAL = "2026-1"

USUARIO_BOOTSTRAP = {
    "nombre_completo": "Administrador (temporal)",
    "username": "admin",
    "password": "cambiar123",
    "rol": "director",
}


def sembrar():
    Base.metadata.create_all(engine)

    with get_session() as session:
        for nombre in ROLES:
            if session.scalar(select(Rol).where(Rol.nombre == nombre)) is None:
                session.add(Rol(nombre=nombre))
        session.commit()

        for numero, nombre, peso in CORTES:
            if session.scalar(select(Corte).where(Corte.numero == numero)) is None:
                session.add(Corte(numero=numero, nombre=nombre, peso_porcentual=peso))
        session.commit()

        if session.scalar(select(PeriodoAcademico).where(PeriodoAcademico.nombre == PERIODO_ACTUAL)) is None:
            anio, semestre = parsear_periodo(PERIODO_ACTUAL)
            session.add(PeriodoAcademico(nombre=PERIODO_ACTUAL, anio=anio, semestre=semestre, activo=True))
        session.commit()

        if session.scalar(select(Usuario).where(Usuario.username == USUARIO_BOOTSTRAP["username"])) is None:
            rol_director = session.scalar(select(Rol).where(Rol.nombre == USUARIO_BOOTSTRAP["rol"]))
            session.add(
                Usuario(
                    nombre_completo=USUARIO_BOOTSTRAP["nombre_completo"],
                    username=USUARIO_BOOTSTRAP["username"],
                    password_hash=hash_password(USUARIO_BOOTSTRAP["password"]),
                    rol_id=rol_director.id,
                    activo=True,
                )
            )
            session.commit()
            print(
                f"Cuenta inicial creada -> usuario: {USUARIO_BOOTSTRAP['username']}  "
                f"contrasena: {USUARIO_BOOTSTRAP['password']}  (cambiala despues de entrar)"
            )
        else:
            print("La cuenta inicial 'admin' ya existia, no se recreo.")

    print("Listo: roles, cortes y periodo academico sembrados.")


if __name__ == "__main__":
    sembrar()
