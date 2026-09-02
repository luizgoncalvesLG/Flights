"""
Consulta a Data API do Travelpayouts para as rotas cadastradas na aba
"rotas" da planilha do Google Sheets, compara com o menor preço já visto
(aba "historico") e reporta oportunidades.

Cada rota pode ser buscada de duas formas:
- Data fixa (ou sem data): usa o endpoint "Cheapest Tickets"
  (v1/prices/cheap).
- Intervalo de datas + duração da viagem (campos data_inicio, data_fim,
  dias_viagem): usa o endpoint "Price Calendar" (v1/prices/calendar),
  consultando mês a mês dentro do intervalo e ficando com a data mais
  barata encontrada.

Quando uma rota de intervalo não tem preço em cache no Travelpayouts
(comum para datas muito distantes em rotas menos populares), tenta uma
vez o FlightAPI.io como fallback, com uma única data representativa (o
início do intervalo) — ver src/flightapi.py e pode_tentar_flightapi
abaixo para o controle de frequência (créditos são limitados).

Uso (a partir da raiz do projeto):
    python -m src.consulta_precos
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

from src import companhias, flightapi, notificacao, planilha

URL_CHEAPEST = "https://api.travelpayouts.com/v1/prices/cheap"
URL_CALENDARIO = "https://api.travelpayouts.com/v1/prices/calendar"

SIMBOLOS_MOEDA = {"brl": "R$", "usd": "US$", "eur": "€"}

# O FlightAPI.io cobra créditos por chamada, então o fallback só é
# tentado de novo depois desse intervalo, por chave sem preço.
INTERVALO_MINIMO_FLIGHTAPI = timedelta(hours=24)


def pode_tentar_flightapi(ultima_tentativa: Optional[datetime]) -> bool:
    if not ultima_tentativa:
        return True
    return datetime.now(timezone.utc) - ultima_tentativa >= INTERVALO_MINIMO_FLIGHTAPI


def formatar_preco(preco: float, moeda: str) -> str:
    simbolo = SIMBOLOS_MOEDA.get(moeda.lower(), moeda.upper())
    valor = f"{preco:,.0f}".replace(",", ".")
    return f"{simbolo} {valor}"


def formatar_data_br(data_iso: str) -> str:
    return date.fromisoformat(data_iso[:10]).strftime("%d/%m/%Y")


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

    spreadsheet = planilha.abrir_planilha()
    aba_historico = planilha.obter_aba_historico(spreadsheet)
    aba_rotas = planilha.obter_aba_rotas(spreadsheet)

    rotas = planilha.carregar_rotas(aba_rotas)
    if not rotas:
        sys.exit("Nenhuma rota cadastrada na aba 'rotas' da planilha.")

    registros_historico = planilha.carregar_registros_historico(aba_historico)
    menores_precos = planilha.calcular_menor_preco_por_rota(registros_historico)
    ultimas_tentativas_flightapi = planilha.calcular_ultima_consulta_flightapi(registros_historico)
    nomes_companhias = companhias.carregar_nomes()

    linhas_historico = []

    try:
        _consultar_e_notificar(
            rotas, moeda, token, menores_precos, ultimas_tentativas_flightapi,
            nomes_companhias, linhas_historico,
        )
    finally:
        planilha.salvar_historico(aba_historico, linhas_historico)


def _consultar_e_notificar(
    rotas: list[dict],
    moeda: str,
    token: str,
    menores_precos: dict,
    ultimas_tentativas_flightapi: dict,
    nomes_companhias: dict,
    linhas_historico: list,
) -> None:
    """Consulta cada rota, notifica oportunidades e acumula as linhas de
    histórico em linhas_historico (gravadas em lote pelo chamador, mesmo
    se esta função levantar uma exceção no meio do caminho)."""
    for rota in rotas:
        origem, destino = rota["origem"], rota["destino"]
        dias_viagem = rota.get("dias_viagem")
        fonte = "travelpayouts"

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

        if oferta is None and "data_inicio" in rota and dias_viagem:
            ultima_tentativa = ultimas_tentativas_flightapi.get(chave)
            if pode_tentar_flightapi(ultima_tentativa):
                data_ida_fallback = rota["data_inicio"]
                data_volta_fallback = (
                    date.fromisoformat(data_ida_fallback) + timedelta(days=dias_viagem)
                ).isoformat()
                try:
                    oferta = flightapi.buscar_menor_oferta(
                        origem, destino, data_ida_fallback, data_volta_fallback, moeda
                    )
                except (requests.RequestException, KeyError, ValueError) as erro:
                    print(f"{chave}: falha ao consultar FlightAPI ({erro})")
                    oferta = None
                if oferta:
                    data_ida = oferta["departure_at"]
                    fonte = "flightapi"
            else:
                print(f"{chave}: sem preço no Travelpayouts, fallback FlightAPI aguardando janela de 24h")

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

        linhas_historico.append(
            planilha.montar_linha_historico(
                timestamp=planilha.formatar_timestamp(datetime.now(timezone.utc)),
                origem=origem,
                destino=destino,
                preco=preco_atual,
                moeda=moeda,
                companhia=nome_companhia,
                voo=str(oferta["flight_number"]) if oferta.get("flight_number") else "",
                data_ida=planilha.formatar_data_hora_voo(data_ida),
                data_volta=planilha.formatar_data_hora_voo(data_volta) if data_volta else None,
                dias_viagem=dias_viagem,
                fonte=fonte,
            )
        )

        if eh_oportunidade:
            menores_precos[chave] = preco_atual

            linha_datas = f"saindo em {formatar_data_br(data_ida)}"
            if data_volta:
                linha_datas += f" e retornando em {formatar_data_br(data_volta)}"

            linha_cia = f"Cia: {nome_companhia}"
            if oferta.get("flight_number"):
                linha_cia += f" / Voo: {oferta['flight_number']}"

            notificacao.enviar_mensagem(
                f"Oportunidade de preço: {origem} -> {destino}\n"
                f"{formatar_preco(preco_atual, moeda)} {linha_datas}\n"
                f"{linha_cia}"
            )


if __name__ == "__main__":
    main()
