import {UF_NOMES, inteiro, decimal, pct, moeda, dataBR, el, limpar, seguro, carregar, verTabela} from './util.js';
import {ranking, pilhaNiveis, miniserie, NIVEIS} from './graficos.js';

const D = {};       // dados carregados
const S = {uf: 'BR', mun: '', anoEm: null, tema: 'Todos', fonteNota: 'Todas', nNotas: 15};
const $ = id => document.getElementById(id);
const ufsOrdenadas = () => Object.keys(UF_NOMES).sort((a, b) => UF_NOMES[a].localeCompare(UF_NOMES[b], 'pt-BR'));
const dias = iso => iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 864e5) : null;

function indisponivel(no, texto) {
  limpar(no).append(el('p', {class: 'indisponivel'}, texto || 'Dados ainda não coletados para este bloco.'));
}
const aviso = txt => el('p', {class: 'aviso', role: 'note'}, txt);
const kpi = (rot, val, nota) => el('div', {class: 'kpi'}, el('div', {class: 'rot'}, rot), el('div', {class: 'val'}, val), nota ? el('div', {class: 'nota'}, nota) : null);
const somaUF = (obj, campo, ufs) => ufs.reduce((s, u) => s + (obj?.[u]?.[campo] || 0), 0);
const ufsAlvo = () => S.uf === 'BR' ? Object.keys(UF_NOMES) : [S.uf];
const nomeTerritorio = () => S.mun ? (D.munAtual?.nome || 'Município') : (S.uf === 'BR' ? 'Brasil' : UF_NOMES[S.uf]);
const semana = se => se ? `${String(se).slice(4)}/${String(se).slice(0, 4)}` : 'sem dado';

// ---------- carga ----------
async function carregarBase() {
  const [t, dr, rr, fin, em, aps, notas, port] = await Promise.all(['dados/territorio.json', 'dados/dengue_resumo.json', 'dados/rede_resumo.json', 'dados/financiamento.json', 'dados/emendas.json', 'dados/aps_meta.json', 'dados/notas.json', 'dados/portarias.json'].map(carregar));
  Object.assign(D, {terr: t, dengueRes: dr, redeRes: rr, fin, em, aps, notas, port});
  const n = [dr, rr, fin, em, aps, notas, port].filter(Boolean).length;
  $('selo').textContent = `Fontes com dados: ${n} de 7. Cada bloco mostra a data da sua coleta.`;
}

function montarFiltros() {
  const selUF = $('selUF');
  ufsOrdenadas().forEach(u => selUF.append(el('option', {value: u}, `${UF_NOMES[u]} (${u})`)));
  selUF.addEventListener('change', () => { S.uf = selUF.value; S.mun = ''; D.munAtual = null; preencherMun(); render(); });
  $('selMun').addEventListener('change', e => {
    S.mun = e.target.value;
    D.munAtual = D.terr?.municipios.find(m => m.cod === S.mun) || null;
    render();
  });
}
function preencherMun() {
  const sel = limpar($('selMun'));
  sel.append(el('option', {value: ''}, 'Todos os municípios'));
  if (S.uf === 'BR' || !D.terr) { sel.disabled = true; return; }
  D.terr.municipios.filter(m => m.uf === S.uf).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
    .forEach(m => sel.append(el('option', {value: m.cod}, m.nome)));
  sel.disabled = false;
}

