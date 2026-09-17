"""Objetivos iniciais, sem inventar valores ou prazos para o usuário."""


def ensure_initial_goal(current, user_id):
    # O marcador também impede que um objetivo excluído volte no próximo login.
    current.execute(
        "UPDATE usuarios SET reserva_inicializada=1 WHERE id=%s AND reserva_inicializada=0",
        (user_id,),
    )
    if current.rowcount != 1:
        return
    current.execute(
        "SELECT id FROM metas WHERE usuario_id=%s AND nome_meta=%s LIMIT 1",
        (user_id, "Reserva de emergência"),
    )
    if current.fetchone() is None:
        current.execute(
            """INSERT INTO metas (usuario_id,nome_meta,valor_alvo,valor_atual,data_limite)
            VALUES (%s,%s,NULL,0,NULL)""",
            (user_id, "Reserva de emergência"),
        )
