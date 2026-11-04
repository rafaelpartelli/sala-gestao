import {UF_NOMES, inteiro, decimal, pct, moeda, dataBR, el, limpar, seguro, carregar, verTabela} from './util.js';
import {ranking, pilhaNiveis, miniserie, rosca, comparativo, NIVEIS} from './graficos.js';
import {icone, preencherIcones} from './icones.js';
import {revelar, semMovimento} from './efeitos.js';
import {montarMapa} from './mapa.js';
import {montarJornada} from './jornada.js';
import {localizar, descobrirTerritorio} from './geo.js';

const D = {};       // dados carregados
const MUN = new Map();   // codigo IBGE de 7 digitos -> municipio
const S = {uf: 'BR', mun: '', anoEm: null, tema: 'Todos', fonteNota: 'Todas', nNotas: 15};
const $ = id => document.getElementById(id);
const ufsOrdenadas = () => Object.keys(UF_NOMES).sort((a, b) => UF_NOMES[a].localeCompare(UF_NOMES[b], 'pt-BR'));
const dias = iso => iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 864e5) : null;

function indisponivel(no, texto) {
  limpar(no).append(el('p', {class: 'indisponivel'}, texto || 'Dados ainda não coletados para este bloco.'));
}
const aviso = txt => el('p', {class: 'aviso', role: 'note'}, txt);
const ICO_ROT = [[/estabelec/i, 'rede'], [/leito|UTI/i, 'leitos'], [/dengue/i, 'dengue'], [/chikun/i, 'chik'], [/equipe/i, 'aps'], [/profission|médico|vínculo|popula|horas/i, 'pessoal'],
  [/repasse|saldo|emenda|transfer|despesa|paga|empenh|liquid|proposta|estadual|pago/i, 'fin'], [/plano|benefici|cobertura|sem plano/i, 'planos'], [/CAUC|pend/i, 'em'], [/município/i, 'mapa']];
const kpi = (rot, val, nota, ico) => el('div', {class: 'kpi rev'},
  el('div', {class: 'kpi-topo'}, el('span', {class: 'ic'}, icone(ico || ICO_ROT.find(([r]) => r.test(rot))?.[1] || 'resumo', 18)), el('div', {class: 'rot'}, rot)),
  el('div', {class: 'val'}, val), nota ? el('div', {class: 'nota'}, nota) : null);
const somaUF = (obj, campo, ufs) => ufs.reduce((s, u) => s + (obj?.[u]?.[campo] || 0), 0);
const ufsAlvo = () => S.uf === 'BR' ? Object.keys(UF_NOMES) : [S.uf];
const nomeTerritorio = () => S.mun ? (D.munAtual?.nome || 'Município') : (S.uf === 'BR' ? 'Brasil' : UF_NOMES[S.uf]);
const compBR = c => { c = String(c || ''); return c.length === 6 ? `${c.slice(4)}/${c.slice(0, 4)}` : c.length === 4 ? `${c.slice(2)}/20${c.slice(0, 2)}` : (c || 'sem data'); };
const popAlvo = () => S.mun ? (D.munAtual?.pop ?? null) : ufsAlvo().reduce((a, u) => a + (D.terr?.por_uf[u]?.pop_soma || 0), 0);
const porMil = (v, pop, f = 1000) => (v != null && pop) ? v / pop * f : null;
const somaVet = (obj, ufs, n) => ufs.reduce((a, u) => { const v = obj?.[u]; if (v) for (let i = 0; i < n; i++) a[i] += v[i] || 0; return a; }, new Array(n).fill(0));
const nomeMun = cod => MUN.get(cod)?.nome || cod;
const semana = se => se ? `${String(se).slice(4)}/${String(se).slice(0, 4)}` : 'sem dado';

// ---------- carga ----------
const ARQUIVOS = {terr: 'dados/territorio.json', dengueRes: 'dados/dengue_resumo.json', chikRes: 'dados/chikungunya_resumo.json', redeRes: 'dados/rede_resumo.json',
  profRes: 'dados/profissionais_resumo.json', equipes: 'dados/equipes.json', leitos: 'dados/leitos.json', fin: 'dados/financiamento.json', em: 'dados/emendas.json',
  transf: 'dados/transferencias.json', desp: 'dados/despesa.json', cauc: 'dados/cauc.json', ans: 'dados/ans.json', aps: 'dados/aps_meta.json',
  notas: 'dados/notas.json', port: 'dados/portarias.json'};

