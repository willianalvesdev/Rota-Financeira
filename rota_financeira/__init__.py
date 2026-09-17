"""Configuração, segurança e ciclo de vida da aplicação Flask."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFError, CSRFProtect
from mysql.connector import Error as DatabaseError
from werkzeug.exceptions import HTTPException

from . import db
from .validation import format_currency, format_date

ROOT = Path(__file__).resolve().parent.parent
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(test_config=None):
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DB_HOST=os.getenv("DB_HOST", "127.0.0.1"),
        DB_PORT=int(os.getenv("DB_PORT", "3306")),
        DB_NAME=os.getenv("DB_NAME", "rota_financeira_db"),
        DB_USER=os.getenv("DB_USER", "rota_financeira_app"),
        DB_PASSWORD=os.getenv("DB_PASSWORD", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024,
        MAX_FORM_PARTS=30,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        RATELIMIT_HEADERS_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    key = app.config["SECRET_KEY"]
    if not key or len(key) < 32 or key.startswith("troque-"):
        raise RuntimeError(
            "Configure SECRET_KEY no arquivo .env com uma chave aleatória de pelo menos 32 caracteres."
        )

    csrf.init_app(app)
    limiter.init_app(app)
    db.init_app(app)
    app.jinja_env.filters["moeda"] = format_currency
    app.jinja_env.filters["data_br"] = format_date

    from .views import register_routes

    register_routes(app, limiter)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    def error_page(code, title, message):
        return render_template("error.html", codigo=code, titulo=title, mensagem=message), code

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return error_page(
            400,
            "Vamos tentar novamente?",
            "Este formulário expirou ou não pôde ser validado. Recarregue a página e envie novamente.",
        )

    @app.errorhandler(DatabaseError)
    def database_error(error):
        app.logger.error("Falha na operação do banco de dados", exc_info=True)
        return error_page(
            503,
            "Serviço temporariamente indisponível",
            "Não foi possível acessar seus dados agora. Tente novamente em alguns instantes.",
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {
            400: ("Solicitação inválida", "Confira os dados e tente novamente."),
            403: ("Acesso não permitido", "Você não tem permissão para acessar este conteúdo."),
            404: ("Página não encontrada", "Esta página ou registro não está disponível."),
            405: ("Ação não permitida", "Use os botões e formulários da página para continuar."),
            413: ("Formulário muito grande", "Reduza o conteúdo enviado e tente novamente."),
            429: (
                "Uma pausa rápida",
                "Muitas tentativas em pouco tempo. Aguarde um minuto antes de tentar novamente.",
            ),
        }
        title, message = messages.get(
            error.code, ("Não foi possível continuar", "Tente novamente em alguns instantes.")
        )
        response = app.make_response(error_page(error.code, title, message))
        if error.code == 405 and error.valid_methods:
            response.headers["Allow"] = ", ".join(error.valid_methods)
        return response

    @app.errorhandler(500)
    def server_error(error):
        return error_page(500, "Algo não saiu como esperado", "Tente novamente em alguns instantes.")

    return app
