"""Validação no servidor e formatação sem perda de precisão monetária."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from email_validator import EmailNotValidError, validate_email

MAX_MONEY = Decimal("9999999999.99")
MONTHS = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def text_field(value, label, *, minimum=1, maximum=160):
    value = (value or "").strip()
    if not minimum <= len(value) <= maximum or any(ord(char) < 32 for char in value):
        raise ValueError(f"{label} deve ter entre {minimum} e {maximum} caracteres válidos.")
    return value


def email_field(value):
    value = (value or "").strip().lower()
    if len(value) > 254:
        raise ValueError("Informe um e-mail válido.")
    try:
        return validate_email(value, check_deliverability=False).normalized.lower()
    except EmailNotValidError as error:
        raise ValueError("Informe um e-mail válido.") from error


def money_field(value, *, allow_zero=False):
    raw = str(value or "").strip()
    if not re.fullmatch(r"\d{1,10}(?:[.,]\d{1,2})?", raw):
        raise ValueError("Informe um valor válido, com no máximo duas casas decimais.")
    try:
        amount = Decimal(raw.replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("Informe um valor válido.") from error
    if amount > MAX_MONEY or amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError("O valor deve ser maior que zero e não ultrapassar R$ 9.999.999.999,99.")
    return amount.quantize(Decimal("0.01"))


def date_field(value, *, future_allowed=True, past_allowed=True):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
            raise ValueError
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as error:
        raise ValueError("Informe uma data válida.") from error
    if parsed.year < 1900 or parsed.year > 9998:
        raise ValueError("Informe um ano entre 1900 e 9998.")
    if not future_allowed and parsed > date.today():
        raise ValueError("A data da transação não pode estar no futuro.")
    if not past_allowed and parsed < date.today():
        raise ValueError("O prazo da nova meta deve ser hoje ou uma data futura.")
    return parsed


def month_range(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value or ""):
        raise ValueError("Selecione um mês válido.")
    start = date_field(value + "-01")
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def format_currency(value):
    amount = Decimal(str(value or 0))
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(value):
    if not value:
        return "—"
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime("%d/%m/%Y")