async function carregarBase() {
  const chaves = Object.keys(ARQUIVOS);
  const lidos = await Promise.all(chaves.map(k => carregar(ARQUIVOS[k])));
  chaves.forEach((k, i) => { D[k] = lidos[i]; });
  D.terr?.municipios.forEach(m => MUN.set(m.cod, m));
  const fontes = chaves.filter(k => k !== 'terr');
  const n = fontes.filter(k => D[k]).length;
  const datas = fontes.map(k => D[k]?.gerado_em || D[k]?.baixado_em || D[k]?.atualizado).filter(Boolean).sort();
  $('upd').textContent = datas.length ? `Atualizado em ${dataBR(datas[datas.length - 1])}` : '';
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
    const lt = D.leitos?.mun?.[S.mun];
    if (lt) k.push(kpi('Leitos SUS', inteiro(lt[2]), `CNES, ${compBR(D.leitos.competencia)}`));
    const eqm = D.equipes?.mun?.[S.mun];
    if (eqm) k.push(kpi('Equipes de saúde ativas', inteiro(Object.values(eqm).reduce((x, y) => x + y, 0)), `CNES, ${compBR(D.equipes.competencia)}`));
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
    if (D.leitos) { const l = somaVet(D.leitos.ufs, ufs, D.leitos.campos.length); k.push(kpi('Leitos SUS por 1.000 habitantes', decimal(porMil(l[2], pop), 2), `${inteiro(l[2])} leitos, CNES ${compBR(D.leitos.competencia)}`)); }
    if (D.equipes) k.push(kpi('Equipes de saúde ativas', inteiro(ufs.reduce((x, u) => x + Object.values(D.equipes.ufs[u] || {}).reduce((a, b) => a + b, 0), 0)), `CNES, ${compBR(D.equipes.competencia)}`));
    if (D.dengueRes) {
      const alto = ufs.reduce((s, u) => s + (+D.dengueRes.ufs[u]?.niveis?.['3'] || 0) + (+D.dengueRes.ufs[u]?.niveis?.['4'] || 0), 0);
      k.push(kpi('Municípios em nível 3 ou 4 de dengue', inteiro(alto), 'Semana mais recente'));
    }
  }
  alvo.append(...k);
}

// ---------- dengue ----------
const dengueUF = uf => uf === 'BR' ? null : carregar(`dados/dengue/${uf}.json`);
const chikUF = uf => uf === 'BR' ? null : carregar(`dados/chikungunya/${uf}.json`);
const redeUF = uf => uf === 'BR' ? null : carregar(`dados/rede/${uf}.json`);

const rDengue = () => rArbo({nome: 'dengue', res: D.dengueRes, uf: dengueUF, alvo: 'dengue', fonte: 'fonte-dengue'});
const rChik = () => rArbo({nome: 'chikungunya', res: D.chikRes, uf: chikUF, alvo: 'chik', fonte: 'fonte-chik'});

async function rArbo(cfg) {
  const alvo = limpar($(cfg.alvo)), fonte = $(cfg.fonte), rotulo = cfg.nome === 'dengue' ? 'dengue' : 'chikungunya';
  if (!cfg.res) { fonte.textContent = ''; return indisponivel(alvo); }
  const r = cfg.res, ufs = ufsAlvo();
  const d = dias(r.gerado_em);
  fonte.textContent = `Fonte: ${r.fonte}. Coleta em ${dataBR(r.gerado_em)}.`;
  if (d != null && d > 3) alvo.append(aviso(`Atenção: a última coleta de ${rotulo} tem ${d} dias.`));
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
  const dg = await cfg.uf(S.uf);
  if (!dg) return alvo.append(aviso('Detalhe por município ainda não coletado para este estado.'));
  alvo.append(el('p', {class: 'fonte'}, `Semana epidemiológica mais recente: ${semana(dg.se)}.`));
  if (S.mun) {
    const x = dg.m.find(l => l[0] === S.mun);
    if (!x || !x[2]) return alvo.append(aviso(`Sem dado de ${rotulo} para este município na semana mais recente.`));
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
      el('div', null, el('h3', null, 'Por esfera administrativa'), rosca(ord(esfera).slice(0, 4), {titulo: 'Estabelecimentos por esfera'}))),
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
  const a = D.em.anos[S.anoEm], u = a.total;
  alvo.append(el('div', {class: 'chips', role: 'group', 'aria-label': 'Ano das emendas'}, anos.map(y =>
    el('button', {class: 'chip', type: 'button', 'aria-pressed': String(y === S.anoEm), onclick: () => { S.anoEm = y; rEm(); }}, y))));
  // A localidade do gasto vem como "Múltiplo" na maior parte do valor: o recorte por estado desta fonte não é confiável.
  const ident = u.pct_empenhado_com_uf ?? (u.empenhado ? 100 * Object.entries(a.por_uf).filter(([k]) => k !== 'ND').reduce((x, [, v]) => x + v.empenhado, 0) / u.empenhado : null);
  alvo.append(aviso(`Valores nacionais. Só ${decimal(ident, 1)}% do empenhado traz um estado identificado na fonte (o restante vem como localidade múltipla), por isso o recorte por estado ou município fica no bloco Financiamento (InvestSUS) e no Radar de Recursos.`));
  alvo.append(el('div', {class: 'kpis'}, kpi('Empenhado', moeda(u.empenhado), `${inteiro(u.n)} ${u.n === 1 ? 'registro' : 'registros'}`), kpi('Liquidado', moeda(u.liquidado)), kpi('Pago', moeda(u.pago), u.empenhado ? pct(u.pago / u.empenhado, 0) + ' do empenhado' : null)));
  const tipos = Object.entries(a.por_tipo).sort((x, y) => y[1].empenhado - x[1].empenhado);
  alvo.append(el('h3', null, `Empenhado por tipo de emenda em ${S.anoEm}`),
    ranking(tipos.map(([k, v]) => ({nome: k, valor: v.empenhado, rotulo: moeda(v.empenhado)}))),
    verTabela('Ver por tipo de emenda e por subfunção', ['Tipo de emenda', 'Registros', 'Empenhado', 'Pago'], tipos.map(([k, v]) => [k, inteiro(v.n), moeda(v.empenhado), moeda(v.pago)]).concat(
      Object.entries(a.por_subfuncao).sort((x, y) => y[1].empenhado - x[1].empenhado).map(([k, v]) => ['Subfunção: ' + k, inteiro(v.n), moeda(v.empenhado), moeda(v.pago)])), [1, 2, 3]));
}

