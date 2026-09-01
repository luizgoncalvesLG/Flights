# Rotas monitoradas pelo agente.
#
# Cada rota é um dicionário com:
#   origem/destino  -> código IATA do aeroporto (obrigatório)
#   depart_date     -> mês (YYYY-MM) ou dia (YYYY-MM-DD) de ida (opcional;
#                       se omitido, a API retorna os próximos preços em cache)
#   return_date     -> mês ou dia de volta (opcional; omitir para busca só de ida)
#
# Edite esta lista com as rotas reais de interesse antes de rodar o script.

ROTAS = [
    {"origem": "GRU", "destino": "LIS"},
    {"origem": "GRU", "destino": "MAD"},
    {"origem": "GRU", "destino": "ROM"},
    {"origem": "GRU", "destino": "MIL"},
]
