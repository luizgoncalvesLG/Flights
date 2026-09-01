"""
Envio de notificações de oportunidade via bot do Telegram.
"""

import os

import requests

URL_ENVIO = "https://api.telegram.org/bot{token}/sendMessage"


def enviar_mensagem(texto: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit(
            "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no arquivo .env (veja .env.example)."
        )

    resposta = requests.post(
        URL_ENVIO.format(token=token),
        data={"chat_id": chat_id, "text": texto},
        timeout=15,
    )
    resposta.raise_for_status()
