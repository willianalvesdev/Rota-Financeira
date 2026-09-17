"""Páginas institucionais e arquivos públicos do aplicativo."""

from datetime import date
from pathlib import Path

from flask import render_template, send_from_directory

ROOT = Path(__file__).resolve().parent.parent


def register_public_routes(app):
    @app.context_processor
    def public_context():
        today = date.today()
        return dict(
            ano_atual=today.year,
            data_atual_label=today.strftime("%d/%m/%Y"),
            contato_email=app.config.get("CONTACT_EMAIL", ""),
            redes_sociais=app.config.get("SOCIAL_LINKS", []),
        )

    @app.get("/privacidade")
    def privacidade():
        return render_template("privacidade.html")

    @app.get("/contato")
    def contato():
        return render_template("contato.html")

    @app.get("/robots.txt")
    def robots():
        return send_from_directory(ROOT, "robots.txt", mimetype="text/plain")

    @app.get("/llms.txt")
    def llms():
        return send_from_directory(ROOT, "llms.txt", mimetype="text/plain")

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(
            ROOT / "static", "manifest.webmanifest", mimetype="application/manifest+json"
        )