// ---------- profissionais e equipes ----------
const profUF = uf => uf === 'BR' ? null : carregar(`dados/profissionais/${uf}.json`);
const GRUPOS_SEM_RANK = new Set(['Total', 'Outros']);
const medicosBR = () => { const us = Object.keys(UF_NOMES); return porMil(us.reduce((a, u) => a + (D.profRes.ufs[u]?.['Médicos']?.[1] || 0), 0), us.reduce((a, u) => a + (D.terr?.por_uf[u]?.pop_soma || 0), 0)); };

async function rPessoal() {
  const alvo = limpar($('pessoal')), fonte = $('fonte-pessoal');
  if (!D.profRes && !D.equipes) { fonte.textContent = ''; return indisponivel(alvo); }
  const ufs = ufsAlvo(), pop = popAlvo();
  fonte.textContent = [D.profRes && `Profissionais: ${D.profRes.fonte}, competência ${compBR(D.profRes.competencia)}, coleta em ${dataBR(D.profRes.gerado_em)}`,
    D.equipes && `Equipes: ${D.equipes.fonte}, competência ${compBR(D.equipes.competencia)}, coleta em ${dataBR(D.equipes.gerado_em)}`].filter(Boolean).join('. ') + '.';
  if (D.profRes) {
    const g = {};
    if (S.mun) {
      const pu = await profUF(S.uf);
      Object.assign(g, pu?.m?.[S.mun] || {});
    } else ufs.forEach(u => { for (const [k, v] of Object.entries(D.profRes.ufs[u] || {})) { const a = g[k] || (g[k] = [0, 0, 0]); for (let i = 0; i < 3; i++) a[i] += v[i]; } });
    alvo.append(el('h3', null, `Profissionais de saúde: ${nomeTerritorio()}`),
      aviso('A contagem é de vínculos profissionais, não de pessoas: quem atua em dois estabelecimentos aparece duas vezes. "Atende o SUS" segue a marcação do CNES. Os grupos seguem a CBO e devem ser conferidos antes de decisões formais.'));
    const tot = g['Total'];
    if (!tot) alvo.append(el('p', {class: 'indisponivel'}, 'Sem vínculos profissionais registrados para este território.'));
    else {
      alvo.append(el('div', {class: 'kpis'}, kpi('Vínculos profissionais', inteiro(tot[0]), 'Todos os grupos'), kpi('Vínculos que atendem o SUS', inteiro(tot[1]), tot[0] ? pct(tot[1] / tot[0], 0) + ' do total' : null),
        kpi('Médicos (SUS) por 1.000 habitantes', decimal(porMil(g['Médicos']?.[1], pop), 2), 'Vínculos, não pessoas'), kpi('Horas semanais contratadas', inteiro(tot[2]))));
      alvo.append(el('div', {class: 'grade2'}, el('div', null, el('h3', null, 'Vínculos: atendem o SUS e demais'), rosca([{nome: 'Atendem o SUS', valor: tot[1], rotulo: inteiro(tot[1])}, {nome: 'Demais', valor: Math.max(0, tot[0] - tot[1]), rotulo: inteiro(Math.max(0, tot[0] - tot[1]))}], {titulo: 'Vínculos profissionais'})),
        S.uf !== 'BR' && !S.mun ? el('div', null, el('h3', null, 'Médicos (SUS) por 1.000 habitantes: território e Brasil'), comparativo({valor: porMil(g['Médicos']?.[1], pop), ref: medicosBR(), rotValor: `${nomeTerritorio()}: ${decimal(porMil(g['Médicos']?.[1], pop), 2)}`, rotRef: decimal(medicosBR(), 2)})) : null));
      const lin = D.profRes.grupos.filter(n => !GRUPOS_SEM_RANK.has(n) && g[n]).map(n => ({n, v: g[n]})).sort((x, y) => y.v[1] - x.v[1]);
      alvo.append(el('h3', null, 'Vínculos que atendem o SUS por 1.000 habitantes, por grupo'),
        ranking(lin.map(x => ({nome: x.n, valor: porMil(x.v[1], pop) || 0, rotulo: `${decimal(porMil(x.v[1], pop), 2)} (${inteiro(x.v[1])})`}))),
        verTabela('Ver todos os grupos em tabela', ['Grupo', 'Vínculos', 'Atendem o SUS', 'Horas semanais', 'SUS por 1.000 hab.'],
          D.profRes.grupos.filter(n => g[n]).map(n => [n, inteiro(g[n][0]), inteiro(g[n][1]), inteiro(g[n][2]), decimal(porMil(g[n][1], pop), 2)]), [1, 2, 3, 4]));
      if (S.uf === 'BR') {
        const rk = Object.keys(UF_NOMES).map(u => ({u, v: porMil(D.profRes.ufs[u]?.['Médicos']?.[1], D.terr?.por_uf[u]?.pop_soma)})).filter(x => x.v != null).sort((a, b) => b.v - a.v);
        alvo.append(el('h3', null, 'Estados com mais vínculos de médicos que atendem o SUS por 1.000 habitantes'),
          ranking(rk.slice(0, 10).map(x => ({nome: UF_NOMES[x.u], valor: x.v, rotulo: decimal(x.v, 2)}))),
          verTabela('Ver os 27 estados em tabela', ['Estado', 'Médicos (SUS) por 1.000 hab.'], rk.map(x => [UF_NOMES[x.u], decimal(x.v, 2)]), [1]));
      }
    }
  }
  if (D.equipes) {
    const t = {};
    if (S.mun) Object.assign(t, D.equipes.mun[S.mun] || {});
    else ufs.forEach(u => { for (const [k, v] of Object.entries(D.equipes.ufs[u] || {})) t[k] = (t[k] || 0) + v; });
    const total = Object.values(t).reduce((a, b) => a + b, 0);
    alvo.append(el('h3', null, `Equipes de saúde ativas: ${nomeTerritorio()}`));
    if (!total) alvo.append(el('p', {class: 'indisponivel'}, 'Sem equipes ativas registradas para este território.'));
    else {
      const aps = (t['70'] || 0) + (t['76'] || 0);
      alvo.append(el('div', {class: 'kpis'}, kpi('Equipes ativas', inteiro(total), 'Contadas pelo INE'), kpi('Equipes de Saúde da Família e de Atenção Primária', inteiro(aps), 'Tipos 70 e 76'),
        kpi('Equipes de APS por 10 mil habitantes', decimal(porMil(aps, pop, 10000), 2), 'Tipos 70 e 76')));
      const ord = Object.entries(t).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({nome: D.equipes.tipos[k] || `Tipo ${k}`, valor: v, rotulo: inteiro(v)}));
      alvo.append(ranking(ord), el('p', {class: 'fonte'}, 'Tipos sem descrição aparecem pelo código do CNES (tabela de domínio a conferir). ' + (D.equipes.observacao || '')));
    }
  }
}

