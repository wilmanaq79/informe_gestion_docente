# -*- coding: utf-8 -*-
"""Fixtures compartidas de pytest.

db_session: sesion de base de datos AISLADA para pruebas que necesitan
Postgres real (ACID, repository). Abre una conexion dedicada, inicia
una transaccion y la revierte al terminar la prueba -- sin importar que
el codigo bajo prueba llame session.commit() (join_transaction_mode=
"create_savepoint" hace que cada commit interno solo cierre un
SAVEPOINT dentro de esta transaccion externa, que nunca se confirma de
verdad). Ningun dato de prueba llega a persistir en la base de datos de
desarrollo -- se usa la misma DATABASE_URL de .env, pero el rollback
final la deja exactamente como estaba."""
import pytest
from sqlalchemy.orm import sessionmaker

from db.database import engine


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(
        bind=connection, autoflush=False, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
