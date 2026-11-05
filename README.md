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
| Planos de saúde | `robo/coletar_ans.py` | ANS, Painel de Dados Abertos | dia 1, após o SIOPS (workflow próprio) |
| Despesa municipal em saúde | `robo/coletar_despesa.py` | SICONFI, DCA Anexo I-E | dia 1, após o SIOPS (workflow próprio) |
| Chikungunya | `robo/coletar_dengue.py` com `DOENCA=chikungunya` | InfoDengue | junto com a dengue |

Os workflows ficam em `.github/workflows/`. Segredo necessário: `PORTAL_TRANSPARENCIA_KEY` (só para emendas). A chave nunca vai no código.

## CNES: natureza, hospitais e equipamentos
O coletor da rede (`coletar_rede.py`) classifica os estabelecimentos pela natureza jurídica (pública, privada com fins lucrativos, privada sem fins lucrativos, que inclui as filantrópicas) e grava a lista de hospitais ativos em `dados/hospitais/<UF>.json`. O coletor `coletar_equipamentos.py` lê os arquivos EQ do FTP do DATASUS e grava `dados/equipamentos.json`. O CNES não informa o CEBAS, então filantrópico aqui significa privado sem fins lucrativos.

## Recursos, gestão estadual e 15% em saúde
- `coletar_recursos.py` lê os arquivos do Radar de Recursos (partelli.pro/fundo) e grava `dados/recursos/<UF>.json`: por município e para o Fundo Estadual, repasses fundo a fundo (Manutenção e Estruturação da rede, valor bruto) e emendas (proposto, empenhado e pago pelo ano da proposta), com a mesma metodologia do Radar. Emendas não se somam aos repasses ordinários.
- `coletar_siops.py` (SIOPS, RREO Anexo 12) grava `dados/siops/<UF>.json` e `dados/siops_resumo.json`: receitas que compõem a base dos 15% (LC 141/2012, art. 6 e 7), mínimo, valor aplicado (empenhado, liquidado e pago) e percentual, por município, no último exercício (5º bimestre) e no atual. Se mais de 5% dos municípios falharem, nada é gravado. Na primeira coleta, 99,1% dos municípios tiveram dado.
- A tela mostra a ficha do município ao escolhê-lo (no filtro ou no mapa), com comparação com o estado, e separa gestão municipal e estadual.

## Agenda (fila diária às 02:35)
O workflow "Coleta diaria (02:35)" (`sondar.yml`) roda todo dia às 02:35 de Brasília (05:35 UTC) e chama os demais em fila, um após o outro: base territorial (só dia 1), notas, emendas, financiamento (com CAUC e transferências), dengue (com chikungunya), CNES (só segunda) e, só no dia 1, Atenção Primária com ANS, SIOPS e despesa (DCA), cada um em workflow próprio para que a falha de um não marque os outros como erro. Se uma etapa falhar, as seguintes continuam. Cada workflow continua disponível para execução manual (Run workflow). A coluna "Agenda" da tabela acima vale para a periodicidade da fonte, e o horário é sempre o da fila.

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

## Mapa, gráficos e jornada
- `js/mapa.js`: mapa por estados (arquivo `js/mapa-brasil.js`, @svg-maps/brazil, CC BY 4.0) e por municípios (malha do IBGE carregada no navegador). Camadas em `js/indicadores.js`, escala por quantis em cinco faixas.
- `js/geo.js`: projeção das malhas e localização. A posição do visitante fica só no navegador.
- `js/jornada.js`: paradas visitadas (guardadas no navegador), perguntas e descobertas calculadas com os dados do território.
- `js/efeitos.js`: animações (respeitam a preferência de reduzir movimento).