// ---------- leitos ----------
async function rLeitos() {
  const alvo = limpar($('leitos')), fonte = $('fonte-leitos');
  if (!D.leitos) { fonte.textContent = ''; return indisponivel(alvo); }
  const L = D.leitos, ix = Object.fromEntries(L.campos.map((c, i) => [c, i])), ufs = ufsAlvo(), pop = popAlvo();
  fonte.textContent = `Fonte: ${L.fonte}. Competência ${compBR(L.competencia)}. Coleta em ${dataBR(L.gerado_em)}. ${L.observacao}`;
  const v = S.mun ? (L.mun[S.mun] || new Array(L.campos.length).fill(0)) : somaVet(L.ufs, ufs, L.campos.length);
  if (S.mun && !L.mun[S.mun]) alvo.append(aviso('Este município não tem estabelecimento com leitos na competência coletada.'));
  alvo.append(el('div', {class: 'kpis'}, kpi('Leitos existentes', inteiro(v[ix.EXIST]), `${inteiro(v[ix.EST])} estabelecimentos`), kpi('Leitos SUS', inteiro(v[ix.SUS]), v[ix.EXIST] ? pct(v[ix.SUS] / v[ix.EXIST], 0) + ' dos existentes' : null),
    kpi('Leitos SUS por 1.000 habitantes', decimal(porMil(v[ix.SUS], pop), 2)), kpi('Leitos de UTI no SUS', inteiro(v[ix.UTI_SUS]), `Adulto ${inteiro(v[ix.UTI_AD_SUS])}, pediátrico ${inteiro(v[ix.UTI_PED_SUS])}, neonatal ${inteiro(v[ix.UTI_NEO_SUS])}`)));
  alvo.append(el('div', {class: 'grade2'},
    el('div', null, el('h3', null, 'Leitos existentes: SUS e fora do SUS'), rosca([{nome: 'SUS', valor: v[ix.SUS], rotulo: inteiro(v[ix.SUS])}, {nome: 'Fora do SUS', valor: Math.max(0, v[ix.EXIST] - v[ix.SUS]), rotulo: inteiro(Math.max(0, v[ix.EXIST] - v[ix.SUS]))}], {titulo: 'Leitos existentes'})),
    el('div', null, el('h3', null, 'Leitos de UTI: SUS e fora do SUS'), !v[ix.UTI_EXIST] ? el('p', {class: 'indisponivel'}, 'Sem leitos de UTI registrados neste território.') : rosca([{nome: 'UTI SUS', valor: v[ix.UTI_SUS], rotulo: inteiro(v[ix.UTI_SUS])}, {nome: 'UTI fora do SUS', valor: Math.max(0, v[ix.UTI_EXIST] - v[ix.UTI_SUS]), rotulo: inteiro(Math.max(0, v[ix.UTI_EXIST] - v[ix.UTI_SUS]))}], {titulo: 'Leitos de UTI'}))));
  if (S.uf !== 'BR' && !S.mun) {
    const lb = somaVet(L.ufs, Object.keys(UF_NOMES), L.campos.length), popB = Object.keys(UF_NOMES).reduce((a, u) => a + (D.terr?.por_uf[u]?.pop_soma || 0), 0);
    alvo.append(el('h3', null, 'Leitos SUS por 1.000 habitantes: território e Brasil'), comparativo({valor: porMil(v[ix.SUS], pop), ref: porMil(lb[ix.SUS], popB), rotValor: `${nomeTerritorio()}: ${decimal(porMil(v[ix.SUS], pop), 2)}`, rotRef: decimal(porMil(lb[ix.SUS], popB), 2)}));
  }
  if (S.uf === 'BR') {
    const rk = Object.keys(UF_NOMES).filter(u => L.ufs[u]).map(u => ({u, v: porMil(L.ufs[u][ix.SUS], D.terr?.por_uf[u]?.pop_soma), n: L.ufs[u][ix.SUS]})).filter(x => x.v != null).sort((a, b) => b.v - a.v);
    alvo.append(el('h3', null, 'Estados com mais leitos SUS por 1.000 habitantes'), ranking(rk.slice(0, 10).map(x => ({nome: UF_NOMES[x.u], valor: x.v, rotulo: `${decimal(x.v, 2)} (${inteiro(x.n)})`}))),
      verTabela('Ver os 27 estados em tabela', ['Estado', 'Leitos SUS', 'Por 1.000 hab.'], rk.map(x => [UF_NOMES[x.u], inteiro(x.n), decimal(x.v, 2)]), [1, 2]));
  } else if (!S.mun) {
    const rk = Object.entries(L.mun).filter(([c]) => MUN.get(c)?.uf === S.uf).map(([c, a]) => ({c, n: a[ix.SUS], p: MUN.get(c)?.pop})).sort((a, b) => b.n - a.n);
    alvo.append(el('h3', null, `Dez municípios com mais leitos SUS em ${UF_NOMES[S.uf]}`), ranking(rk.slice(0, 10).map(x => ({nome: nomeMun(x.c), valor: x.n, rotulo: `${inteiro(x.n)} (${decimal(porMil(x.n, x.p), 2)} por 1.000 hab.)`}))),
      verTabela('Ver todos os municípios em tabela', ['Município', 'Leitos SUS', 'Por 1.000 hab.'], rk.map(x => [nomeMun(x.c), inteiro(x.n), decimal(porMil(x.n, x.p), 2)]), [1, 2]));
  }
}

