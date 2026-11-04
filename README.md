# Sala de Gestão Estratégica em Saúde

Painel para gestores de saúde, alimentado por APIs e bases públicas. Cobertura nacional: 27 UFs e 5.570 municípios, com o Espírito Santo como amostra de teste das fontes.

## Estado atual
- `robo/sondar_fontes.py`: testa cada fonte a partir do GitHub e grava `dados/sondagem.json`.
- Os módulos só serão construídos sobre as fontes que a sondagem confirmar.

## Rodar a sondagem
GitHub, aba Actions, "Sondar fontes da Sala de Gestao", Run workflow.
Opcional: cadastrar o segredo `PORTAL_TRANSPARENCIA_KEY` (Settings, Secrets and variables, Actions) para testar o Portal da Transparência. A chave nunca vai no código.

## Dados
Somente dados públicos e agregados. Nenhum dado pessoal é coletado ou guardado.
