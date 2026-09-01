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
Etapas 4, 5 e 6 concluídas e testadas ponta a ponta. `src/consulta_precos.py`
consulta o endpoint `v1/prices/cheap` da Data API do Travelpayouts para as
rotas em `config/rotas.py` (GRU→LIS, MAD, ROM, MIL); `src/planilha.py`
grava cada consulta como uma linha na aba "historico" do Google Sheets
(auth via service account, JSON em `credentials/google_service_account.json`,
fora do git) e calcula o menor preço já visto por rota a partir desse
histórico bruto; `src/notificacao.py` envia a mensagem de oportunidade via
bot do Telegram (token e chat ID no `.env`) sempre que o preço atual é um
novo mínimo para a rota. Testes feitos: execução normal não dispara nada
quando não há novidade; teste ponta a ponta inflando temporariamente (e
revertendo depois) o histórico de uma rota confirmou que a notificação
real chega no Telegram só para a rota que teve queda de preço, sem
disparar para as demais — comportamento de "evitar spam" funcionando.
Próximo passo: etapa 7, automatizar com GitHub Actions (cron agendado).

## Roteiro completo
1. [x] Criar conta no Travelpayouts e pegar a API key
2. [x] Definir rotas e regras de alerta de interesse
3. [x] Criar bot do Telegram (@BotFather) e guardar o token
4. [x] Escrever o script de consulta em Python
5. [x] Salvar histórico de preços no Google Sheets
6. [x] Implementar a lógica de comparação e alerta
7. [ ] Automatizar com GitHub Actions  ← estamos aqui
8. [ ] Testar e ajustar as regras de alerta por 1–2 semanas

## Convenções do projeto
- Linguagem: Python.
- Segredos (API keys, tokens) NUNCA hardcoded no código. Usar variáveis de
  ambiente localmente (arquivo `.env`, com `.env` no `.gitignore`) e GitHub
  Secrets no workflow do Actions.
- Comentários e mensagens de commit em português.
- Preferência de trabalho: entender a arquitetura/opções antes de partir
  pro código — explicar o raciocínio, não só entregar a solução pronta.
