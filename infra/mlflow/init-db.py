"""Create the MLflow tracking database and its restricted owner over PostgreSQL TCP."""

from pathlib import Path

import psycopg
from psycopg import sql


def secret(name: str) -> str:
    return Path("/run/secrets", name).read_text().strip()


def connect(user: str, database: str, password: str) -> psycopg.Connection:
    return psycopg.connect(
        host="postgres", user=user, dbname=database, password=password,
        connect_timeout=5, options="-c statement_timeout=15000", autocommit=True,
    )


def provision(connection: psycopg.Connection, name: str, password: str) -> None:
    identifier = sql.Identifier(name)
    role = connection.execute(
        """SELECT rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole
                                      OR rolreplication OR rolbypassrls)
           FROM pg_roles WHERE rolname = %s""",
        (name,),
    ).fetchone()
    if role is None:
        connection.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
            identifier, sql.Literal(password),
        ))
    elif not role[0]:
        raise RuntimeError(f"Existing database role {name} has unexpected privileges")

    owner = connection.execute(
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (name,),
    ).fetchone()
    if owner is None:
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(identifier, identifier))
    elif owner[0] != name:
        raise RuntimeError(f"Existing database {name} has an unexpected owner")

    connection.execute(sql.SQL("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC").format(
        identifier,
    ))
    with connect(name, name, password) as service:
        service.execute("SELECT 1")
    print(f"Database {name} is ready")


with connect("platform_db_admin", "postgres", secret("postgres_password")) as admin:
    admin.execute("SELECT pg_advisory_lock(7871)")
    provision(admin, "mlflow", secret("tracking_db_password"))
