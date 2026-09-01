"""
Envio de notificações de oportunidade via bot do Telegram, para uma ou
mais pessoas (TELEGRAM_CHAT_IDS).
"""

import os

import requests

URL_ENVIO = "https://api.telegram.org/bot{token}/sendMessage"


def enviar_mensagem(texto: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids_bruto = os.environ.get("TELEGRAM_CHAT_IDS")
    if not token or not chat_ids_bruto:
        raise SystemExit(
            "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_IDS no arquivo .env (veja .env.example)."
        )

    chat_ids = [chat_id.strip() for chat_id in chat_ids_bruto.split(",") if chat_id.strip()]
    for chat_id in chat_ids:
        resposta = requests.post(
            URL_ENVIO.format(token=token),
            data={"chat_id": chat_id, "text": texto},
            timeout=15,
        )
        resposta.raise_for_status()
