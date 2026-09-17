"""Prepara schema e usuário da aplicação usando credenciais administrativas temporárias."""

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mysql.connector  # noqa: E402

from rota_financeira import create_app  # noqa: E402
from rota_financeira.db import connection_options, initialize_database  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-user", default="root")
    args = parser.parse_args()
    app = create_app()
    config = dict(app.config)
    name, user = config["DB_NAME"], config["DB_USER"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", user) or user == args.admin_user:
        raise SystemExit(
            "Configure DB_USER no .env com um usuário próprio da aplicação, diferente do administrador."
        )
    if config["DB_HOST"] not in ("127.0.0.1", "localhost"):
        raise SystemExit("Este configurador é exclusivo para MySQL local.")
    if len(config["DB_PASSWORD"]) < 16:
        raise SystemExit("Configure DB_PASSWORD com uma senha aleatória de pelo menos 16 caracteres.")
    admin_config = dict(
        config,
        DB_USER=args.admin_user,
        DB_PASSWORD=os.getenv("MYSQL_ADMIN_PASSWORD") or getpass.getpass("Senha do administrador MySQL: "),
    )
    initialize_database(admin_config)
    with mysql.connector.connect(**connection_options(admin_config)) as connection:
        with connection.cursor() as current:
            current.execute(
                "CREATE USER IF NOT EXISTS %s@'localhost' IDENTIFIED BY %s", (user, config["DB_PASSWORD"])
            )
            current.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{name}`.* TO %s@'localhost'", (user,))
        connection.commit()
    # Uma conta já existente não tem a senha sobrescrita: a conexão abaixo valida o .env.
    with mysql.connector.connect(**connection_options(config)) as connection:
        with connection.cursor() as current:
            current.execute("SELECT 1")
            current.fetchone()
    print("Banco pronto. A aplicação usa uma conta própria, sem permissões administrativas.")


if __name__ == "__main__":
    main()
