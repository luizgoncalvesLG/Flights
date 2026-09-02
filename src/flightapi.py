"""
Fallback pontual via FlightAPI.io (Round Trip API) para rotas em que o
Travelpayouts não tem preço em cache.

Diferente do Travelpayouts, aqui não existe busca por calendário/intervalo
— cada chamada exige uma data de ida e volta exatas e custa 2 créditos do
free tier (20–100/mês), então é usado com moderação: uma única data
representativa por rota, e só quando ainda não foi tentado nas últimas 24h
(controle feito em consulta_precos.py via o próprio histórico).
"""

import os
from typing import Optional

import requests

URL_ROUNDTRIP = (
    "https://api.flightapi.io/roundtrip/{key}/{origem}/{destino}/"
    "{data_ida}/{data_volta}/1/0/0/Economy/{moeda}"
)


def buscar_menor_oferta(
    origem: str, destino: str, data_ida: str, data_volta: str, moeda: str
) -> Optional[dict]:
    """Consulta uma combinação específica de ida/volta e retorna a oferta
    mais barata encontrada, no mesmo formato usado para as ofertas do
    Travelpayouts (price, airline, flight_number, departure_at, return_at)."""
    api_key = os.environ.get("FLIGHTAPI_KEY")
    if not api_key:
        return None

    url = URL_ROUNDTRIP.format(
        key=api_key,
        origem=origem,
        destino=destino,
        data_ida=data_ida,
        data_volta=data_volta,
        moeda=moeda.upper(),
    )
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    corpo = resposta.json()

    itinerarios = corpo.get("itineraries") or []

    candidatos = []
    for itinerario in itinerarios:
        precos = [
            opcao["price"]["amount"]
            for opcao in itinerario.get("pricing_options", [])
            if opcao.get("price") and "amount" in opcao["price"]
        ]
        if precos:
            candidatos.append((itinerario, min(precos)))

    if not candidatos:
        return None

    melhor_itinerario, melhor_preco = min(candidatos, key=lambda par: par[1])

    legs_por_id = {leg["id"]: leg for leg in corpo.get("legs", [])}
    segmentos_por_id = {seg["id"]: seg for seg in corpo.get("segments", [])}
    companhias_por_id = {c["id"]: c for c in corpo.get("carriers", [])}

    leg_ida = legs_por_id[melhor_itinerario["leg_ids"][0]]
    leg_volta = legs_por_id[melhor_itinerario["leg_ids"][1]]
    primeiro_segmento = segmentos_por_id[leg_ida["segment_ids"][0]]
    companhia = companhias_por_id.get(primeiro_segmento["marketing_carrier_id"], {})

    return {
        # arredondado para inteiro: preços do Travelpayouts também são
        # inteiros, e a planilha (locale BR) confunde ponto decimal com
        # separador de milhar ao ler de volta um valor com casas decimais
        "price": round(melhor_preco),
        "airline": companhia.get("display_code") or companhia.get("name", "?"),
        "flight_number": primeiro_segmento.get("marketing_flight_number"),
        "departure_at": leg_ida["departure"],
        "return_at": leg_volta["departure"],
    }
