"""Integration fixtures that never use the application's real database."""

import os
import re
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import mysql.connector
import pytest
from flask import template_rendered
from werkzeug.security import generate_password_hash

from rota_financeira import create_app
from rota_financeira.db import initialize_database


@pytest.fixture(scope="session")
def database_config():
    database_name = f"rota_financeira_test_{uuid4().hex}"
    connection_settings = {
        "host": os.getenv("MYSQL_TEST_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_TEST_PORT", "3306")),
        "user": os.getenv("MYSQL_TEST_USER", "root"),
        "password": os.getenv("MYSQL_TEST_PASSWORD", "root"),
    }
    config = {
        "TESTING": True,
        "SECRET_KEY": "test-only-secret-key-never-use-in-production",
        "DB_HOST": connection_settings["host"],
        "DB_PORT": connection_settings["port"],
        "DB_USER": connection_settings["user"],
        "DB_PASSWORD": connection_settings["password"],
        "DB_NAME": database_name,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
    }
    connection = mysql.connector.connect(**connection_settings)
    created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        created = True
        initialize_database(config)
        yield config
    finally:
        # Both strict format and the locally generated name are checked before DROP.
        if created:
            assert re.fullmatch(r"rota_financeira_test_[0-9a-f]{32}", database_name)
            assert config["DB_NAME"] == database_name
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database_name}`")
        connection.close()


@pytest.fixture
def db_connection(database_config):
    connection = mysql.connector.connect(
        host=database_config["DB_HOST"],
        port=database_config["DB_PORT"],
        user=database_config["DB_USER"],
        password=database_config["DB_PASSWORD"],
        database=database_config["DB_NAME"],
        autocommit=True,
    )
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def clean_database(db_connection):
    with db_connection.cursor() as cursor:
        for table in ("transacoes", "metas", "usuarios"):
            cursor.execute(f"DELETE FROM {table}")


@pytest.fixture
def app(database_config):
    return create_app(database_config.copy())


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(db_connection):
    def create(
        email="ana@example.com", name="Ana Teste", password="senha-segura-123", reserve_initialized=True
    ):
        with db_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha, reserva_inicializada) VALUES (%s, %s, %s, %s)",
                (name, email, generate_password_hash(password), reserve_initialized),
            )
            return cursor.lastrowid

    return create


@pytest.fixture
def user_id(make_user):
    return make_user()


@pytest.fixture
def authenticated_client(client, user_id):
    response = client.post("/fazer-login", data={"email": "ana@example.com", "senha": "senha-segura-123"})
    assert response.status_code == 302
    return client


@pytest.fixture
def insert_transaction(db_connection):
    def insert(user_id, description, value, kind, day):
        with db_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transacoes "
                "(usuario_id, descricao, valor, tipo, data_transacao) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, description, Decimal(str(value)), kind, day),
            )
            return cursor.lastrowid

    return insert


@pytest.fixture
def insert_goal(db_connection):
    def insert(user_id, name="Reserva", target="1000.00", current="0.00", deadline=None):
        if deadline is None:
            deadline = date.today() + timedelta(days=30)
        with db_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO metas "
                "(usuario_id, nome_meta, valor_alvo, valor_atual, data_limite) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, name, Decimal(target), Decimal(current), deadline),
            )
            return cursor.lastrowid

    return insert


@pytest.fixture
def rendered_context(app):
    @contextmanager
    def capture():
        contexts = []

        def record(sender, template, context, **extra):
            contexts.append(context.copy())

        template_rendered.connect(record, app)
        try:
            yield contexts
        finally:
            template_rendered.disconnect(record, app)

    return capture


@pytest.fixture
def query_one(db_connection):
    def query(sql, parameters=()):
        with db_connection.cursor(dictionary=True) as cursor:
            cursor.execute(sql, parameters)
            return cursor.fetchone()

    return query