// ---------- resumo ----------
async function rResumo() {
  const alvo = limpar($('kpis')), ufs = ufsAlvo();
  if (!D.terr) return indisponivel(alvo, 'Base territorial indisponível.');
  const k = [];
  if (S.mun) {
    const m = D.munAtual;
    k.push(kpi('População (SICONFI)', inteiro(m.pop), m.capital ? 'Capital do estado' : null));
    const dg = await dengueUF(S.uf), linha = dg?.m.find(x => x[0] === S.mun);
    if (linha && linha[2]) k.push(kpi('Dengue: nível de alerta', 'Nível ' + linha[2], `Semana ${semana(dg.se)}`));
    const rd = await redeUF(S.uf), r = rd?.m?.[S.mun];
    if (r) k.push(kpi('Estabelecimentos ativos', inteiro(r.ativos), 'CNES'));
  } else {
    const pop = ufs.reduce((s, u) => s + (D.terr.por_uf[u]?.pop_soma || 0), 0);
    k.push(kpi('Municípios', inteiro(ufs.reduce((s, u) => s + (D.terr.por_uf[u]?.municipios || 0), 0))));
    k.push(kpi('População', inteiro(pop), 'Estimativa publicada no SICONFI'));
    if (D.fin) {
      const f = D.fin.dados.uf;
      k.push(kpi('Repasses fundo a fundo no ano', moeda(somaUF(f, 'fb', ufs)), `Ano ${f[ufs[0]]?.anoFaf}`));
      k.push(kpi('Saldo em contas dos fundos', moeda(somaUF(f, 's', ufs)), `Em ${f[ufs[0]]?.saldoData}`));
    }
    if (D.redeRes) k.push(kpi('Estabelecimentos ativos', inteiro(somaUF(D.redeRes.ufs, 'ativos', ufs)), 'CNES'));
    if (D.dengueRes) {
      const alto = ufs.reduce((s, u) => s + (+D.dengueRes.ufs[u]?.niveis?.['3'] || 0) + (+D.dengueRes.ufs[u]?.niveis?.['4'] || 0), 0);
      k.push(kpi('Municípios em nível 3 ou 4 de dengue', inteiro(alto), 'Semana mais recente'));
    }
  }
  alvo.append(...k);
}

// ---------- dengue ----------
const dengueUF = uf => uf === 'BR' ? null : carregar(`dados/dengue/${uf}.json`);
const redeUF = uf => uf === 'BR' ? null : carregar(`dados/rede/${uf}.json`);

async function rDengue() {
  const alvo = limpar($('dengue')), fonte = $('fonte-dengue');
  if (!D.dengueRes) { fonte.textContent = ''; return indisponivel(alvo); }
  const r = D.dengueRes, ufs = ufsAlvo();
  const d = dias(r.gerado_em);
  fonte.textContent = `Fonte: ${r.fonte}. Coleta em ${dataBR(r.gerado_em)}.`;
  if (d != null && d > 3) alvo.append(aviso(`Atenção: a última coleta de dengue tem ${d} dias.`));
  if (!S.mun) {
    const niveis = {};
    ufs.forEach(u => NIVEIS.forEach(n => { niveis[n.k] = (niveis[n.k] || 0) + (+r.ufs[u]?.niveis?.[n.k] || 0); }));
    alvo.append(el('h3', null, `Municípios por nível de alerta: ${nomeTerritorio()}`), pilhaNiveis(niveis));
  }
  alvo.append(el('p', {class: 'fonte'}, 'Níveis do InfoDengue: 1 verde, 2 amarelo, 3 laranja e 4 vermelho. Casos são estimativas do modelo.'));

  if (S.uf === 'BR') {
    const lin = ufs.map(u => { const x = r.ufs[u]; const alto = (+x?.niveis?.['3'] || 0) + (+x?.niveis?.['4'] || 0); return {u, alto, mun: x?.municipios || 0, casos: x?.casos_est_semana || 0}; })
      .filter(x => x.mun).sort((a, b) => b.alto / b.mun - a.alto / a.mun);
    alvo.append(el('h3', null, 'Estados com maior proporção de municípios em nível 3 ou 4'),
      ranking(lin.slice(0, 10).map(x => ({nome: UF_NOMES[x.u], valor: x.alto / x.mun, rotulo: `${pct(x.alto / x.mun, 0)} (${x.alto} de ${x.mun})`})), {max: 1}),
      verTabela('Ver os 27 estados em tabela', ['Estado', 'Municípios', 'Nível 3 ou 4', 'Casos estimados na semana'], lin.map(x => [UF_NOMES[x.u], inteiro(x.mun), inteiro(x.alto), inteiro(x.casos)]), [1, 2, 3]));
    return;
  }
  const dg = await dengueUF(S.uf);
  if (!dg) return alvo.append(aviso('Detalhe por município ainda não coletado para este estado.'));
  alvo.append(el('p', {class: 'fonte'}, `Semana epidemiológica mais recente: ${semana(dg.se)}.`));
  if (S.mun) {
    const x = dg.m.find(l => l[0] === S.mun);
    if (!x || !x[2]) return alvo.append(aviso('Sem dado de dengue para este município na semana mais recente.'));
    const n = NIVEIS.find(v => v.k === String(x[2]));
    alvo.append(el('div', {class: 'cartao-mun'}, el('h3', null, x[1]),
      el('span', {class: 'selonivel ' + n.cls}, n.nome),
      el('p', null, `Casos estimados: ${inteiro(x[4])} (notificados: ${inteiro(x[3])}). Incidência: ${decimal(x[5])} por 100 mil habitantes. Rt: ${decimal(x[6], 2)}.`),
      miniserie(x[7] || []), el('p', {class: 'fonte'}, 'Casos estimados nas últimas 8 semanas.')));
    return;
  }
  const top = dg.m.filter(l => l[5] != null).sort((a, b) => b[5] - a[5]).slice(0, 10);
  alvo.append(el('h3', null, 'Dez maiores incidências (casos estimados por 100 mil habitantes)'),
    ranking(top.map(l => ({nome: l[1], valor: l[5], rotulo: decimal(l[5], 0)}))),
    verTabela('Ver todos os municípios em tabela', ['Município', 'Nível', 'Casos estimados', 'Incidência por 100 mil', 'Rt'],
      dg.m.slice().sort((a, b) => a[1].localeCompare(b[1], 'pt-BR')).map(l => [l[1], l[2] ?? 'sem dado', inteiro(l[4]), decimal(l[5]), decimal(l[6], 2)]), [1, 2, 3, 4]));
}