// ---------- transferencias federais, despesa e regularidade ----------
async function rRecursos() {
  const alvo = limpar($('rec')), fonte = $('fonte-rec');
  if (!D.transf && !D.desp && !D.cauc) { fonte.textContent = ''; return indisponivel(alvo); }
  const ufs = ufsAlvo(), pop = popAlvo();
  fonte.textContent = [D.transf && `Transferências: ${D.transf.fonte}, coleta em ${dataBR(D.transf.gerado_em)}`, D.desp && `Despesa: ${D.desp.fonte}, exercício ${D.desp.exercicio}`,
    D.cauc && `CAUC: ${D.cauc.fonte}, pesquisa de ${dataBR(D.cauc.data_pesquisa)}`].filter(Boolean).join('. ') + '.';
  if (D.transf) {
    const T = D.transf, n = T.meses.length, serie = S.mun ? (T.mun[S.mun] || new Array(n).fill(0)) : somaVet(T.ufs, ufs, n), soma = serie.reduce((a, b) => a + b, 0);
    alvo.append(el('h3', null, `Transferências da União em saúde: ${nomeTerritorio()}`),
      el('div', {class: 'kpis'}, kpi(`Transferido em ${compBR(T.meses[n - 1])}`, moeda(serie[n - 1])), kpi(`Soma de ${n} ${n === 1 ? 'mês' : 'meses'}`, moeda(soma)), kpi('Por habitante no período', pop ? 'R$ ' + decimal(soma / pop, 0) : 'sem dado')),
      ranking(T.meses.map((m, i) => ({nome: compBR(m), valor: serie[i], rotulo: moeda(serie[i])}))),
      el('p', {class: 'fonte'}, `${T.observacao} Em ${compBR(T.meses[n - 1])}, ${decimal(T.pct_valor_com_municipio?.[T.meses[n - 1]], 0)}% do valor trazia município identificado.`));
    if (!S.mun && S.uf !== 'BR') {
      const rk = Object.entries(T.mun).filter(([c]) => MUN.get(c)?.uf === S.uf).map(([c, a]) => ({c, v: a.reduce((x, y) => x + y, 0), p: MUN.get(c)?.pop})).sort((a, b) => b.v - a.v);
      alvo.append(el('h3', null, `Dez municípios com maior valor transferido em ${UF_NOMES[S.uf]} no período`), ranking(rk.slice(0, 10).map(x => ({nome: nomeMun(x.c), valor: x.v, rotulo: moeda(x.v)}))),
        verTabela('Ver todos os municípios em tabela', ['Município', 'Transferido no período', 'Por habitante'], rk.map(x => [nomeMun(x.c), moeda(x.v), x.p ? 'R$ ' + decimal(x.v / x.p, 0) : 'sem dado']), [1, 2]));
    }
  }
  if (D.desp) {
    const Dp = D.desp;
    const v = S.mun ? Dp.mun[S.mun] : (() => { const s5 = somaVet(Dp.ufs, ufs, 5); return [s5[0], s5[1], s5[2], s5[3]]; })();
    alvo.append(el('h3', null, `Despesa em saúde no exercício ${Dp.exercicio}: ${nomeTerritorio()}`));
    if (!v) alvo.append(aviso('Este município não entregou a Declaração de Contas Anuais do exercício, por isso não há valor.'));
    else {
      alvo.append(el('div', {class: 'kpis'}, kpi('Despesa paga em saúde', moeda(v[2])), kpi('Por habitante', v[3] ? 'R$ ' + decimal(v[2] / v[3], 0) : 'sem dado', 'População do SICONFI'), kpi('Empenhada', moeda(v[0]), v[0] ? pct(v[2] / v[0], 0) + ' paga' : null)));
      if (!S.mun) alvo.append(el('p', {class: 'fonte'}, `${inteiro(S.uf === 'BR' ? Dp.municipios_com_despesa : Object.keys(Dp.mun).filter(c => MUN.get(c)?.uf === S.uf).length)} municípios com despesa declarada. ${Dp.observacao}`));
      if (S.uf === 'BR') {
        const rk = Object.keys(UF_NOMES).filter(u => Dp.ufs[u] && Dp.ufs[u][3]).map(u => ({u, v: Dp.ufs[u][2] / Dp.ufs[u][3]})).sort((a, b) => b.v - a.v);
        alvo.append(el('h3', null, 'Estados com maior despesa municipal paga em saúde por habitante'), ranking(rk.slice(0, 10).map(x => ({nome: UF_NOMES[x.u], valor: x.v, rotulo: 'R$ ' + decimal(x.v, 0)}))),
          verTabela('Ver os 27 estados em tabela', ['Estado', 'Por habitante'], rk.map(x => [UF_NOMES[x.u], 'R$ ' + decimal(x.v, 0)]), [1]));
      } else if (!S.mun) {
        const rk = Object.entries(Dp.mun).filter(([c]) => MUN.get(c)?.uf === S.uf && Dp.mun[c][3]).map(([c, a]) => ({c, pc: a[2] / a[3], pago: a[2], pop: a[3]})).sort((a, b) => b.pc - a.pc);
        const med = rk.length ? rk.map(x => x.pc).sort((a, b) => a - b)[Math.floor(rk.length / 2)] : null;
        alvo.append(el('p', null, `Mediana dos municípios: R$ ${decimal(med, 0)} por habitante.`),
          verTabela('Ver todos os municípios em tabela', ['Município', 'População', 'Despesa paga', 'Por habitante'], rk.map(x => [nomeMun(x.c), inteiro(x.pop), moeda(x.pago), 'R$ ' + decimal(x.pc, 0)]), [1, 2, 3]));
      }
    }
  }
  if (D.cauc) {
    const C = D.cauc;
    alvo.append(el('h3', null, `Regularidade no CAUC: ${nomeTerritorio()}`));
    if (S.mun) {
      const p = C.mun[S.mun] || [];
      alvo.append(el('p', null, p.length ? `Itens com pendência: ${p.join(', ')}.` : 'Nenhum item marcado como pendente na pesquisa mais recente.'));
    } else {
      const com = ufs.reduce((a, u) => a + (C.ufs[u]?.com_pendencia || 0), 0), tot = ufs.reduce((a, u) => a + (C.ufs[u]?.municipios || 0), 0);
      alvo.append(el('div', {class: 'kpis'}, kpi('Municípios com alguma pendência', inteiro(com), tot ? pct(com / tot, 1) + ' de ' + inteiro(tot) : null)));
      if (S.uf === 'BR') {
        const itens = Object.entries(C.por_item).sort((a, b) => b[1].pendentes - a[1].pendentes);
        alvo.append(verTabela('Ver pendências por item do CAUC', ['Item', 'Municípios com pendência', 'Percentual'], itens.map(([k, x]) => [k, inteiro(x.pendentes), decimal(x.pct, 1) + '%']), [1, 2]));
      }
    }
    alvo.append(el('p', {class: 'fonte'}, 'O arquivo do CAUC mostra a situação de cada item (regular ou pendente). Não traz percentuais de aplicação nem a descrição dos itens. ',
      el('a', {href: 'https://www.gov.br/tesouronacional/pt-br/estados-e-municipios/cauc', rel: 'noopener'}, 'CAUC no Tesouro Nacional'), '.'));
  }
}

