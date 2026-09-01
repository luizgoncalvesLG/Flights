# Rotas monitoradas pelo agente.
#
# Cada rota é um dicionário com origem/destino (código IATA, obrigatório)
# e pode ser buscada de duas formas:
#
# 1) Data fixa (ou sem data) — consulta o menor preço em cache pra rota:
#      {"origem": "GRU", "destino": "LIS"}
#      {"origem": "GRU", "destino": "LIS", "depart_date": "2027-02", "return_date": "2027-03"}
#
# 2) Intervalo de datas + duração da viagem — varre mês a mês o intervalo
#    e fica com a data mais barata encontrada:
#      {
#          "origem": "GRU",
#          "destino": "LIS",
#          "data_inicio": "2027-02-01",
#          "data_fim": "2027-05-30",
#          "dias_viagem": 20,
#      }
#    "dias_viagem" é opcional (omitir busca só ida); quando informado,
#    entra também na chave do histórico (preços de estadias diferentes
#    não são comparáveis entre si).
#
# Edite esta lista com as rotas reais de interesse.

ROTAS = [
    {"origem": "GRU", "destino": "LIS"},
    {"origem": "GRU", "destino": "MAD"},
    {"origem": "GRU", "destino": "ROM"},
    {"origem": "GRU", "destino": "MIL"},
    {
        "origem": "GRU",
        "destino": "LIS",
        "data_inicio": "2027-02-01",
        "data_fim": "2027-05-30",
        "dias_viagem": 20,
    },
]
