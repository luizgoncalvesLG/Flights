# Agente de Monitoramento de Passagens Aéreas Internacionais

## Objetivo
Agente pessoal (não é produto/negócio) para monitorar continuamente preços de
passagens aéreas internacionais e me alertar quando aparecer uma boa
oportunidade. Vou usar o VS Code + Claude Code para desenvolver.

## Decisões já tomadas — não reabrir sem um motivo forte

### Fonte de dados
- **Amadeus Self-Service está DESCARTADA.** A Amadeus encerrou o portal
  self-service para novos desenvolvedores em 17/07/2026. Só resta acesso
  Enterprise, que exige credenciamento IATA/ARC — inviável para projeto
  pessoal. Não sugerir Amadeus como alternativa.
- **Fonte principal: Travelpayouts Data API.** Gratuita, sem exigência de
  tráfego mínimo (MAU) para os endpoints de preço em cache (calendário de
  preços, menor tarifa por rota). Cadastro em travelpayouts.com.
- **Complemento: FlightAPI.io.** Free tier pequeno (20–100 chamadas/mês),
  usar para buscas pontuais que o Travelpayouts não cobre bem.
- Google Flights não tem API pública (a QPX Express foi descontinuada em
  2018). Se algum dia precisarmos desses dados especificamente, a única via
  seria scraping — não é prioridade agora, não sugerir como primeira opção.

### Arquitetura escolhida
1. **Coleta:** script em Python, rodando via GitHub Actions agendado (cron)
   — sem precisar manter servidor próprio ligado.
2. **Armazenamento:** Google Sheets, guardando o histórico de preços por
   rota e data.
3. **Lógica de alerta:** comparar o preço atual com o histórico da própria
   rota (menor preço já visto, ou X% abaixo da média móvel dos últimos 30
   dias). Só notificar quando cruzar esse limite — evitar spam.
4. **Notificação:** Bot do Telegram (criado via @BotFather).
5. **Dashboard:** não é prioridade agora. O próprio Google Sheets já serve
   de visualização inicial.

## Status atual / próximo passo
Etapas 4 a 7 concluídas e testadas ponta a ponta, inclusive rodando de
verdade na nuvem. `src/consulta_precos.py` busca preços de duas formas:
(a) data fixa/sem data, via `v1/prices/cheap`; (b) intervalo de datas +
duração da viagem (campos `data_inicio`/`data_fim`/`dias_viagem` na rota),
via `v1/prices/calendar` consultado mês a mês, ficando com a data mais
barata da janela inteira. `src/planilha.py` grava cada consulta como uma
linha na aba "historico" do Google Sheets (auth via service account) e
calcula o menor preço já visto por chave — rota sozinha, ou rota+duração
quando há `dias_viagem` (preços de estadias diferentes não são
comparáveis). `src/companhias.py` traduz o código IATA da companhia pro
nome conhecido (ex: AZ → ITA Airways, KL → KLM, DT → TAAG Angola) usando
o arquivo de referência público do Travelpayouts (`data/pt/airlines.json`,
não precisa de token). `src/notificacao.py` envia a mensagem de
oportunidade via bot do Telegram (para todos os chat_ids em
`TELEGRAM_CHAT_IDS`, lista separada por vírgula — hoje Luiz e Monica)
sempre que o preço atual é um novo mínimo pra chave, com preço em R$
(separador de milhar), datas de ida e volta em dd/mm/aaaa e
"Cia: X / Voo: Y" em campo separado. Pra descobrir o chat_id de uma nova
pessoa: ela dá `/start` no bot, depois
`GET https://api.telegram.org/bot<TOKEN>/getUpdates` mostra o chat_id nas
mensagens recentes.

**Rotas cadastradas na planilha, não mais em arquivo.** A aba "rotas" da
mesma planilha (colunas: origem, destino, data_inicio, data_fim,
dias_viagem) substituiu `config/rotas.py` (removido do repo). O usuário
adiciona/remove destinos direto editando a planilha — `src/planilha.py`
(`obter_aba_rotas`/`carregar_rotas`) lê essa aba a cada execução; se a
aba não existir ainda, é criada automaticamente com as 4 rotas que
estavam no antigo rotas.py como seed (`ROTAS_INICIAIS`, só usado na
criação — depois disso editar essa constante no código não tem efeito).
Linhas com data_inicio/data_fim/dias_viagem em branco caem no modo "data
fixa/sem data" (endpoint cheapest). Rotas hoje: todas no formato
intervalo+duração, abril-maio/2027, 20 dias — GRU→LIS, MAD→LIS, GRU→ROM,
GRU→MIL.

**Limitação do Travelpayouts e fallback via FlightAPI.io.** O endpoint
`v1/prices/calendar` só devolve preço quando existe cache pra aquela
combinação exata de rota+mês+duração. Confirmado com teste direto: pra
datas muito distantes (7+ meses, ex: abril-maio/2027) em rotas menos
populares (MAD→LIS, GRU→ROM, GRU→MIL com 20 dias), a API **ignora o mês
pedido** e devolve sempre o mesmo conjunto de datas em cache (perto de
hoje) — meu código descarta corretamente por estarem fora do intervalo
pedido, resultando em "nenhum preço encontrado". Não resolve sozinho com
o tempo (testado rodando por 14h+ sem mudança).

