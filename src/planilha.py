"""
Integração com o Google Sheets: guarda a lista de rotas monitoradas e o
histórico de preços coletados, nas abas "rotas" e "historico" da planilha
configurada em GOOGLE_SHEETS_ID.
"""

import os
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]

NOME_ABA_HISTORICO = "historico"
CABECALHO_HISTORICO = [
    "timestamp",
    "origem",
    "destino",
    "preco",
    "moeda",
    "companhia",
    "voo",
    "data_ida",
    "data_volta",
    "dias_viagem",
]

NOME_ABA_ROTAS = "rotas"
CABECALHO_ROTAS = ["origem", "destino", "data_inicio", "data_fim", "dias_viagem"]
# Rotas usadas para popular a aba na primeira vez que ela é criada — depois
# disso, a planilha é que manda; editar aqui não tem mais efeito.
ROTAS_INICIAIS = [
    ["GRU", "LIS", "2027-04-01", "2027-05-30", 20],
    ["MAD", "LIS", "2027-04-01", "2027-05-30", 20],
    ["GRU", "ROM", "2027-04-01", "2027-05-30", 20],
    ["GRU", "MIL", "2027-04-01", "2027-05-30", 20],
]


def montar_chave(origem: str, destino: str, dias_viagem: Optional[int] = None) -> str:
    """Chave usada para agrupar o histórico. Quando há duração de viagem
    definida, ela entra na chave — preços de estadias diferentes não são
    comparáveis entre si."""
    if dias_viagem:
        return f"{origem}-{destino}-{dias_viagem}d"
    return f"{origem}-{destino}"


def abrir_planilha() -> gspread.Spreadsheet:
    """Autentica com a service account e abre a planilha configurada em
    GOOGLE_SHEETS_ID."""
    caminho_credenciais = os.environ.get(
        "GOOGLE_CREDENTIALS_PATH", "credentials/google_service_account.json"
    )
    id_planilha = os.environ.get("GOOGLE_SHEETS_ID")
    if not id_planilha:
        raise SystemExit("Defina GOOGLE_SHEETS_ID no arquivo .env (veja .env.example).")

    credenciais = Credentials.from_service_account_file(caminho_credenciais, scopes=ESCOPOS)
    cliente = gspread.authorize(credenciais)
    return cliente.open_by_key(id_planilha)


def obter_aba_historico(planilha: gspread.Spreadsheet) -> gspread.Worksheet:
    """Retorna a aba de histórico, criando-a (com cabeçalho) se ainda não
    existir, e atualizando o cabeçalho se novas colunas tiverem sido
    adicionadas."""
    try:
        aba = planilha.worksheet(NOME_ABA_HISTORICO)
        if aba.row_values(1) != CABECALHO_HISTORICO:
            aba.update("A1", [CABECALHO_HISTORICO])
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=NOME_ABA_HISTORICO, rows=1000, cols=len(CABECALHO_HISTORICO)
        )
        aba.append_row(CABECALHO_HISTORICO)

    return aba


def obter_aba_rotas(planilha: gspread.Spreadsheet) -> gspread.Worksheet:
    """Retorna a aba de rotas monitoradas, criando-a com cabeçalho e as
    rotas iniciais se ainda não existir."""
    try:
        aba = planilha.worksheet(NOME_ABA_ROTAS)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(title=NOME_ABA_ROTAS, rows=200, cols=len(CABECALHO_ROTAS))
        aba.append_row(CABECALHO_ROTAS)
        aba.append_rows(ROTAS_INICIAIS)

    return aba


def carregar_rotas(aba: gspread.Worksheet) -> list[dict]:
    """Lê a aba de rotas e retorna a lista de rotas a monitorar. Linhas
    sem origem/destino são ignoradas (permite deixar linhas em branco na
    planilha)."""
    rotas = []
    for registro in aba.get_all_records():
        origem = str(registro.get("origem") or "").strip()
        destino = str(registro.get("destino") or "").strip()
        if not origem or not destino:
            continue

        rota = {"origem": origem, "destino": destino}
        if registro.get("data_inicio") and registro.get("data_fim"):
            rota["data_inicio"] = str(registro["data_inicio"]).strip()
            rota["data_fim"] = str(registro["data_fim"]).strip()
        if registro.get("dias_viagem"):
            rota["dias_viagem"] = int(registro["dias_viagem"])
        rotas.append(rota)

    return rotas


def carregar_menor_preco_por_rota(aba: gspread.Worksheet) -> dict:
    """Lê todo o histórico e retorna o menor preço já visto por chave
    (rota, ou rota+duração quando aplicável — ver montar_chave)."""
    menores: dict = {}
    for registro in aba.get_all_records():
        chave = montar_chave(registro["origem"], registro["destino"], registro.get("dias_viagem") or None)
        preco = registro["preco"]
        if chave not in menores or preco < menores[chave]:
            menores[chave] = preco
    return menores


def registrar_consulta(
    aba: gspread.Worksheet,
    timestamp: str,
    origem: str,
    destino: str,
    preco: float,
    moeda: str,
    companhia: str,
    voo: str,
    data_ida: str,
    data_volta: Optional[str],
    dias_viagem: Optional[int] = None,
) -> None:
    """Acrescenta uma linha de histórico na planilha."""
    aba.append_row(
        [
            timestamp,
            origem,
            destino,
            preco,
            moeda,
            companhia,
            voo,
            data_ida,
            data_volta or "",
            dias_viagem or "",
        ]
    )
