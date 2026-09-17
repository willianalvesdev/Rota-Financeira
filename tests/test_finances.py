from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

import pytest


def transaction(**changes):
    fields = {
        "descricao": "Pagamento",
        "valor": "123.45",
        "tipo": "receita",
        "data_transacao": date.today().isoformat(),
        "mes_retorno": date.today().strftime("%Y-%m"),
    }
    fields.update(changes)
    return fields


def goal(**changes):
    fields = {
        "nome_meta": "Reserva de emergência",
        "valor_alvo": "1000.00",
        "valor_atual": "0.00",
        "data_limite": (date.today() + timedelta(days=60)).isoformat(),
        "mes_retorno": date.today().strftime("%Y-%m"),
    }
    fields.update(changes)
    return fields


def test_dashboard_separates_month_year_and_lifetime_balance(
    authenticated_client, user_id, make_user, insert_transaction, rendered_context
):
    insert_transaction(user_id, "Receita anterior", "100.00", "receita", "2023-12-31")
    insert_transaction(user_id, "Salário", "200.10", "receita", "2024-01-10")
    insert_transaction(user_id, "Mercado", "50.05", "despesa", "2024-01-15")
    insert_transaction(user_id, "Conta fevereiro", "20.00", "despesa", "2024-02-10")
    insert_transaction(user_id, "Outro ano", "30.00", "receita", "2025-01-10")
    other = make_user("outro@example.com")
    insert_transaction(other, "Dado privado", "999.00", "receita", "2024-01-10")
    with rendered_context() as contexts:
        response = authenticated_client.get("/?month=2024-01")
    assert response.status_code == 200
    context = contexts[-1]
    assert Decimal(str(context["receitas_html"])) == Decimal("200.10")
    assert Decimal(str(context["despesas_html"])) == Decimal("50.05")
    assert Decimal(str(context["saldo_html"])) == Decimal("260.05")
    assert context["total_transacoes"] == 2
    assert context["mes_selecionado"] == "2024-01"
    assert context["ano_selecionado"] == 2024
    assert context["receitas_grafico"] == pytest.approx([200.10] + [0] * 11)
    assert context["despesas_grafico"] == pytest.approx([50.05, 20] + [0] * 10)
    assert b"Dado privado" not in response.data


def test_search_and_type_filters_do_not_change_financial_totals(
    authenticated_client, user_id, insert_transaction, rendered_context
):
    insert_transaction(user_id, "Salário", "500.00", "receita", "2024-01-10")
    insert_transaction(user_id, "Mercado", "50.00", "despesa", "2024-01-11")
    insert_transaction(user_id, "Mercado extra", "25.00", "despesa", "2024-01-12")
    with rendered_context() as contexts:
        response = authenticated_client.get("/?month=2024-01&q=Mercado&tipo=despesa")
    assert response.status_code == 200
    context = contexts[-1]
    assert context["total_transacoes"] == 2
    assert Decimal(str(context["receitas_html"])) == Decimal("500")
    assert Decimal(str(context["despesas_html"])) == Decimal("75")
    assert all(row["tipo"] == "despesa" for row in context["lista_para_html"])
    assert all("Mercado" in row["descricao"] for row in context["lista_para_html"])


def test_pagination_keeps_order_and_returns_all_transactions(
    authenticated_client, user_id, insert_transaction, rendered_context
):
    expected_ids = {
        insert_transaction(user_id, f"Compra {number:02d}", "1.00", "despesa", "2024-01-10")
        for number in range(35)
    }
    collected = []
    with rendered_context() as contexts:
        assert authenticated_client.get("/?month=2024-01").status_code == 200
    first = contexts[-1]
    assert first["total_transacoes"] == 35
    assert first["paginas"] >= 2
    collected.extend(row["id"] for row in first["lista_para_html"])
    for page in range(2, first["paginas"] + 1):
        with rendered_context() as contexts:
            response = authenticated_client.get(f"/?month=2024-01&page={page}")
        assert response.status_code == 200
        collected.extend(row["id"] for row in contexts[-1]["lista_para_html"])
    assert set(collected) == expected_ids
    assert len(collected) == len(expected_ids)
    assert collected == sorted(collected, reverse=True)


@pytest.mark.parametrize("month", ["not-a-date", "2024-13", "0000-01", "9999-12"])
def test_invalid_month_is_handled_without_server_error(authenticated_client, month):
    response = authenticated_client.get("/", query_string={"month": month})
    assert response.status_code in {200, 302, 400}


def test_transaction_create_edit_delete_preserves_decimal_amount(authenticated_client, user_id, query_one):
    response = authenticated_client.post("/adicionar-transacao", data=transaction(valor="0.10"))
    assert response.status_code == 302
    row = query_one("SELECT * FROM transacoes WHERE usuario_id = %s", (user_id,))
    assert row["valor"] == Decimal("0.10")
    response = authenticated_client.post(
        f"/transacoes/{row['id']}/editar",
        data=transaction(descricao="Almoço", valor="19.99", tipo="despesa"),
    )
    assert response.status_code == 302
    updated = query_one("SELECT * FROM transacoes WHERE id = %s", (row["id"],))
    assert updated["descricao"] == "Almoço"
    assert updated["tipo"] == "despesa"
    assert updated["valor"] == Decimal("19.99")
    assert authenticated_client.post(f"/transacoes/{row['id']}/excluir").status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"valor": "0"},
        {"valor": "-0.01"},
        {"valor": "0.001"},
        {"valor": "NaN"},
        {"valor": "Infinity"},
        {"valor": "10000000000.00"},
        {"tipo": "transferencia"},
        {"descricao": " "},
        {"descricao": "x" * 161},
        {"data_transacao": "2024-02-30"},
        {"data_transacao": (date.today() + timedelta(days=1)).isoformat()},
    ],
)
def test_invalid_transaction_never_inserts(authenticated_client, query_one, changes):
    response = authenticated_client.post("/adicionar-transacao", data=transaction(**changes))
    assert response.status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM transacoes")["total"] == 0


