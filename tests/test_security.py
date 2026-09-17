from datetime import date
from decimal import Decimal
from html.parser import HTMLParser

import pytest
from mysql.connector import OperationalError

from rota_financeira import create_app, db


class CsrfTokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name") == "csrf_token":
            self.token = values.get("value")


def csrf_token(response):
    parser = CsrfTokenParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.token, "The form must render a CSRF token."
    return parser.token


@pytest.mark.parametrize(
    "path",
    [
        "/adicionar-transacao",
        "/transacoes/1/editar",
        "/transacoes/1/excluir",
        "/adicionar-meta",
        "/metas/1/editar",
        "/metas/1/aportar",
        "/metas/1/excluir",
    ],
)
def test_anonymous_writes_require_login(client, query_one, path):
    response = client.post(path, data={"valor": "100", "nome_meta": "Intruso"})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 0
    assert query_one("SELECT COUNT(*) AS total FROM metas")["total"] == 0


def test_other_users_cannot_change_transactions_or_goals(
    authenticated_client, make_user, insert_transaction, insert_goal, query_one
):
    owner = make_user("proprietario@example.com")
    transaction_id = insert_transaction(owner, "Privado", "60.00", "receita", "2024-01-10")
    goal_id = insert_goal(owner, current="100.00")
    forms = [
        (
            f"/transacoes/{transaction_id}/editar",
            {
                "descricao": "Ataque",
                "valor": "1.00",
                "tipo": "despesa",
                "data_transacao": date.today().isoformat(),
            },
        ),
        (f"/transacoes/{transaction_id}/excluir", {}),
        (
            f"/metas/{goal_id}/editar",
            {
                "nome_meta": "Ataque",
                "valor_alvo": "1.00",
                "valor_atual": "0",
                "data_limite": date.today().isoformat(),
            },
        ),
        (f"/metas/{goal_id}/aportar", {"valor": "100.00"}),
        (f"/metas/{goal_id}/excluir", {}),
    ]
    for path, form in forms:
        assert authenticated_client.post(path, data=form).status_code == 404
    assert query_one("SELECT descricao, valor FROM transacoes WHERE id = %s", (transaction_id,)) == {
        "descricao": "Privado",
        "valor": Decimal("60.00"),
    }
    assert query_one("SELECT nome_meta, valor_atual FROM metas WHERE id = %s", (goal_id,)) == {
        "nome_meta": "Reserva",
        "valor_atual": Decimal("100.00"),
    }


def test_search_treats_sql_injection_and_wildcards_as_literal_text(
    authenticated_client, user_id, insert_transaction, rendered_context
):
    insert_transaction(user_id, "Compra normal", "10.00", "despesa", "2024-01-10")
    insert_transaction(user_id, "Desconto 10% especial", "20.00", "receita", "2024-01-10")
    with rendered_context() as contexts:
        response = authenticated_client.get("/", query_string={"month": "2024-01", "q": "' OR 1=1 --"})
    assert response.status_code == 200
    assert contexts[-1]["total_transacoes"] == 0
    with rendered_context() as contexts:
        response = authenticated_client.get("/", query_string={"month": "2024-01", "q": "%"})
    assert response.status_code == 200
    assert contexts[-1]["total_transacoes"] == 1


def test_user_content_is_escaped_in_dashboard(authenticated_client, user_id, insert_transaction, insert_goal):
    payload = '<script>alert("xss")</script>'
    insert_transaction(user_id, payload, "10.00", "receita", "2024-01-10")
    insert_goal(user_id, name=payload)
    response = authenticated_client.get("/?month=2024-01")
    assert response.status_code == 200
    assert payload.encode() not in response.data
    assert b"&lt;script&gt;" in response.data


def test_csrf_is_required_for_login_and_authenticated_writes(database_config, user_id, query_one):
    config = dict(database_config, WTF_CSRF_ENABLED=True)
    csrf_app = create_app(config)
    client = csrf_app.test_client()
    credentials = {"email": "ana@example.com", "senha": "senha-segura-123"}
    assert client.post("/fazer-login", data=credentials).status_code == 400
    login_token = csrf_token(client.get("/login"))
    response = client.post("/fazer-login", data=dict(credentials, csrf_token=login_token))
    assert response.status_code == 302
    form = {
        "descricao": "Com proteção",
        "valor": "1.00",
        "tipo": "receita",
        "data_transacao": date.today().isoformat(),
    }
    assert client.post("/adicionar-transacao", data=form).status_code == 400
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 0
    token = csrf_token(client.get("/"))
    assert client.post("/adicionar-transacao", data=dict(form, csrf_token=token)).status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 1
    assert client.post("/logout").status_code == 400


def test_missing_resource_does_not_expose_debugger(authenticated_client):
    response = authenticated_client.get("/pagina-inexistente")
    assert response.status_code == 404
    body = response.get_data(as_text=True).lower()
    assert "traceback" not in body
    assert "werkzeug debugger" not in body


def test_database_failure_is_friendly_and_does_not_expose_internal_details(authenticated_client, monkeypatch):
    detail = "private-database-host SQL password=private-test-secret"

    def unavailable():
        raise OperationalError(detail)

    monkeypatch.setattr(db, "get_db", unavailable)
    response = authenticated_client.get("/")
    assert response.status_code == 503
    body = response.get_data(as_text=True)
    assert detail not in body
    assert "Traceback" not in body
    assert "temporariamente" in body.lower()


def test_database_initialization_is_repeatable_and_preserves_data(database_config, user_id, query_one):
    db.initialize_database(database_config)
    assert query_one("SELECT COUNT(*) AS total FROM usuarios")["total"] == 1
    assert query_one("SELECT email FROM usuarios WHERE id = %s", (user_id,))["email"] == "ana@example.com"


def test_sensitive_pages_have_security_and_cache_headers(authenticated_client):
    response = authenticated_client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "object-src 'none'" in response.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in response.headers["Content-Security-Policy"]


def test_repeated_failed_logins_are_rate_limited(database_config, user_id):
    config = dict(database_config, RATELIMIT_ENABLED=True, RATELIMIT_STORAGE_URI="memory://")
    limited_app = create_app(config)
    client = limited_app.test_client()
    for _ in range(10):
        assert (
            client.post("/fazer-login", data={"email": "ana@example.com", "senha": "incorreta"}).status_code
            == 401
        )
    response = client.post("/fazer-login", data={"email": "ana@example.com", "senha": "incorreta"})
    assert response.status_code == 429
    assert "Traceback" not in response.get_data(as_text=True)
