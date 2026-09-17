"""A starter reserve must help new users without inventing financial data."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

from mysql.connector import OperationalError

from rota_financeira import views


def register(client):
    return client.post(
        "/fazer-cadastro",
        data={
            "nome": "Ana Teste",
            "email": "ana@example.com",
            "senha": "senha-segura-123",
            "confirmar_senha": "senha-segura-123",
        },
    )


def login(client):
    return client.post("/fazer-login", data={"email": "ana@example.com", "senha": "senha-segura-123"})


def test_signup_creates_one_unconfigured_reserve_without_invented_target_or_deadline(client, query_one):
    assert register(client).status_code == 302
    user = query_one("SELECT id, reserva_inicializada FROM usuarios")
    assert user["reserva_inicializada"] == 1
    reserve = query_one("SELECT * FROM metas WHERE usuario_id = %s", (user["id"],))
    assert reserve["nome_meta"] == "Reserva de emergência"
    assert reserve["valor_alvo"] is None
    assert reserve["data_limite"] is None
    assert reserve["valor_atual"] == Decimal("0.00")
    assert query_one("SELECT COUNT(*) AS total FROM metas")["total"] == 1
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 0


def test_signup_rolls_back_the_account_if_default_reserve_creation_fails(client, query_one, monkeypatch):
    original_cursor = views.cursor

    class FailingReserveCursor:
        def __init__(self, current):
            self.current = current

        def execute(self, operation, parameters=None):
            if "INSERT INTO METAS" in " ".join(operation.upper().split()):
                raise OperationalError("Simulated reserve creation failure")
            return self.current.execute(operation, parameters)

        def __getattr__(self, name):
            return getattr(self.current, name)

    @contextmanager
    def failing_cursor(*, write=False):
        with original_cursor(write=write) as current:
            yield FailingReserveCursor(current)

    monkeypatch.setattr(views, "cursor", failing_cursor)
    response = register(client)
    assert response.status_code == 503
    assert query_one("SELECT COUNT(*) AS total FROM usuarios")["total"] == 0
    assert query_one("SELECT COUNT(*) AS total FROM metas")["total"] == 0


def test_legacy_user_receives_reserve_once_and_deletion_is_respected(client, make_user, query_one):
    user_id = make_user(reserve_initialized=False)
    for _ in range(2):
        assert login(client).status_code == 302
        assert client.post("/logout").status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM metas WHERE usuario_id = %s", (user_id,))["total"] == 1
    assert (
        query_one("SELECT reserva_inicializada FROM usuarios WHERE id = %s", (user_id,))[
            "reserva_inicializada"
        ]
        == 1
    )
    reserve_id = query_one("SELECT id FROM metas WHERE usuario_id = %s", (user_id,))["id"]
    assert login(client).status_code == 302
    assert client.post(f"/metas/{reserve_id}/excluir").status_code == 302
    assert client.post("/logout").status_code == 302
    assert login(client).status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM metas WHERE usuario_id = %s", (user_id,))["total"] == 0


def test_legacy_user_existing_emergency_reserve_is_not_duplicated(client, make_user, insert_goal, query_one):
    user_id = make_user(reserve_initialized=False)
    goal_id = insert_goal(user_id, name="Reserva de emergência", target="2500.00", current="150.00")
    assert login(client).status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM metas WHERE usuario_id = %s", (user_id,))["total"] == 1
    existing = query_one("SELECT valor_alvo, valor_atual FROM metas WHERE id = %s", (goal_id,))
    assert existing == {"valor_alvo": Decimal("2500.00"), "valor_atual": Decimal("150.00")}


def test_simultaneous_first_logins_create_only_one_default_reserve(app, make_user, query_one):
    user_id = make_user(reserve_initialized=False)
    clients = [app.test_client() for _ in range(3)]

    def sign_in(client):
        return login(client).status_code

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        assert list(executor.map(sign_in, clients)) == [302] * len(clients)
    assert query_one("SELECT COUNT(*) AS total FROM metas WHERE usuario_id = %s", (user_id,))["total"] == 1


def test_default_reserve_requires_configuration_before_contributions(client, query_one, rendered_context):
    assert register(client).status_code == 302
    assert login(client).status_code == 302
    with rendered_context() as contexts:
        assert client.get("/").status_code == 200
    reserve = contexts[-1]["lista_metas"][0]
    assert reserve["precisa_configurar"] is True
    assert reserve["concluida"] is False
    assert reserve["porcentagem"] == 0
    reserve_id = reserve["id"]
    assert client.post(f"/metas/{reserve_id}/aportar", data={"valor": "25.00"}).status_code == 302
    assert query_one("SELECT valor_atual FROM metas WHERE id = %s", (reserve_id,))["valor_atual"] == Decimal(
        "0"
    )

    response = client.post(
        f"/metas/{reserve_id}/editar",
        data={
            "nome_meta": "Reserva de emergência",
            "valor_alvo": "1200.00",
            "valor_atual": "0.00",
            "data_limite": (date.today() + timedelta(days=365)).isoformat(),
        },
    )
    assert response.status_code == 302
    assert client.post(f"/metas/{reserve_id}/aportar", data={"valor": "25.00"}).status_code == 302
    with rendered_context() as contexts:
        assert client.get("/").status_code == 200
    configured = contexts[-1]["lista_metas"][0]
    assert configured["precisa_configurar"] is False
    assert configured["valor_alvo"] == Decimal("1200.00")
    assert configured["valor_atual"] == Decimal("25.00")