Solução: quando isso acontece numa rota de intervalo, `src/flightapi.py`
tenta uma vez o FlightAPI.io (Round Trip API,
`api.flightapi.io/roundtrip/...`) com uma única data representativa
(o início do intervalo + dias_viagem) — não varre o intervalo inteiro,
porque cada chamada custa 2 créditos do free tier (20–100/mês). O
fallback só é tentado de novo a cada 24h por chave (controlado via nova
coluna `fonte` no histórico: "travelpayouts" ou "flightapi", ver
`planilha.calcular_ultima_consulta_flightapi`/`pode_tentar_flightapi`).
API key em `FLIGHTAPI_KEY` (.env local e secret no GitHub).

Dois bugs encontrados e corrigidos durante a implementação:
- A resposta do FlightAPI (formato tipo Skyscanner: itineraries/legs/
  segments/carriers referenciados por id) tem itinerários sem preço
  válido em algumas `pricing_options` — `flightapi.buscar_menor_oferta`
  agora filtra por preços válidos antes de calcular o mínimo.
- Preços do FlightAPI vêm com casas decimais; a planilha (locale BR)
  confundia o ponto decimal com separador de milhar ao ler de volta via
  `get_all_records()` (5472.48 virava 547248 no dict lido, embora a
  célula em si estivesse certa como "5472,48"). Preço agora sempre
  arredondado pra inteiro antes de gravar, como já era o padrão dos
  preços do Travelpayouts.
- Bug separado (não do FlightAPI): múltiplas chamadas de `append_row`
  em sequência rápida (uma por rota, dentro do mesmo loop) colidiam e
  perdiam linhas — só a última rota processada ficava gravada. Corrigido
  acumulando as linhas do histórico durante o loop e gravando todas de
  uma vez com `append_rows` (`planilha.montar_linha_historico` +
  `salvar_historico`) dentro de um `try/finally` em
  `consulta_precos.py`, pra não perder o que já foi coletado mesmo se
  algo falhar no meio da execução.

**Créditos do FlightAPI.io gastos em testes durante essa sessão:**
bastante (~12 chamadas reais de roundtrip × 2 créditos ≈ 24 créditos) —
vale conferir o saldo no dashboard do FlightAPI.io antes de contar com a
cota do mês.

**Actions do workflow:** `actions/checkout` e `actions/setup-python`
atualizadas para `@v7` (estavam em v4/v5, que rodavam sobre Node.js 20 —
depreciado e será REMOVIDO dos runners em 16/09/2026; sem atualizar o
workflow pararia de rodar depois dessa data).
Repositório: github.com/luizgoncalvesLG/Flights (conta dona do repo —
cuidado, há outra conta gh `luizgoncalvesTrampay` na mesma máquina sem
acesso a esse repo). Workflow `.github/workflows/consulta-precos.yml` roda
a cada 3 horas (cron `0 */3 * * *`, em UTC) e também aceita disparo manual
via `workflow_dispatch`. Os segredos ficam em GitHub Secrets
(`TRAVELPAYOUTS_TOKEN`, `GOOGLE_SHEETS_ID`, `GOOGLE_CREDENTIALS_JSON` —
conteúdo inteiro do JSON da service account —, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_IDS`); o workflow recria o arquivo de credenciais a partir
do secret usando `printf` com o valor vindo de `env:` (NÃO usar
`echo "${{ secrets.X }}"` direto dentro de aspas — quebra se o JSON tiver
aspas internas) e valida que o JSON gerado é válido antes de seguir.
Confirmado rodando com sucesso na nuvem (`gh run view`), inclusive com a
busca por intervalo — consultou preços reais, comparou com a planilha e
não disparou notificação à toa.
Próximo passo: etapa 8, deixar rodando 1–2 semanas e ajustar regras de
alerta conforme os resultados reais.

## Roteiro completo
1. [x] Criar conta no Travelpayouts e pegar a API key
2. [x] Definir rotas e regras de alerta de interesse
3. [x] Criar bot do Telegram (@BotFather) e guardar o token
4. [x] Escrever o script de consulta em Python
5. [x] Salvar histórico de preços no Google Sheets
6. [x] Implementar a lógica de comparação e alerta
7. [x] Automatizar com GitHub Actions
8. [ ] Testar e ajustar as regras de alerta por 1–2 semanas  ← estamos aqui

## Evoluções pós-roteiro inicial
- Busca por intervalo de datas + duração da viagem (não estava no roteiro
  original, adicionado depois a pedido do usuário).
- Nomes de companhia aérea legíveis em vez de código IATA.
- Mensagem de notificação reformatada (R$, datas dd/mm/aaaa, Cia/Voo
  separados) e suporte a múltiplos destinatários no Telegram.
- Cadastro de rotas migrado de `config/rotas.py` para a aba "rotas" da
  planilha — usuário gerencia destinos sem precisar editar código.
- Fallback via FlightAPI.io quando o Travelpayouts não tem cache pra
  rota/duração pesquisada (ver seção de limitação acima).

## Convenções do projeto
- Linguagem: Python.
- Segredos (API keys, tokens) NUNCA hardcoded no código. Usar variáveis de
  ambiente localmente (arquivo `.env`, com `.env` no `.gitignore`) e GitHub
  Secrets no workflow do Actions.
- Comentários e mensagens de commit em português.
- Preferência de trabalho: entender a arquitetura/opções antes de partir
  pro código — explicar o raciocínio, não só entregar a solução pronta.
