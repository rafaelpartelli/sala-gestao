# Receitas municipais e Painel das Organizações (acréscimo ao repositório sala-gestao)

Arquivos novos, nenhum arquivo existente foi alterado.

| Peça | Arquivo | Fonte | Agenda (Brasília) |
|---|---|---|---|
| Receita | `robo/coletar_receita.py` | SICONFI, RREO Anexo 01 | diária, 01:46 |
| Pessoal | `robo/coletar_pessoal.py` | SICONFI, RGF Anexo 01 (Poder Executivo) | junto com a receita |
| Sondagem dos portais estaduais | `robo/sondar_portais_uf.py` + `config/portais_uf.json` | portais de transparência de ES, TO, PA, PE | segunda, 02:10 |
| Sondagem SisCEBAS | `robo/sondar_siscebas.py` | páginas públicas do MS e OpenDataSUS | segunda, 02:10 |

Páginas: `receitas/index.html` (Receitas Municipais) e `organizacoes/index.html` (Painel das Organizações, abas OS de saúde e Entidades CEBAS).

## Como ativar
1. Workflows já em `.github/workflows/` (receita_pessoal.yml e sondar_portais_siscebas.yml).
2. Em Actions, rodar "Coletar receita e pessoal (SICONFI)" (padrão: piloto ES, TO, PA, PE; informar `BR` para o Brasil).
3. Rodar "Sondar portais estaduais e SisCEBAS".
4. Abrir `/receitas/` e `/organizacoes/`.

## Regras
- Só dado público. Nenhuma credencial no código.
- O SisCEBAS exige login do representante legal e o site bloqueia leitura automática (robots.txt). O robô respeita o bloqueio, não entra na área restrita e só procura vias abertas.
- Endereços dos portais estaduais em `config/portais_uf.json` são candidatos e precisam ser validados antes de qualquer coleta de dados.
- Testes: `python3 -I -m unittest discover -s tests` (12 novos testes, valores reais de Vitória/ES, exercício 2025).

## Metas propostas (são metas, não resultados)
- Receita informada em pelo menos 90% dos municípios do piloto.
- Falha da coleta abaixo de 5% (o robô já recusa gravar acima disso).
- Piloto concluído em menos de 30 minutos.

Nota: as sondagens gravam `dados/fontes_portais_uf.json` e `dados/fontes_siscebas.json` (o `.htaccess` bloqueia arquivos `dados/sondagem*`, então esses nomes ficam públicos para a página ler).