// ---------- rede ----------
async function rRede() {
  const alvo = limpar($('rede')), fonte = $('fonte-rede');
  if (!D.redeRes) { fonte.textContent = ''; return indisponivel(alvo); }
  const r = D.redeRes, ufs = ufsAlvo();
  fonte.textContent = `Fonte: ${r.fonte}. Coleta em ${dataBR(r.gerado_em)}. Contagem de estabelecimentos ativos cadastrados, não de leitos nem de equipes.`;
  let grupos = {}, esfera = {}, ativos = 0, total = 0;
  if (S.mun) {
    const rd = await redeUF(S.uf), m = rd?.m?.[S.mun];
    if (!m) return alvo.append(aviso('Sem estabelecimentos registrados para este município.'));
    grupos = m.grupos; esfera = m.esfera; ativos = m.ativos; total = m.total;
  } else {
    ufs.forEach(u => { const x = r.ufs[u]; if (!x) return; ativos += x.ativos; total += x.total;
      for (const [k, v] of Object.entries(x.grupos)) grupos[k] = (grupos[k] || 0) + v;
      for (const [k, v] of Object.entries(x.esfera)) esfera[k] = (esfera[k] || 0) + v; });
  }
  const ord = o => Object.entries(o).sort((a, b) => b[1] - a[1]).map(([nome, v]) => ({nome, valor: v, rotulo: inteiro(v)}));
  alvo.append(el('p', null, `${nomeTerritorio()}: ${inteiro(ativos)} estabelecimentos ativos (${inteiro(total)} cadastrados, incluindo desabilitados).`),
    el('div', {class: 'grade2'},
      el('div', null, el('h3', null, 'Por tipo de unidade'), ranking(ord(grupos))),
      el('div', null, el('h3', null, 'Por esfera administrativa'), ranking(ord(esfera)))),
    verTabela('Ver em tabela', ['Tipo de unidade', 'Estabelecimentos ativos'], ord(grupos).map(g => [g.nome, g.rotulo]), [1]));
}

