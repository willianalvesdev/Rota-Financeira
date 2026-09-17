"""Entrada da aplicação: python run.py (servidor local sem modo de depuração)."""

import os

from rota_financeira import create_app

app = create_app()

if __name__ == "__main__":
    from waitress import serve

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "5000"))
    print(f"Rota Financeira disponível em http://{host}:{port}", flush=True)
    serve(app, host=host, port=port, threads=4)
