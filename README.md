# Sala de Gestão Estratégica em Saúde

Painel para gestores de saúde, alimentado por bases públicas. Cobertura nacional: 27 UFs e 5.570 municípios. Público: gestor de saúde (compras e editais ficam no Painel de Editais, voltado ao prestador).

## Como funciona
Coletores em Python (somente biblioteca padrão) rodam no GitHub Actions, gravam arquivos JSON em `dados/` e o site estático (`index.html`, `css/`, `js/`) lê esses arquivos. Cada bloco da tela mostra a fonte e a data da coleta e avisa quando o dado está velho.

| Módulo | Coletor | Fonte | Agenda (Brasília) |
|---|---|---|---|
| Território | `robo/coletar_territorio.py` | SICONFI (entes) | dia 1, 02:17 |
| Dengue | `robo/coletar_dengue.py` | InfoDengue (Fiocruz e FGV), casos estimados | diária, 05:37 |
| Rede assistencial | `robo/coletar_rede.py` | CNES, Dados Abertos do SUS | segunda, 04:23 |
| Financiamento e portarias | `robo/coletar_financiamento.py` | Radar de Recursos (partelli.pro), InvestSUS/FNS | diária 08:41 e sexta 16:41 |
| Emendas da União | `robo/coletar_emendas.py` | Portal da Transparência (chave) | diária, 06:29 |
| Atenção Primária | `robo/coletar_aps.py` | Dados Abertos do SUS (SISAB 2024) | dia 1, 03:17 |
| Notas técnicas | `robo/coletar_notas.py` | CONASS e Ministério da Saúde | 07:11 e 13:11 |
| Leitos | `robo/coletar_leitos.py` | CNES, Leitos SUS (Dados Abertos do SUS) | junto com a rede (segunda) |
| Equipes ativas | `robo/coletar_equipes.py` | CNES, arquivos EP do FTP do DATASUS | junto com a rede (segunda) |
| Profissionais (vínculos) | `robo/coletar_profissionais.py` | CNES, arquivos PF do FTP do DATASUS | junto com a rede (segunda) |
| CAUC | `robo/coletar_cauc.py` | Tesouro Transparente | junto com o financiamento |
| Transferências da União | `robo/coletar_transferencias.py` | Portal da Transparência (CSV mensal, sem chave) | junto com o financiamento |
| Planos de saúde | `robo/coletar_ans.py` | ANS, Painel de Dados Abertos | dia 1, junto com a Atenção Primária |
| Despesa municipal em saúde | `robo/coletar_despesa.py` | SICONFI, DCA Anexo I-E | dia 1, junto com a Atenção Primária |
| Chikungunya | `robo/coletar_dengue.py` com `DOENCA=chikungunya` | InfoDengue | junto com a dengue |

Os workflows ficam em `.github/workflows/`. Segredo necessário: `PORTAL_TRANSPARENCIA_KEY` (só para emendas). A chave nunca vai no código.

## Regras de dados
- Somente dados públicos e agregados. Nenhum dado de pessoa é coletado ou publicado.
- Casos de dengue são estimativas do modelo do InfoDengue, não notificações.
- Emendas: sem nomes de autores. Valores agregados por localidade do gasto.
- Financiamento: valores oficiais nos Painéis InvestSUS do FNS; o painel apenas replica o resumo do Radar de Recursos.
- Agrupamento de tipos de unidade do CNES (campo `TP_UNIDADE`) é do painel e deve ser conferido com a tabela oficial.

- Profissionais: contagem de vínculos (não de pessoas). Nome, CPF e CNS existem no arquivo de origem e nunca são lidos nem gravados.
- Grupos de CBO (profissionais) e tipos de equipe (códigos 70, 71, 73, 74 e 76) devem ser conferidos com as tabelas oficiais.
- CAUC: o arquivo aberto traz só a situação de cada item (regular ou pendente), sem percentual de aplicação.
- Emendas: a localidade do gasto vem como múltipla em mais de 90% do valor, então não há recorte por estado nesta fonte.
- Os arquivos .dbc do DATASUS são lidos por `robo/dbc.py` (Python puro), validado contra o decodificador `blast` original em C.

## Testes
`python3 -I -m unittest discover -s tests` (rodam antes de cada coleta, sem acesso à internet).

## Sondagens
`robo/sondar_fontes.py`, `sondar_r3.py` e `sondar_r4.py` testam as fontes a partir do GitHub e gravam `dados/sondagem*.json` (histórico das rodadas 1 a 7).

## Publicação
O repositório inteiro é o site (raiz = `index.html`). Teste rápido: GitHub Pages (Settings, Pages, branch main, pasta raiz). Produção prevista: partelli.pro/gestor/sala/ por Git deploy da Hostinger. O `.htaccess` esconde `robo/`, `tests/` e arquivos internos.