// ---------- financiamento ----------
async function rFin() {
  const alvo = limpar($('fin')), fonte = $('fonte-fin');
  if (!D.fin) { fonte.textContent = ''; return indisponivel(alvo); }
  const f = D.fin.dados.uf, ufs = ufsAlvo(), meta = D.fin.dados.meta;
  fonte.textContent = `Fonte: ${D.fin.fonte}. Extração do InvestSUS em ${meta.gerado}. Baixado em ${dataBR(D.fin.baixado_em)}. Valores oficiais nos Painéis InvestSUS do FNS.`;
  const dd = dias(D.fin.baixado_em);
  if (dd != null && dd > 10) alvo.append(aviso(`Atenção: os dados de financiamento foram baixados há ${dd} dias.`));
  if (S.mun) {
    alvo.append(el('p', null, 'O detalhe por município (repasses, saldos e emendas) está no Radar de Recursos. ', el('a', {href: 'https://partelli.pro/gestor/recursos/'}, 'Abrir o Radar de Recursos'), '.'));
    return;
  }
  const x = ufs.map(u => f[u]).filter(Boolean), s = c => x.reduce((a, b) => a + (b[c] || 0), 0);
  alvo.append(el('div', {class: 'kpis'},
    kpi('Repasses fundo a fundo', moeda(s('fb')), `Ano ${x[0].anoFaf}`),
    kpi('Parte do governo estadual', moeda(s('fbEst')), 'Dentro do total de repasses'),
    kpi('Saldo em contas', moeda(s('s')), `Em ${x[0].saldoData}`),
    kpi('Emendas: proposta', moeda(s('ep')), `Ano ${x[0].anoEm}`),
    kpi('Emendas: empenhado', moeda(s('ee'))),
    kpi('Emendas: pago', moeda(s('eg')), s('ep') ? pct(s('eg') / s('ep'), 0) + ' da proposta' : null)));
  if (S.uf === 'BR') {
    const lin = ufs.map(u => ({u, v: f[u]?.pop ? f[u].fb / f[u].pop : null})).filter(l => l.v != null).sort((a, b) => b.v - a.v);
    alvo.append(el('h3', null, 'Dez estados com maior repasse fundo a fundo por habitante no ano'),
      ranking(lin.slice(0, 10).map(l => ({nome: UF_NOMES[l.u], valor: l.v, rotulo: 'R$ ' + decimal(l.v, 0)}))),
      verTabela('Ver os 27 estados em tabela', ['Estado', 'Municípios', 'Repasses', 'Saldo', 'Emendas pagas'], ufs.map(u => f[u] && [UF_NOMES[u], inteiro(f[u].mun), moeda(f[u].fb), moeda(f[u].s), moeda(f[u].eg)]).filter(Boolean), [1, 2, 3, 4]));
  } else {
    alvo.append(el('p', {class: 'fonte'}, `${f[S.uf].mun} municípios e o governo estadual. Detalhe por município no `, el('a', {href: 'https://partelli.pro/gestor/recursos/'}, 'Radar de Recursos'), '.'));
  }
}

