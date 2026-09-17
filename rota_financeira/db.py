"""Conexão por requisição e inicialização idempotente do schema MySQL."""

import re
from contextlib import contextmanager
from pathlib import Path

import click
import mysql.connector
from flask import current_app, g
from flask.cli import with_appcontext


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
