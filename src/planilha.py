"""
Integração com o Google Sheets: guarda o histórico de preços coletados,
uma linha por consulta, na aba "historico" da planilha configurada em
GOOGLE_SHEETS_ID.
"""

import os
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]
NOME_ABA = "historico"
CABECALHO = [
    "timestamp",
    "origem",
    "destino",
    "preco",
    "moeda",
    "companhia",
    "voo",
    "data_ida",
    "data_volta",
]


def conectar() -> gspread.Worksheet:
    """Autentica com a service account e retorna a aba de histórico,
    criando a aba e o cabeçalho se ainda não existirem."""
    caminho_credenciais = os.environ.get(
        "GOOGLE_CREDENTIALS_PATH", "credentials/google_service_account.json"
    )
    id_planilha = os.environ.get("GOOGLE_SHEETS_ID")
    if not id_planilha:
        raise SystemExit("Defina GOOGLE_SHEETS_ID no arquivo .env (veja .env.example).")

    credenciais = Credentials.from_service_account_file(caminho_credenciais, scopes=ESCOPOS)
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open_by_key(id_planilha)

    try:
        aba = planilha.worksheet(NOME_ABA)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(title=NOME_ABA, rows=1000, cols=len(CABECALHO))
        aba.append_row(CABECALHO)

    return aba


def carregar_menor_preco_por_rota(aba: gspread.Worksheet) -> dict:
    """Lê todo o histórico e retorna o menor preço já visto por rota
    (chave "ORIGEM-DESTINO")."""
    menores: dict = {}
    for registro in aba.get_all_records():
        chave = f"{registro['origem']}-{registro['destino']}"
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
) -> None:
    """Acrescenta uma linha de histórico na planilha."""
    aba.append_row(
        [timestamp, origem, destino, preco, moeda, companhia, voo, data_ida, data_volta or ""]
    )