def test_invalid_edit_preserves_existing_transaction(
    authenticated_client, user_id, insert_transaction, query_one
):
    transaction_id = insert_transaction(user_id, "Original", "10.00", "receita", "2024-01-01")
    response = authenticated_client.post(
        f"/transacoes/{transaction_id}/editar", data=transaction(valor="NaN")
    )
    assert response.status_code == 302
    row = query_one("SELECT descricao, valor FROM transacoes WHERE id = %s", (transaction_id,))
    assert row == {"descricao": "Original", "valor": Decimal("10.00")}


def test_goals_create_edit_contribute_and_delete(authenticated_client, user_id, query_one):
    assert authenticated_client.post("/adicionar-meta", data=goal()).status_code == 302
    row = query_one("SELECT * FROM metas WHERE usuario_id = %s", (user_id,))
    assert row["valor_atual"] == Decimal("0.00")
    assert row["valor_alvo"] == Decimal("1000.00")
    goal_id = row["id"]
    response = authenticated_client.post(
        f"/metas/{goal_id}/editar",
        data=goal(nome_meta="Férias", valor_alvo="2000.00", valor_atual="0.10"),
    )
    assert response.status_code == 302
    for _ in range(3):
        assert (
            authenticated_client.post(f"/metas/{goal_id}/aportar", data={"valor": "0.10"}).status_code == 302
        )
    updated = query_one("SELECT * FROM metas WHERE id = %s", (goal_id,))
    assert updated["nome_meta"] == "Férias"
    assert updated["valor_atual"] == Decimal("0.40")
    assert authenticated_client.post(f"/metas/{goal_id}/excluir").status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM metas")["total"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"nome_meta": "x" * 121},
        {"valor_alvo": "0"},
        {"valor_alvo": "NaN"},
        {"valor_atual": "-0.01"},
        {"valor_atual": "0.001"},
        {"data_limite": (date.today() - timedelta(days=1)).isoformat()},
    ],
)
def test_invalid_goal_does_not_insert(authenticated_client, query_one, changes):
    response = authenticated_client.post("/adicionar-meta", data=goal(**changes))
    assert response.status_code == 302
    assert query_one("SELECT COUNT(*) AS total FROM metas")["total"] == 0


def test_goal_can_be_edited_after_deadline(authenticated_client, user_id, insert_goal, query_one):
    past = date.today() - timedelta(days=1)
    goal_id = insert_goal(user_id, deadline=past)
    response = authenticated_client.post(
        f"/metas/{goal_id}/editar", data=goal(nome_meta="Meta revisada", data_limite=past.isoformat())
    )
    assert response.status_code == 302
    assert query_one("SELECT nome_meta FROM metas WHERE id = %s", (goal_id,))["nome_meta"] == "Meta revisada"


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "0.001", "10000000000"])
def test_invalid_contribution_keeps_goal_unchanged(
    authenticated_client, user_id, insert_goal, query_one, value
):
    goal_id = insert_goal(user_id, current="15.20")
    response = authenticated_client.post(f"/metas/{goal_id}/aportar", data={"valor": value})
    assert response.status_code == 302
    assert query_one("SELECT valor_atual FROM metas WHERE id = %s", (goal_id,))["valor_atual"] == Decimal(
        "15.20"
    )


def test_contribution_overflow_is_rejected_without_data_loss(
    authenticated_client, user_id, insert_goal, query_one
):
    goal_id = insert_goal(user_id, target="9999999999.99", current="9999999999.98")
    response = authenticated_client.post(f"/metas/{goal_id}/aportar", data={"valor": "0.02"})
    assert response.status_code == 302
    assert query_one("SELECT valor_atual FROM metas WHERE id = %s", (goal_id,))["valor_atual"] == Decimal(
        "9999999999.98"
    )


def test_simultaneous_contributions_are_not_lost(app, user_id, insert_goal, query_one):
    goal_id = insert_goal(user_id)
    clients = [app.test_client() for _ in range(6)]
    for client in clients:
        assert (
            client.post(
                "/fazer-login", data={"email": "ana@example.com", "senha": "senha-segura-123"}
            ).status_code
            == 302
        )

    def contribute(client):
        return client.post(f"/metas/{goal_id}/aportar", data={"valor": "0.10"}).status_code

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        assert list(executor.map(contribute, clients)) == [302] * len(clients)
    assert query_one("SELECT valor_atual FROM metas WHERE id = %s", (goal_id,))["valor_atual"] == Decimal(
        "0.60"
    )
