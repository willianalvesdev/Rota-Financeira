"""Conexão por requisição e inicialização idempotente do schema MySQL."""

import re
from contextlib import contextmanager
from pathlib import Path

import click
import mysql.connector
from flask import current_app, g
from flask.cli import with_appcontext

from .defaults import ensure_initial_goal


def connection_options(config, *, include_database=True):
    options = dict(
        host=config["DB_HOST"],
        port=config["DB_PORT"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        connection_timeout=5,
        autocommit=False,
    )
    if include_database:
        options["database"] = config["DB_NAME"]
    return options


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**connection_options(current_app.config))
    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def cursor(*, write=False):
    connection = get_db()
    current = connection.cursor(dictionary=True, buffered=True)
    try:
        yield current
        if write:
            connection.commit()
    except Exception:
        if write:
            connection.rollback()
        raise
    finally:
        current.close()


def initialize_database(config):
    name = config["DB_NAME"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
        raise ValueError("Nome de banco inválido: use letras, números e sublinhado.")
    schema = (Path(__file__).resolve().parent.parent / "setup_banco_sq.sql").read_text(encoding="utf-8")
    schema = schema.replace("rota_financeira_db", name)
    connection = mysql.connector.connect(**connection_options(config, include_database=False))
    try:
        with connection.cursor() as current:
            for statement in schema.split(";"):
                if statement.strip():
                    current.execute(statement)
            # Migração aditiva para instalações anteriores. Nenhum registro é apagado.
            current.execute(
                """SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='usuarios' AND COLUMN_NAME='reserva_inicializada'""",
                (name,),
            )
            if current.fetchone() is None:
                current.execute(
                    "ALTER TABLE usuarios ADD COLUMN reserva_inicializada BOOLEAN NOT NULL DEFAULT FALSE"
                )
            current.execute(
                """SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s
                AND TABLE_NAME='metas' AND COLUMN_NAME IN ('valor_alvo','data_limite') AND IS_NULLABLE='NO'""",
                (name,),
            )
            if current.fetchone()[0]:
                current.execute(
                    "ALTER TABLE metas MODIFY valor_alvo DECIMAL(12,2) NULL, MODIFY data_limite DATE NULL"
                )
            current.execute("SELECT id FROM usuarios WHERE reserva_inicializada=0")
            for (user_id,) in current.fetchall():
                ensure_initial_goal(current, user_id)
        connection.commit()
    finally:
        connection.close()


@click.command("init-db")
@click.option("--admin-user", default=None, help="Usuário administrador usado apenas na criação do banco.")
@with_appcontext
def init_db_command(admin_user):
    """Cria banco e tabelas ausentes, sem apagar registros existentes."""
    config = dict(current_app.config)
    if admin_user:
        config["DB_USER"] = admin_user
        config["DB_PASSWORD"] = click.prompt("Senha do administrador MySQL", hide_input=True)
    try:
        initialize_database(config)
    except (mysql.connector.Error, ValueError) as error:
        raise click.ClickException(
            "Não foi possível inicializar o banco. Confira a configuração e as permissões."
        ) from error
    click.echo("Banco e tabelas verificados com sucesso.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
