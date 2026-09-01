"""
Consulta a Data API do Travelpayouts para as rotas definidas em
config/rotas.py, compara com o menor preço já visto (histórico no Google
Sheets) e reporta oportunidades.

Cada rota pode ser buscada de duas formas:
- Data fixa (ou sem data): usa o endpoint "Cheapest Tickets"
  (v1/prices/cheap).
- Intervalo de datas + duração da viagem (campos data_inicio, data_fim,
  dias_viagem): usa o endpoint "Price Calendar" (v1/prices/calendar),
  consultando mês a mês dentro do intervalo e ficando com a data mais
  barata encontrada.

Uso (a partir da raiz do projeto):
    python -m src.consulta_precos
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

from config.rotas import ROTAS
from src import companhias, notificacao, planilha

URL_CHEAPEST = "https://api.travelpayouts.com/v1/prices/cheap"
URL_CALENDARIO = "https://api.travelpayouts.com/v1/prices/calendar"


def buscar_menor_oferta(
    origem: str,
    destino: str,
    moeda: str,
    token: str,
    depart_date: Optional[str] = None,
    return_date: Optional[str] = None,
) -> Optional[dict]:
    """Consulta o endpoint "Cheapest Tickets" e retorna a oferta mais
    barata encontrada para a rota."""
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

    resposta = requests.get(URL_CHEAPEST, params=parametros, timeout=15)
    resposta.raise_for_status()
    corpo = resposta.json()

    if not corpo.get("success") or not corpo.get("data"):
        return None

    ofertas_destino = corpo["data"].get(destino, {})
    if not ofertas_destino:
        return None

    return min(ofertas_destino.values(), key=lambda oferta: oferta["price"])


def proximo_mes(dia: date) -> date:
    if dia.month == 12:
        return date(dia.year + 1, 1, 1)
    return date(dia.year, dia.month + 1, 1)


def meses_no_intervalo(data_inicio: str, data_fim: str) -> list[str]:
    """Gera a lista de meses (YYYY-MM) cobertos por um intervalo de datas."""
    atual = date.fromisoformat(data_inicio).replace(day=1)
    fim = date.fromisoformat(data_fim).replace(day=1)

    meses = []
    while atual <= fim:
        meses.append(atual.strftime("%Y-%m"))
        atual = proximo_mes(atual)
    return meses


def buscar_menor_oferta_intervalo(
    origem: str,
    destino: str,
    moeda: str,
    token: str,
    data_inicio: str,
    data_fim: str,
    dias_viagem: Optional[int] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """Percorre, mês a mês, o calendário de preços da rota dentro do
    intervalo (com a duração de viagem fixada, se informada) e retorna a
    (data, oferta) mais barata encontrada em toda a janela."""
    melhor_data = None
    melhor_oferta = None

    for mes in meses_no_intervalo(data_inicio, data_fim):
        parametros = {
            "origin": origem,
            "destination": destino,
            "depart_date": mes,
            "calendar_type": "departure_date",
            "currency": moeda,
            "token": token,
        }
        if dias_viagem:
            parametros["length"] = dias_viagem

        resposta = requests.get(URL_CALENDARIO, params=parametros, timeout=15)
        resposta.raise_for_status()
        corpo = resposta.json()

        if not corpo.get("success") or not corpo.get("data"):
            continue

        for data_str, oferta in corpo["data"].items():
            if not (data_inicio <= data_str <= data_fim):
                continue
            if melhor_oferta is None or oferta["price"] < melhor_oferta["price"]:
                melhor_data = data_str
                melhor_oferta = oferta

    return melhor_data, melhor_oferta


def montar_info_voo(nome_companhia: str, oferta: dict) -> str:
    if oferta.get("flight_number"):
        return f"{nome_companhia} {oferta['flight_number']}"
    return nome_companhia


def main() -> None:
    load_dotenv()

    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        sys.exit("Defina TRAVELPAYOUTS_TOKEN no arquivo .env (veja .env.example).")
    moeda = os.environ.get("MOEDA", "brl")

    aba = planilha.conectar()
    menores_precos = planilha.carregar_menor_preco_por_rota(aba)
    nomes_companhias = companhias.carregar_nomes()

    for rota in ROTAS:
        origem, destino = rota["origem"], rota["destino"]
        dias_viagem = rota.get("dias_viagem")

        if "data_inicio" in rota and "data_fim" in rota:
            data_ida, oferta = buscar_menor_oferta_intervalo(
                origem,
                destino,
                moeda,
                token,
                data_inicio=rota["data_inicio"],
                data_fim=rota["data_fim"],
                dias_viagem=dias_viagem,
            )
        else:
            oferta = buscar_menor_oferta(
                origem,
                destino,
                moeda,
                token,
                depart_date=rota.get("depart_date"),
                return_date=rota.get("return_date"),
            )
            data_ida = oferta["departure_at"] if oferta else None

        chave = planilha.montar_chave(origem, destino, dias_viagem)

        if oferta is None:
            print(f"{chave}: nenhum preço encontrado")
            continue

        preco_atual = oferta["price"]
        menor_ja_visto = menores_precos.get(chave)
        eh_oportunidade = menor_ja_visto is None or preco_atual < menor_ja_visto
        nome_companhia = nomes_companhias.get(oferta["airline"], oferta["airline"])
        info_voo = montar_info_voo(nome_companhia, oferta)

        status = "OPORTUNIDADE (novo menor preço)" if eh_oportunidade else "sem novidade"
        referencia = f" | menor até agora: {menor_ja_visto}" if menor_ja_visto is not None else ""
        print(
            f"{chave}: {preco_atual} {moeda.upper()} em {data_ida} "
            f"({info_voo}) -> {status}{referencia}"
        )

        data_volta = oferta.get("return_at")
        if data_volta is None and dias_viagem:
            data_volta = (date.fromisoformat(data_ida[:10]) + timedelta(days=dias_viagem)).isoformat()

        planilha.registrar_consulta(
            aba,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            origem=origem,
            destino=destino,
            preco=preco_atual,
            moeda=moeda,
            companhia=nome_companhia,
            voo=str(oferta["flight_number"]) if oferta.get("flight_number") else "",
            data_ida=data_ida,
            data_volta=data_volta,
            dias_viagem=dias_viagem,
        )

        if eh_oportunidade:
            menores_precos[chave] = preco_atual
            notificacao.enviar_mensagem(
                f"Oportunidade de preço: {origem} -> {destino}\n"
                f"{preco_atual} {moeda.upper()} em {data_ida}\n"
                f"Cia: {info_voo}"
            )


if __name__ == "__main__":
    main()
