# Sala de Gestão Estratégica em Saúde

Painel para gestores de saúde, alimentado por APIs e bases públicas. Cobertura nacional: 27 UFs e 5.570 municípios, com o Espírito Santo como amostra de teste das fontes.

## Estado atual
- `robo/sondar_fontes.py`: testa cada fonte a partir do GitHub. A rodada 1 gravou `dados/sondagem.json`; a rodada 2 grava `dados/sondagem_r2.json` (inclui teste de volume do InfoDengue e a estrutura do arquivo do CNES).
- `robo/sondar_r3.py` (rodada 3): especificações de API (MS e Transferegov), paginação do RREO, teste de 500 municípios no InfoDengue, SINASC, Atenção Primária (indicadores, e-Gestor APS, SISAB) e radar de notas técnicas. Grava `dados/sondagem_r3.json`.
- Escopo: a sala é para o **gestor de saúde**. Compras e editais (PNCP) ficam no Painel de Editais, voltado ao prestador.
- A rodada 3 também sonda: Portal da Transparência da União (CSV e API), portais estaduais (ES, SP, PR, MG, PE), FNS e a ligação com os dados já coletados no Radar de Recursos (partelli.pro/gestor/recursos).
- `robo/sondar_r4.py` (rodada 4): especificações de API (Transferegov, MS, e-Gestor APS), padrão dos arquivos do Portal da Transparência, anexo de saúde do RREO, arquivos dos conjuntos do Dados Abertos SUS, notas técnicas via WordPress e estrutura dos arquivos do Radar de Recursos. Grava `dados/sondagem_r4.json`.
- `robo/coletar_territorio.py`: base territorial (27 UFs e 5.570 municípios) a partir do SICONFI. Grava `dados/territorio.json`. Roda todo dia 1 às 02:17 (Brasília) e sob demanda.
- Testes offline em `tests/` (rodam antes de cada coleta).
- Os módulos só serão construídos sobre as fontes que a sondagem confirmar.

## Rodar a sondagem
GitHub, aba Actions, "Sondar fontes da Sala de Gestao (rodada 3)", Run workflow. A rodada 3 leva de 15 a 25 minutos (teste de volume do InfoDengue).
Depois, "Coletar base territorial", Run workflow.
Opcional: cadastrar o segredo `PORTAL_TRANSPARENCIA_KEY` (Settings, Secrets and variables, Actions) para testar o Portal da Transparência. A chave nunca vai no código.

## Dados
Somente dados públicos e agregados. Nenhum dado pessoal é coletado ou guardado.
