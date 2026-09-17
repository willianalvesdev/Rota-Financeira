"""Rotas de autenticação e operações financeiras sempre limitadas ao usuário."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from hashlib import sha256
from secrets import token_urlsafe

from flask import abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .db import cursor
from .validation import MAX_MONEY, MONTHS, date_field, email_field, money_field, month_range, text_field


def login_required(view):
    @wraps(view)
    def protected(*args, **kwargs):
        if not session.get("usuario_id") or not session.get("auth_token"):
            session.clear()
            return redirect(url_for("login"))
        with cursor() as current:
            current.execute(
                """SELECT u.id, u.nome FROM usuarios u JOIN sessoes s ON s.usuario_id=u.id
                WHERE u.id=%s AND s.token_hash=%s AND s.expira_em > UTC_TIMESTAMP()""",
                (session["usuario_id"], sha256(session["auth_token"].encode()).hexdigest()),
            )
            user = current.fetchone()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        if session.get("usuario_nome") != user["nome"]:
            session["usuario_nome"] = user["nome"]
        return view(*args, **kwargs)

    return protected


def return_to_dashboard():
    month = request.form.get("mes_retorno", date.today().strftime("%Y-%m"))
    try:
        month_range(month)
    except ValueError:
        month = date.today().strftime("%Y-%m")
    return redirect(url_for("index", month=month))


def transaction_values():
    description = text_field(request.form.get("descricao"), "A descrição", maximum=160)
    amount = money_field(request.form.get("valor"))
    kind = request.form.get("tipo")
    if kind not in ("receita", "despesa"):
        raise ValueError("Selecione receita ou despesa.")
    when = date_field(request.form.get("data_transacao"), future_allowed=False)
    return description, amount, kind, when


def goal_values(*, creating=False):
    name = text_field(request.form.get("nome_meta"), "O nome da meta", maximum=120)
    target = money_field(request.form.get("valor_alvo"))
    saved = money_field(request.form.get("valor_atual") or "0", allow_zero=True)
    deadline = date_field(request.form.get("data_limite"), past_allowed=not creating)
    return name, target, saved, deadline


def owned_row(current, table, row_id):
    # Identificadores internos fixos, nunca oriundos do formulário.
    if table not in ("transacoes", "metas"):
        raise ValueError("Tabela não permitida")
    current.execute(
        f"SELECT * FROM {table} WHERE id = %s AND usuario_id = %s FOR UPDATE", (row_id, session["usuario_id"])
    )
    row = current.fetchone()
    if not row:
        abort(404)
    return row


def register_routes(app, limiter):
    dummy_hash = generate_password_hash("senha-inexistente-para-comparacao")

    @app.get("/login")
    def login():
        if session.get("usuario_id"):
            return redirect(url_for("index"))
        return render_template("login.html", valores={})

    @app.get("/cadastro")
    def cadastro():
        if session.get("usuario_id"):
            return redirect(url_for("index"))
        return render_template("cadastro.html", valores={})

    @app.post("/fazer-cadastro")
    @limiter.limit("5 per minute")
    def fazer_cadastro():
        values = {"nome": request.form.get("nome", ""), "email": request.form.get("email", "")}
        try:
            name = text_field(values["nome"], "O nome", minimum=2, maximum=100)
            email = email_field(values["email"])
            password = request.form.get("senha", "")
            if not 8 <= len(password) <= 128 or not password.strip():
                raise ValueError("A senha deve ter entre 8 e 128 caracteres.")
            if password != request.form.get("confirmar_senha"):
                raise ValueError("As senhas não coincidem.")
            password_hash = generate_password_hash(password)
            with cursor(write=True) as current:
                current.execute(
                    "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
                    (name, email, password_hash),
                )
        except ValueError as error:
            flash(str(error), "error")
            return render_template("cadastro.html", valores=values), 422
        except IntegrityError as error:
            if error.errno != 1062:
                raise
            flash("Este e-mail já está cadastrado. Entre com sua conta.", "error")
            return render_template("cadastro.html", valores=values), 422
        flash("Conta criada! Entre para começar sua jornada.", "success")
        return redirect(url_for("login"))

    @app.post("/fazer-login")
    @limiter.limit("10 per minute")
    def fazer_login():
        values = {"email": request.form.get("email", "")}
        password = request.form.get("senha", "")
        user = None
        try:
            email = email_field(values["email"])
            if len(password) > 128:
                raise ValueError
            with cursor() as current:
                current.execute("SELECT id, nome, senha FROM usuarios WHERE email = %s", (email,))
                user = current.fetchone()
            valid_password = check_password_hash(user["senha"] if user else dummy_hash, password)
        except (ValueError, TypeError):
            valid_password = False
        if not user or not valid_password:
            flash("E-mail ou senha incorretos.", "error")
            return render_template("login.html", valores=values), 401
        token = token_urlsafe(32)
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
        with cursor(write=True) as current:
            current.execute(
                "DELETE FROM sessoes WHERE usuario_id=%s AND expira_em <= UTC_TIMESTAMP()", (user["id"],)
            )
            current.execute(
                "INSERT INTO sessoes (token_hash, usuario_id, expira_em) VALUES (%s,%s,%s)",
                (sha256(token.encode()).hexdigest(), user["id"], expires),
            )
        session.clear()
        session.permanent = True
        session["usuario_id"] = user["id"]
        session["usuario_nome"] = user["nome"]
        session["auth_token"] = token
        return redirect(url_for("index"))

    @app.post("/logout")
    def logout():
        if session.get("auth_token") and session.get("usuario_id"):
            with cursor(write=True) as current:
                current.execute(
                    "DELETE FROM sessoes WHERE token_hash=%s AND usuario_id=%s",
                    (sha256(session["auth_token"].encode()).hexdigest(), session["usuario_id"]),
                )
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        selected = request.args.get("month", date.today().strftime("%Y-%m"))
        try:
            start, end = month_range(selected)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))
        search = request.args.get("q", "").strip()[:160]
        kind = request.args.get("tipo", "")
        if kind not in ("", "receita", "despesa"):
            kind = ""
        page = max(1, request.args.get("page", 1, type=int) or 1)
        user_id = session["usuario_id"]
        conditions = "usuario_id = %s AND data_transacao >= %s AND data_transacao < %s"
        parameters = [user_id, start, end]
        if search:
            literal = search.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            conditions += " AND descricao LIKE %s ESCAPE '!'"
            parameters.append(f"%{literal}%")
        if kind:
            conditions += " AND tipo = %s"
            parameters.append(kind)
        with cursor() as current:
            current.execute(
                """SELECT
                COALESCE(SUM(CASE WHEN tipo='receita' THEN valor ELSE 0 END), 0) AS receitas,
                COALESCE(SUM(CASE WHEN tipo='despesa' THEN valor ELSE 0 END), 0) AS despesas
                FROM transacoes WHERE usuario_id=%s AND data_transacao >= %s AND data_transacao < %s""",
                (user_id, start, end),
            )
            totals = current.fetchone()
            current.execute(
                """SELECT COALESCE(SUM(CASE WHEN tipo='receita' THEN valor ELSE -valor END),0)
                AS saldo FROM transacoes WHERE usuario_id=%s""",
                (user_id,),
            )
            balance = current.fetchone()["saldo"]
            current.execute(f"SELECT COUNT(*) AS total FROM transacoes WHERE {conditions}", parameters)
            count = current.fetchone()["total"]
            pages = max(1, (count + 9) // 10)
            page = min(page, pages)
            current.execute(
                f"""SELECT id, descricao, valor, tipo, data_transacao FROM transacoes
                WHERE {conditions} ORDER BY data_transacao DESC, id DESC LIMIT %s OFFSET %s""",
                parameters + [10, (page - 1) * 10],
            )
            transactions = current.fetchall()
            current.execute("SELECT * FROM metas WHERE usuario_id=%s ORDER BY data_limite, id", (user_id,))
            goals = current.fetchall()
            current.execute(
                """SELECT MONTH(data_transacao) AS mes, tipo, SUM(valor) AS total
                FROM transacoes WHERE usuario_id=%s AND data_transacao >= %s AND data_transacao < %s
                GROUP BY MONTH(data_transacao), tipo""",
                (user_id, date(start.year, 1, 1), date(start.year + 1, 1, 1)),
            )
            chart_rows = current.fetchall()
        for goal in goals:
            percentage = goal["valor_atual"] / goal["valor_alvo"] * 100
            goal["porcentagem"] = float(min(Decimal("100"), percentage).quantize(Decimal("0.1")))
            goal["concluida"] = goal["valor_atual"] >= goal["valor_alvo"]
        revenues, expenses = [0.0] * 12, [0.0] * 12
        for row in chart_rows:
            values = revenues if row["tipo"] == "receita" else expenses
            values[row["mes"] - 1] = float(row["total"])
        return render_template(
            "index.html",
            lista_para_html=transactions,
            receitas_html=totals["receitas"],
            despesas_html=totals["despesas"],
            saldo_html=balance,
            lista_metas=goals,
            receitas_grafico=revenues,
            despesas_grafico=expenses,
            mes_selecionado=selected,
            mes_label=f"{MONTHS[start.month - 1]} de {start.year}",
            ano_selecionado=start.year,
            hoje=date.today().isoformat(),
            busca=search,
            tipo_filtro=kind,
            pagina=page,
            paginas=pages,
            total_transacoes=count,
        )

    @app.post("/adicionar-transacao")
    @login_required
    def adicionar_transacao():
        try:
            values = transaction_values()
        except ValueError as error:
            flash(str(error), "error")
            return return_to_dashboard()
        with cursor(write=True) as current:
            current.execute(
                """INSERT INTO transacoes (descricao,valor,tipo,data_transacao,usuario_id)
                VALUES (%s,%s,%s,%s,%s)""",
                (*values, session["usuario_id"]),
            )
        flash("Transação adicionada.", "success")
        return return_to_dashboard()

    @app.post("/transacoes/<int:transacao_id>/editar")
    @login_required
    def editar_transacao(transacao_id):
        with cursor(write=True) as current:
            owned_row(current, "transacoes", transacao_id)
            try:
                values = transaction_values()
            except ValueError as error:
                flash(str(error), "error")
                return return_to_dashboard()
            current.execute(
                """UPDATE transacoes SET descricao=%s,valor=%s,tipo=%s,data_transacao=%s
                WHERE id=%s AND usuario_id=%s""",
                (*values, transacao_id, session["usuario_id"]),
            )
        flash("Transação atualizada.", "success")
        return return_to_dashboard()

    @app.post("/transacoes/<int:transacao_id>/excluir")
    @login_required
    def excluir_transacao(transacao_id):
        with cursor(write=True) as current:
            owned_row(current, "transacoes", transacao_id)
            current.execute(
                "DELETE FROM transacoes WHERE id=%s AND usuario_id=%s", (transacao_id, session["usuario_id"])
            )
        flash("Transação excluída.", "success")
        return return_to_dashboard()

    @app.post("/adicionar-meta")
    @login_required
    def adicionar_meta():
        try:
            values = goal_values(creating=True)
        except ValueError as error:
            flash(str(error), "error")
            return return_to_dashboard()
        with cursor(write=True) as current:
            current.execute(
                """INSERT INTO metas (nome_meta,valor_alvo,valor_atual,data_limite,usuario_id)
                VALUES (%s,%s,%s,%s,%s)""",
                (*values, session["usuario_id"]),
            )
        flash("Meta criada. Um passo mais perto do seu objetivo!", "success")
        return return_to_dashboard()

    @app.post("/metas/<int:meta_id>/editar")
    @login_required
    def editar_meta(meta_id):
        with cursor(write=True) as current:
            owned_row(current, "metas", meta_id)
            try:
                values = goal_values()
            except ValueError as error:
                flash(str(error), "error")
                return return_to_dashboard()
            current.execute(
                """UPDATE metas SET nome_meta=%s,valor_alvo=%s,valor_atual=%s,data_limite=%s
                WHERE id=%s AND usuario_id=%s""",
                (*values, meta_id, session["usuario_id"]),
            )
        flash("Meta atualizada.", "success")
        return return_to_dashboard()

    @app.post("/metas/<int:meta_id>/aportar")
    @login_required
    def adicionar_aporte(meta_id):
        with cursor(write=True) as current:
            goal = owned_row(current, "metas", meta_id)
            try:
                amount = money_field(request.form.get("valor"))
                if goal["valor_atual"] + amount > MAX_MONEY:
                    raise ValueError("Este aporte ultrapassa o valor máximo permitido para a meta.")
            except ValueError as error:
                flash(str(error), "error")
                return return_to_dashboard()
            current.execute(
                "UPDATE metas SET valor_atual=valor_atual+%s WHERE id=%s AND usuario_id=%s",
                (amount, meta_id, session["usuario_id"]),
            )
        flash("Aporte registrado na meta. O saldo das transações não foi alterado.", "success")
        return return_to_dashboard()

    @app.post("/metas/<int:meta_id>/excluir")
    @login_required
    def excluir_meta(meta_id):
        with cursor(write=True) as current:
            owned_row(current, "metas", meta_id)
            current.execute(
                "DELETE FROM metas WHERE id=%s AND usuario_id=%s", (meta_id, session["usuario_id"])
            )
        flash("Meta excluída.", "success")
        return return_to_dashboard()

    @app.get("/testar-banco")
    @login_required
    def testar_banco():
        with cursor() as current:
            current.execute("SELECT 1")
            current.fetchone()
        return {"status": "ok"}
