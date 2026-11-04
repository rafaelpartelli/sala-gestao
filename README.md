# Sala de Gestão Estratégica em Saúde

Painel para gestores de saúde, alimentado por APIs e bases públicas. Cobertura nacional: 27 UFs e 5.570 municípios, com o Espírito Santo como amostra de teste das fontes.

## Estado atual
- `robo/sondar_fontes.py`: testa cada fonte a partir do GitHub. A rodada 1 gravou `dados/sondagem.json`; a rodada 2 grava `dados/sondagem_r2.json` (inclui teste de volume do InfoDengue e a estrutura do arquivo do CNES).
- Os módulos só serão construídos sobre as fontes que a sondagem confirmar.

## Rodar a sondagem
GitHub, aba Actions, "Sondar fontes da Sala de Gestao", Run workflow.
Opcional: cadastrar o segredo `PORTAL_TRANSPARENCIA_KEY` (Settings, Secrets and variables, Actions) para testar o Portal da Transparência. A chave nunca vai no código.

## Dados
Somente dados públicos e agregados. Nenhum dado pessoal é coletado ou guardado.