// ---------- emendas da Uniao ----------
async function rEm() {
  const alvo = limpar($('em')), fonte = $('fonte-em');
  if (!D.em) { fonte.textContent = ''; return indisponivel(alvo, 'Dados ainda não coletados. Este bloco exige a chave do Portal da Transparência no GitHub.'); }
  fonte.textContent = `Fonte: ${D.em.fonte}. Coleta em ${dataBR(D.em.gerado_em)}. ${D.em.observacao}`;
  const anos = Object.keys(D.em.anos).sort().reverse();
  if (!S.anoEm || !anos.includes(S.anoEm)) S.anoEm = anos[0];
  const a = D.em.anos[S.anoEm], t = a.total;
  alvo.append(el('div', {class: 'chips', role: 'group', 'aria-label': 'Ano das emendas'}, anos.map(y =>
    el('button', {class: 'chip', type: 'button', 'aria-pressed': String(y === S.anoEm), onclick: () => { S.anoEm = y; rEm(); }}, y))));
  const ufs = ufsAlvo(), u = S.uf === 'BR' ? t : a.por_uf[S.uf] || {empenhado: 0, liquidado: 0, pago: 0, n: 0};
  if (S.mun) alvo.append(aviso(`Valores do estado de ${UF_NOMES[S.uf]}. O recorte por município não está disponível nesta fonte.`));
  alvo.append(el('div', {class: 'kpis'}, kpi('Empenhado', moeda(u.empenhado), `${inteiro(u.n)} ${u.n === 1 ? 'registro' : 'registros'}`), kpi('Liquidado', moeda(u.liquidado)), kpi('Pago', moeda(u.pago), u.empenhado ? pct(u.pago / u.empenhado, 0) + ' do empenhado' : null)));
  if (S.uf === 'BR') {
    const lin = Object.entries(a.por_uf).filter(([k]) => k !== 'ND').sort((x, y) => y[1].pago - x[1].pago).slice(0, 10);
    alvo.append(el('h3', null, `Dez estados com maior valor pago em ${S.anoEm}`),
      ranking(lin.map(([k, v]) => ({nome: UF_NOMES[k] || k, valor: v.pago, rotulo: moeda(v.pago)}))));
    if (a.por_uf.ND) alvo.append(el('p', {class: 'fonte'}, `Localidade do gasto não identificada por estado: ${moeda(a.por_uf.ND.empenhado)} empenhados (${inteiro(a.por_uf.ND.n)} registros).`));
  }
  const tipos = Object.entries(a.por_tipo).sort((x, y) => y[1].empenhado - x[1].empenhado);
  alvo.append(verTabela('Ver por tipo de emenda e por subfunção', ['Tipo de emenda', 'Registros', 'Empenhado', 'Pago'], tipos.map(([k, v]) => [k, inteiro(v.n), moeda(v.empenhado), moeda(v.pago)]).concat(
    Object.entries(a.por_subfuncao).sort((x, y) => y[1].empenhado - x[1].empenhado).map(([k, v]) => ['Subfunção: ' + k, inteiro(v.n), moeda(v.empenhado), moeda(v.pago)])), [1, 2, 3]));
}

// ---------- atencao primaria ----------
const INDICADORES = {
  'Equipes de Saúde da Família e de Atenção Primária (7)': ['Acesso à APS', 'Desenvolvimento infantil', 'Cuidado da gestante e da puérpera', 'Pessoa com diabetes', 'Pessoa com hipertensão arterial', 'Pessoa idosa', 'Prevenção do câncer da mulher'],
  'Equipes Multiprofissionais, eMulti (2)': ['Média de atendimento por pessoa', 'Ações interprofissionais'],
  'Equipes de Saúde Bucal (6)': ['Primeira consulta odontológica programada na APS', 'Tratamento odontológico concluído na APS', 'Escovação supervisionada na APS', 'Procedimentos odontológicos preventivos', 'Taxa de exodontias na APS', 'Tratamento restaurador atraumático na APS']
};
function rAps() {
  const alvo = limpar($('aps'));
  $('fonte-aps').textContent = 'Fontes: Portaria GM/MS nº 10.994/2026 (DOU de 14/05/2026), Ministério da Saúde e Dados Abertos do SUS. Conferir os textos oficiais antes de decidir.';
  alvo.append(el('h3', null, 'Nova metodologia de cofinanciamento: o que muda'),
    el('ul', null,
      el('li', null, '15 indicadores de qualidade, em três blocos de equipes. Desempenho em escala de 0 a 100, em faixas de "regular" (abaixo de 25 pontos) a "ótimo" (acima de 75).'),
      el('li', null, 'Qualidade: implantação parcial a partir do 2º quadrimestre de 2026. Vínculo e acompanhamento territorial: a partir do 3º quadrimestre de 2026.'),
      el('li', null, 'Transferência conforme a classificação das equipes: a partir do 1º quadrimestre de 2027.')),
    el('details', null, el('summary', null, 'Ver os 15 indicadores'), ...Object.entries(INDICADORES).map(([g, l]) => el('div', null, el('h3', null, g), el('ul', null, l.map(i => el('li', null, i)))))),
    el('p', null, 'Relatórios públicos oficiais (cobertura, financiamento e credenciamento): ', el('a', {href: 'https://relatorioaps.saude.gov.br/'}, 'e-Gestor APS, Relatórios Públicos'), '.'));
  const m = D.aps;
  alvo.append(el('h3', null, 'Série fechada do modelo anterior (Previne Brasil, 2024)'));
  if (!m) return alvo.append(el('p', {class: 'indisponivel'}, 'Arquivos de indicadores de 2024 ainda não coletados.'));
  const ok = m.arquivos.filter(a => a.ok);
  alvo.append(el('p', null, `${ok.length} de ${m.arquivos.length} arquivos quadrimestrais coletados em ${dataBR(m.gerado_em)}. É uma carga fechada, sem atualização, e o modelo foi substituído pela Portaria GM/MS nº 3.493/2024.`),
    verTabela('Ver os arquivos coletados', ['Quadrimestre', 'Linhas', 'Colunas'], m.arquivos.map(a => [a.trimestre, a.ok ? inteiro(a.linhas) : 'falhou', a.ok ? String(a.colunas.length) : '-']), [1, 2]));
}