// ---------- planos privados de saude ----------
async function rPlanos() {
  const alvo = limpar($('planos')), fonte = $('fonte-planos');
  if (!D.ans) { fonte.textContent = ''; return indisponivel(alvo); }
  const A = D.ans, ufs = ufsAlvo();
  fonte.textContent = `Fonte: ${A.fonte}. Período ${A.periodo}. Coleta em ${dataBR(A.gerado_em)}. ${A.observacao}`;
  const v = S.mun ? A.mun[S.mun] : somaVet(A.ufs, ufs, 2);
  if (!v || !v[1]) return alvo.append(aviso('Sem dado de cobertura para este território.'));
  alvo.append(el('div', {class: 'kpis'}, kpi('Beneficiários de plano de assistência médica', inteiro(v[0])), kpi('Cobertura da população', pct(v[0] / v[1], 1), 'Beneficiários ÷ população (ANS)'),
    kpi('Sem plano privado (estimativa)', pct(Math.max(0, 1 - v[0] / v[1]), 1), 'Complemento da cobertura')));
  alvo.append(rosca([{nome: 'Com plano de assistência médica', valor: v[0], rotulo: inteiro(v[0])}, {nome: 'Sem plano privado (estimativa)', valor: Math.max(0, v[1] - v[0]), rotulo: inteiro(Math.max(0, v[1] - v[0]))}], {titulo: 'Cobertura de planos'}));
  if (S.uf === 'BR') {
    const rk = Object.keys(UF_NOMES).filter(u => A.ufs[u] && A.ufs[u][1]).map(u => ({u, v: A.ufs[u][0] / A.ufs[u][1]})).sort((a, b) => b.v - a.v);
    alvo.append(el('h3', null, 'Estados com maior cobertura de planos de assistência médica'), ranking(rk.slice(0, 10).map(x => ({nome: UF_NOMES[x.u], valor: x.v, rotulo: pct(x.v, 1)})), {max: 1}),
      verTabela('Ver os 27 estados em tabela', ['Estado', 'Cobertura'], rk.map(x => [UF_NOMES[x.u], pct(x.v, 1)]), [1]));
  } else if (!S.mun) {
    const rk = Object.entries(A.mun).filter(([c]) => MUN.get(c)?.uf === S.uf && A.mun[c][1]).map(([c, a]) => ({c, v: a[0] / a[1], b: a[0]})).sort((a, b) => b.v - a.v);
    alvo.append(verTabela('Ver todos os municípios em tabela', ['Município', 'Beneficiários', 'Cobertura'], rk.map(x => [nomeMun(x.c), inteiro(x.b), pct(x.v, 1)]), [1, 2]));
  }
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

// ---------- jornada: paradas, perguntas e descobertas ----------
const sumGrupos = (ufs, chave) => ufs.reduce((o, u) => { for (const [k, v] of Object.entries(D.redeRes?.ufs[u]?.[chave] || {})) o[k] = (o[k] || 0) + v; return o; }, {});
const terr = () => S.uf === 'BR' ? 'o Brasil' : UF_NOMES[S.uf];
function fatoArbo(res, rot) {
  if (!res) return null;
  const ufs = ufsAlvo(), alta = u => (+res.ufs[u]?.niveis?.['3'] || 0) + (+res.ufs[u]?.niveis?.['4'] || 0);
  const alto = ufs.reduce((a, u) => a + alta(u), 0), tot = ufs.reduce((a, u) => a + (res.ufs[u]?.municipios || 0), 0);
  if (!tot) return null;
  if (S.uf !== 'BR') return `${inteiro(alto)} de ${inteiro(tot)} municípios (${pct(alto / tot, 1)}) de ${UF_NOMES[S.uf]} estão em nível 3 ou 4 de ${rot}.`;
  const r = ufs.filter(u => res.ufs[u]?.municipios).map(u => ({u, p: alta(u) / res.ufs[u].municipios})).sort((a, b) => b.p - a.p)[0];
  return `${inteiro(alto)} de ${inteiro(tot)} municípios (${pct(alto / tot, 1)}) estão em nível 3 ou 4 de ${rot}. A maior proporção é em ${UF_NOMES[r.u]} (${pct(r.p, 0)}).`;
}
let mapa, jornada;
const PARADAS = [
  {id: 'mapa', rot: 'Mapa da saúde', ico: 'mapa', pergunta: 'Onde cada indicador é mais alto? Troque a camada e veja o mapa mudar.', disp: () => !!D.terr, fato: () => mapa?.fato || null},
  {id: 'dengue', rot: 'Dengue', ico: 'dengue', pergunta: 'Qual estado tem a maior parte dos municípios em alerta alto?', disp: () => !!D.dengueRes, fato: () => fatoArbo(D.dengueRes, 'dengue')},
  {id: 'chik', rot: 'Chikungunya', ico: 'chik', pergunta: 'A chikungunya segue o mesmo desenho da dengue?', disp: () => !!D.chikRes, fato: () => fatoArbo(D.chikRes, 'chikungunya')},
  {id: 'rede', rot: 'Rede assistencial', ico: 'rede', pergunta: 'Que tipo de unidade domina a rede do seu território?', disp: () => !!D.redeRes, fato: () => {
    const g = sumGrupos(ufsAlvo(), 'grupos'), tot = Object.values(g).reduce((a, b) => a + b, 0), top = Object.entries(g).sort((a, b) => b[1] - a[1])[0];
    return top && tot ? `${pct(top[1] / tot, 0)} dos estabelecimentos ativos de ${terr()} são do tipo "${top[0]}" (${inteiro(top[1])}).` : null; }},
  {id: 'pessoal', rot: 'Profissionais e equipes', ico: 'pessoal', pergunta: 'Quantos médicos atendem o SUS para cada 1.000 habitantes?', disp: () => !!(D.profRes || D.equipes), fato: () => {
    if (!D.profRes) return null; const ufs = ufsAlvo(), v = porMil(ufs.reduce((a, u) => a + (D.profRes.ufs[u]?.['Médicos']?.[1] || 0), 0), ufs.reduce((a, u) => a + (D.terr?.por_uf[u]?.pop_soma || 0), 0));
    return v != null ? `${decimal(v, 2)} vínculos de médicos que atendem o SUS por 1.000 habitantes em ${terr()} (Brasil: ${decimal(medicosBR(), 2)}).` : null; }},
  {id: 'leitos', rot: 'Leitos', ico: 'leitos', pergunta: 'Quantos leitos de UTI o SUS tem no seu território?', disp: () => !!D.leitos, fato: () => {
    const L = D.leitos, ix = Object.fromEntries(L.campos.map((c, i) => [c, i])), ufs = ufsAlvo(), v = somaVet(L.ufs, ufs, L.campos.length);
    return `${inteiro(v[ix.UTI_SUS])} leitos de UTI no SUS e ${decimal(porMil(v[ix.SUS], popAlvoUF()), 2)} leitos SUS por 1.000 habitantes em ${terr()}.`; }},
  {id: 'fin', rot: 'Financiamento', ico: 'fin', pergunta: 'Quanto chega por habitante em cada estado?', disp: () => !!D.fin, fato: () => {
    const f = D.fin.dados.uf, ufs = ufsAlvo(), fb = somaUF(f, 'fb', ufs), pp = ufs.reduce((a, u) => a + (f[u]?.pop || 0), 0);
    return pp ? `R$ ${decimal(fb / pp, 0)} por habitante em repasses fundo a fundo no ano, em ${terr()}.` : null; }},
  {id: 'em', rot: 'Emendas da União', ico: 'em', pergunta: 'Quanto das emendas já foi de fato pago?', disp: () => !!D.em, fato: () => {
    const anos = Object.keys(D.em.anos).sort().reverse(), u = D.em.anos[anos[0]]?.total;
    return u?.empenhado ? `${pct(u.pago / u.empenhado, 0)} do valor empenhado em ${anos[0]} já foi pago (dado nacional).` : null; }},
  {id: 'rec', rot: 'Transferências e regularidade', ico: 'rec', pergunta: 'Seu município está regular no CAUC?', disp: () => !!(D.transf || D.desp || D.cauc), fato: () => {
    const ufs = ufsAlvo();
    if (D.cauc) { const com = ufs.reduce((a, u) => a + (D.cauc.ufs[u]?.com_pendencia || 0), 0), tot = ufs.reduce((a, u) => a + (D.cauc.ufs[u]?.municipios || 0), 0); if (tot) return `${pct(com / tot, 1)} dos municípios de ${terr()} têm alguma pendência no CAUC (${inteiro(com)} de ${inteiro(tot)}).`; }
    return null; }},
  {id: 'planos', rot: 'Planos de saúde', ico: 'planos', pergunta: 'Que parte da população não tem plano privado?', disp: () => !!D.ans, fato: () => {
    const v = somaVet(D.ans.ufs, ufsAlvo(), 2); return v[1] ? `${pct(v[0] / v[1], 1)} da população de ${terr()} tem plano de assistência médica; o restante depende do SUS na prática (estimativa).` : null; }},
  {id: 'aps', rot: 'Atenção Primária', ico: 'aps', pergunta: 'O que muda no cofinanciamento da Atenção Primária?', disp: () => true, fato: () => '15 indicadores de qualidade em três blocos de equipes, com desempenho de 0 a 100 (Portaria GM/MS nº 10.994/2026).'},
  {id: 'notas', rot: 'Notas e portarias', ico: 'notas', pergunta: 'Saiu alguma norma nova que afeta o seu município?', disp: () => !!(D.notas || D.port), fato: () => `${inteiro(D.notas?.itens?.length || 0)} notas e informes e ${inteiro(D.port?.portarias?.length || 0)} portarias na última coleta.`}
];
const popAlvoUF = () => ufsAlvo().reduce((a, u) => a + (D.terr?.por_uf[u]?.pop_soma || 0), 0);

// ---------- acoes: sorteio de estado e localizacao ----------
const rolar = id => { const n = document.getElementById('mod-' + id); if (n) n.scrollIntoView({behavior: semMovimento() ? 'auto' : 'smooth', block: 'start'}); };
function selecionarUF(u) { const sel = $('selUF'); if (!sel || ![...sel.options].some(o => o.value === u)) return; sel.value = u; sel.dispatchEvent(new Event('change')); }
function selecionarMun(c) { const sel = $('selMun'); if (!sel || ![...sel.options].some(o => o.value === c)) return; sel.value = c; sel.dispatchEvent(new Event('change')); }
function surpreender() {
  const opcoes = Object.keys(UF_NOMES).filter(u => u !== S.uf);
  const u = opcoes[Math.floor(Math.random() * opcoes.length)];
  selecionarUF(u); rolar('mapa'); jornada?.avisar(`Sorteado: ${UF_NOMES[u]}. Explore os blocos e compare com o Brasil.`);
}
async function usarLocalizacao() {
  const st = $('geo-status'), btn = $('btnLocal');
  const dizer = t => { st.textContent = t; };
  btn.disabled = true; dizer('Pedindo permissão de localização ao navegador...');
  try {
    const p = await localizar();
    dizer('Identificando o município...');
    const t = await descobrirTerritorio(p.lat, p.lon, D.terr?.municipios || []);
    if (!t) { dizer('Sua posição está fora do território brasileiro coberto pelo painel.'); return; }
    C.minhaPos = p;
    selecionarUF(t.uf);
    if (t.cod) selecionarMun(t.cod);
    dizer(t.cod ? `Localizamos você em ${nomeMun(t.cod)}, ${t.uf}. A posição fica só no seu navegador.` : `Localizamos você em ${UF_NOMES[t.uf]}. Não foi possível identificar o município.`);
    rolar('mapa');
  } catch (e) {
    dizer(e && e.code === 1 ? 'Permissão negada. Escolha o estado e o município nas listas acima.' : 'Não foi possível obter a localização agora. Escolha o estado e o município nas listas acima.');
  } finally { btn.disabled = false; }
}

const C = {D, MUN, S, UF_NOMES, dengueUF, chikUF, redeUF, profUF, selecionarUF, selecionarMun, minhaPos: null, aoMapa: () => jornada?.atualizar()};

async function render() {
  await Promise.all([mapa.atualizar(), rResumo(), rDengue(), rChik(), rRede(), rPessoal(), rLeitos(), rFin(), rEm(), rRecursos(), rPlanos()]);
  rAps(); rNotas();
  preencherIcones(); revelar(); jornada.atualizar();
}

(async () => {
  montarFiltros();
  preencherIcones();
  const mb = $('menuBtn'); mb?.addEventListener('click', () => { const ab = $('nav').classList.toggle('aberto'); mb.setAttribute('aria-expanded', String(ab)); });
  $('ano').textContent = new Date().getFullYear();
  $('btnLocal').addEventListener('click', usarLocalizacao);
  $('btnSorte').addEventListener('click', surpreender);
  await carregarBase();
  preencherMun();
  mapa = montarMapa(C);
  jornada = montarJornada({paradas: PARADAS, irPara: rolar, surpreender, nomeTerritorio: () => S.uf === 'BR' ? 'o Brasil' : UF_NOMES[S.uf]});
  await render();
})();
