"""Compare equivalent year-to-date periods without inventing growth rates."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from rota_financeira import views


def test_year_comparison_uses_equivalent_periods_and_preserves_monthly_balances(
    authenticated_client, user_id, make_user, insert_transaction, rendered_context
):
    entries = [
        ("2023-01-10", "receita", "100.00"),
        ("2023-02-15", "despesa", "150.00"),
        ("2023-05-01", "receita", "2000.00"),
        ("2024-01-10", "receita", "300.10"),
        ("2024-03-10", "despesa", "20.05"),
        ("2024-12-10", "receita", "1000.00"),
    ]
    for day, kind, value in entries:
        insert_transaction(user_id, "Movimentação anual", value, kind, day)
    other_user = make_user("outro@example.com")
    insert_transaction(other_user, "Outro usuário", "999.00", "receita", "2024-01-10")
    with rendered_context() as contexts:
        response = authenticated_client.get("/?month=2024-03&q=sem-resultados&tipo=despesa")
    assert response.status_code == 200
    context = contexts[-1]
    assert context["total_transacoes"] == 0
    assert context["saldo_anual"] == Decimal("1280.05")
    assert context["saldo_ano_anterior"] == Decimal("1950.00")
    assert context["comparacao_atual"] == Decimal("280.05")
    assert context["comparacao_anterior"] == Decimal("-50.00")
    assert context["variacao_anual"] == Decimal("330.05")
    assert Decimal(str(context["percentual_anual"])) == Decimal("660.1")
    assert context["tem_dados_ano_anterior"] is True
    assert context["comparacao_disponivel"] is True
    assert context["comparacao_label"]
    assert context["saldos_mensais"] == [
        Decimal("300.10"),
        Decimal("0"),
        Decimal("-20.05"),
        *([Decimal("0")] * 8),
        Decimal("1000.00"),
    ]
    assert all(isinstance(value, Decimal) for value in context["saldos_mensais"])


@pytest.mark.parametrize("previous_has_data", [False, True])
def test_zero_previous_balance_has_no_infinite_percentage_and_distinguishes_missing_history(
    authenticated_client, user_id, insert_transaction, rendered_context, previous_has_data
):
    insert_transaction(user_id, "Receita atual", "50.00", "receita", "2024-02-10")
    if previous_has_data:
        insert_transaction(user_id, "Entrada anterior", "10.00", "receita", "2023-02-10")
        insert_transaction(user_id, "Saída anterior", "10.00", "despesa", "2023-02-11")
    with rendered_context() as contexts:
        assert authenticated_client.get("/?month=2024-02").status_code == 200
    context = contexts[-1]
    assert context["comparacao_anterior"] == Decimal("0")
    assert context["variacao_anual"] == Decimal("50.00")
    assert context["percentual_anual"] is None
    assert context["tem_dados_ano_anterior"] is previous_has_data


@pytest.mark.parametrize("selected_month", ["2024-02", "2024-10"])
def test_current_year_comparison_cuts_at_today_and_maps_leap_day_to_february_28(
    authenticated_client, user_id, insert_transaction, rendered_context, monkeypatch, selected_month
):
    fixed_date = Mock(wraps=date)
    fixed_date.today.return_value = date(2024, 2, 29)
    monkeypatch.setattr(views, "date", fixed_date)
    entries = [
        ("2023-02-28", "despesa", "10.00"),
        ("2023-03-01", "receita", "200.00"),
        ("2024-01-10", "receita", "10.00"),
        ("2024-02-29", "receita", "20.00"),
        ("2024-03-01", "receita", "500.00"),
    ]
    for day, kind, value in entries:
        insert_transaction(user_id, "Limite do período", value, kind, day)
    with rendered_context() as contexts:
        response = authenticated_client.get("/", query_string={"month": selected_month})
    assert response.status_code == 200
    context = contexts[-1]
    assert context["saldo_anual"] == Decimal("530.00")
    assert context["saldo_ano_anterior"] == Decimal("190.00")
    assert context["comparacao_atual"] == Decimal("30.00")
    assert context["comparacao_anterior"] == Decimal("-10.00")
    assert context["variacao_anual"] == Decimal("40.00")
    assert Decimal(str(context["percentual_anual"])) == Decimal("400.0")


def test_future_year_shows_its_data_without_claiming_a_year_over_year_comparison(
    authenticated_client, user_id, insert_transaction, rendered_context, monkeypatch
):
    fixed_date = Mock(wraps=date)
    fixed_date.today.return_value = date(2024, 6, 15)
    monkeypatch.setattr(views, "date", fixed_date)
    insert_transaction(user_id, "Registro futuro importado", "42.00", "receita", "2027-01-10")
    with rendered_context() as contexts:
        assert authenticated_client.get("/?month=2027-01").status_code == 200
    context = contexts[-1]
    assert context["comparacao_disponivel"] is False
    assert context["variacao_anual"] == Decimal("0")
    assert context["percentual_anual"] is None
    assert context["saldo_anual"] == Decimal("42.00")
    assert context["receitas_grafico"] == pytest.approx([42.0] + [0.0] * 11)