// ---------- notas tecnicas e portarias ----------
function rNotas() {
  const alvo = limpar($('notas')), fonte = $('fonte-notas');
  if (!D.notas && !D.port) { fonte.textContent = ''; return indisponivel(alvo); }
  fonte.textContent = 'Somente título, data, fonte e link. O conteúdo está no site de cada órgão.';
  const itens = (D.notas?.itens || []);
  const temas = ['Todos', ...new Set(itens.map(i => i.tema))];
  const fontes = ['Todas', ...new Set(itens.map(i => i.fonte))];
  const lista = itens.filter(i => (S.tema === 'Todos' || i.tema === S.tema) && (S.fonteNota === 'Todas' || i.fonte === S.fonteNota));
  const chips = (rot, valores, atual, set) => el('div', {class: 'chips', role: 'group', 'aria-label': rot}, valores.map(v => el('button', {class: 'chip', type: 'button', 'aria-pressed': String(v === atual), onclick: () => { set(v); S.nNotas = 15; rNotas(); }}, v)));
  if (itens.length) {
    alvo.append(el('p', null, `Coleta em ${dataBR(D.notas.gerado_em)}.`), chips('Tema', temas, S.tema, v => S.tema = v), chips('Fonte', fontes, S.fonteNota, v => S.fonteNota = v),
      el('ul', {class: 'lista-notas'}, lista.slice(0, S.nNotas).map(i => el('li', null,
        seguro(i.link) ? el('a', {href: i.link, rel: 'noopener'}, i.titulo) : i.titulo,
        el('div', {class: 'meta'}, [i.fonte, i.data ? dataBR(i.data) : null, i.tema].filter(Boolean).join(' · '))))));
    if (lista.length > S.nNotas) alvo.append(el('button', {class: 'botao', type: 'button', onclick: () => { S.nNotas += 15; rNotas(); }}, 'Mostrar mais'));
    if (!lista.length) alvo.append(el('p', {class: 'indisponivel'}, 'Nenhum item para esse filtro.'));
  }
  if (D.port?.portarias?.length) {
    const d = dias(D.port.atualizado);
    alvo.append(el('h3', null, 'Portarias do Ministério da Saúde no DOU'),
      el('p', {class: 'fonte'}, `Radar de portarias atualizado em ${dataBR(D.port.atualizado)}.`),
      d != null && d > 7 ? aviso(`Atenção: o radar de portarias tem ${d} dias. A coleta do DOU pode estar parada.`) : null,
      el('ul', {class: 'lista-notas'}, D.port.portarias.slice(0, 10).map(p => el('li', null,
        seguro(p.url) ? el('a', {href: p.url, rel: 'noopener'}, p.titulo) : p.titulo,
        el('div', null, p.resumo), el('div', {class: 'meta'}, [p.orgao, dataBR(p.data), p.tema].filter(Boolean).join(' · '))))));
  }
}

async function render() {
  await Promise.all([rResumo(), rDengue(), rRede(), rFin(), rEm()]);
  rAps(); rNotas();
}

(async () => {
  montarFiltros();
  await carregarBase();
  preencherMun();
  await render();
})();
