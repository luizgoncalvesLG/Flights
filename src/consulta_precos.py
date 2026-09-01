"""
Consulta a Data API do Travelpayouts (endpoint "Cheapest Tickets") para as
rotas definidas em config/rotas.py, compara com o menor preço já visto
(histórico no Google Sheets) e reporta oportunidades.

Uso (a partir da raiz do projeto):
    python -m src.consulta_precos
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

from config.rotas import ROTAS
from src import notificacao, planilha

URL_API = "https://api.travelpayouts.com/v1/prices/cheap"


def buscar_menor_oferta(
    origem: str,
    destino: str,
    moeda: str,
    token: str,
    depart_date: Optional[str] = None,
    return_date: Optional[str] = None,
) -> Optional[dict]:
    """Consulta a API e retorna a oferta mais barata encontrada para a rota."""
    parametros = {
        "origin": origem,
        "destination": destino,
        "currency": moeda,
        "token": token,
    }
    if depart_date:
        parametros["depart_date"] = depart_date
    if return_date:
        parametros["return_date"] = return_date

    resposta = requests.get(URL_API, params=parametros, timeout=15)
    resposta.raise_for_status()
    corpo = resposta.json()

    if not corpo.get("success") or not corpo.get("data"):
        return None

    ofertas_destino = corpo["data"].get(destino, {})
    if not ofertas_destino:
        return None

    return min(ofertas_destino.values(), key=lambda oferta: oferta["price"])


def main() -> None:
    load_dotenv()

    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        sys.exit("Defina TRAVELPAYOUTS_TOKEN no arquivo .env (veja .env.example).")
    moeda = os.environ.get("MOEDA", "brl")

    aba = planilha.conectar()
    menores_precos = planilha.carregar_menor_preco_por_rota(aba)

    for rota in ROTAS:
        origem, destino = rota["origem"], rota["destino"]
        chave = f"{origem}-{destino}"

        oferta = buscar_menor_oferta(
            origem,
            destino,
            moeda,
            token,
            depart_date=rota.get("depart_date"),
            return_date=rota.get("return_date"),
        )

        if oferta is None:
            print(f"{chave}: nenhum preço encontrado")
            continue

        preco_atual = oferta["price"]
        menor_ja_visto = menores_precos.get(chave)
        eh_oportunidade = menor_ja_visto is None or preco_atual < menor_ja_visto

        status = "OPORTUNIDADE (novo menor preço)" if eh_oportunidade else "sem novidade"
        referencia = f" | menor até agora: {menor_ja_visto}" if menor_ja_visto is not None else ""
        print(
            f"{chave}: {preco_atual} {moeda.upper()} em {oferta['departure_at']} "
            f"({oferta['airline']} {oferta['flight_number']}) -> {status}{referencia}"
        )

        planilha.registrar_consulta(
            aba,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            origem=origem,
            destino=destino,
            preco=preco_atual,
            moeda=moeda,
            companhia=oferta["airline"],
            voo=str(oferta["flight_number"]),
            data_ida=oferta["departure_at"],
            data_volta=oferta.get("return_at"),
        )

        if eh_oportunidade:
            menores_precos[chave] = preco_atual
            notificacao.enviar_mensagem(
                f"Oportunidade de preço: {origem} -> {destino}\n"
                f"{preco_atual} {moeda.upper()} em {oferta['departure_at']}\n"
                f"Cia: {oferta['airline']} {oferta['flight_number']}"
            )


if __name__ == "__main__":
    main()
