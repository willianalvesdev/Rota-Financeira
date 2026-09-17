import pytest
from werkzeug.security import check_password_hash


def registration(**changes):
    fields = {
        "nome": "  Ana da Silva  ",
        "email": "  Ana@Example.com  ",
        "senha": "senha-segura-123",
        "confirmar_senha": "senha-segura-123",
    }
    fields.update(changes)
    return fields


def test_registration_hashes_password_and_normalizes_email(client, query_one):
    response = client.post("/fazer-cadastro", data=registration())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    user = query_one("SELECT nome, email, senha FROM usuarios")
    assert user["nome"] == "Ana da Silva"
    assert user["email"] == "ana@example.com"
    assert user["senha"] != "senha-segura-123"
    assert check_password_hash(user["senha"], "senha-segura-123")


def test_duplicate_email_is_case_insensitive(client, make_user, query_one):
    make_user()
    response = client.post("/fazer-cadastro", data=registration(email="ANA@example.COM"))
    assert response.status_code == 422
    assert query_one("SELECT COUNT(*) AS total FROM usuarios")["total"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"nome": " "},
        {"nome": "a" * 101},
        {"email": "nao-e-email"},
        {"senha": "curta", "confirmar_senha": "curta"},
        {"senha": "a" * 129, "confirmar_senha": "a" * 129},
        {"confirmar_senha": "outra-senha"},
    ],
)
def test_invalid_registration_does_not_create_user(client, query_one, changes):
    response = client.post("/fazer-cadastro", data=registration(**changes))
    assert response.status_code == 422
    assert query_one("SELECT COUNT(*) AS total FROM usuarios")["total"] == 0
    assert b"senha-segura-123" not in response.data


def test_login_rejects_wrong_password_and_accepts_normalized_email(client, user_id):
    response = client.post("/fazer-login", data={"email": "ana@example.com", "senha": "incorreta"})
    assert response.status_code == 401
    assert client.get("/").status_code == 302
    response = client.post("/fazer-login", data={"email": " ANA@EXAMPLE.COM ", "senha": "senha-segura-123"})
    assert response.status_code == 302
    assert client.get("/").status_code == 200


def test_logout_requires_post_and_ends_session(authenticated_client):
    assert authenticated_client.get("/logout").status_code == 405
    response = authenticated_client.post("/logout")
    assert response.status_code == 302
    assert authenticated_client.get("/").status_code == 302


def test_logout_revokes_previously_copied_session_cookie(authenticated_client, app):
    original_cookie = authenticated_client.get_cookie("session").value
    assert authenticated_client.post("/logout").status_code == 302

    replay_client = app.test_client()
    replay_client.set_cookie("session", original_cookie)
    response = replay_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_server_expired_session_requires_new_login(authenticated_client, user_id, db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sessoes SET expira_em = %s WHERE usuario_id = %s",
            ("2000-01-01 00:00:00", user_id),
        )
        assert cursor.rowcount == 1

    response = authenticated_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    response = authenticated_client.post(
        "/fazer-login", data={"email": "ana@example.com", "senha": "senha-segura-123"}
    )
    assert response.status_code == 302
    assert authenticated_client.get("/").status_code == 200


@pytest.mark.parametrize("path", ["/login", "/cadastro"])
def test_public_auth_pages_render_without_bootstrap(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"bootstrap" not in response.data.lower()
    assert b"stylesheet" in response.data.lower()
