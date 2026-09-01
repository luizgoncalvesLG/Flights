"""
Nomes de companhias aéreas a partir do arquivo de referência público do
Travelpayouts (não precisa de token).
"""

import requests

URL_COMPANHIAS = "https://api.travelpayouts.com/data/pt/airlines.json"


def carregar_nomes() -> dict:
    """Retorna um dicionário {código IATA: nome da companhia}. Em caso de
    falha na consulta, retorna um dicionário vazio — o chamador usa o
    código como nome de fallback."""
    try:
        resposta = requests.get(URL_COMPANHIAS, timeout=15)
        resposta.raise_for_status()
        companhias = resposta.json()
    except requests.RequestException:
        return {}

    nomes = {}
    for companhia in companhias:
        traducoes = companhia.get("name_translations") or {}
        nome = companhia.get("name") or traducoes.get("pt") or traducoes.get("en")
        if nome:
            nomes[companhia["code"]] = nome
    return nomes
