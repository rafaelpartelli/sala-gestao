// Mapa coropletico: estados (mapa incluido no site) e municipios do estado escolhido (malha do IBGE, carregada no navegador).
import MAPA from './mapa-brasil.js';
import {el, limpar, inteiro, verTabela} from './util.js';
import {icone} from './icones.js';
import {indicadores} from './indicadores.js';
import {malhaUF, projetar} from './geo.js';
import {ranking, escala} from './graficos.js';

const NS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs = {}) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };

// Quatro cortes por quantis: cinco faixas com cerca de 20% dos territorios cada.
function faixas(valores, fmt) {
  const v = valores.filter(x => x != null && isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return {classe: () => null, legenda: []};
  const cortes = [1, 2, 3, 4].map(i => v[Math.min(v.length - 1, Math.floor(v.length * i / 5))]);
  const classe = x => x == null || !isFinite(x) ? null : cortes.reduce((k, c) => x >= c ? k + 1 : k, 0);
  const lim = Array.from({length: 5}, () => [Infinity, -Infinity]);
  v.forEach(x => { const k = classe(x); if (x < lim[k][0]) lim[k][0] = x; if (x > lim[k][1]) lim[k][1] = x; });
  const legenda = lim.map((l, k) => isFinite(l[0]) ? {k, rotulo: l[0] === l[1] ? fmt(l[0]) : `${fmt(l[0])} a ${fmt(l[1])}`} : null).filter(Boolean);
  return {classe, legenda};
}

export function montarMapa(c) {
  const raiz = document.getElementById('mapa-corpo');
  let camada = null, ficha = 0;

  async function atualizar() {
    const meu = ++ficha;
    const defs = indicadores(c);
    limpar(raiz);
    if (!defs.length || !c.D.terr) { raiz.append(el('p', {class: 'indisponivel'}, 'Os indicadores do mapa aparecem assim que as fontes forem coletadas.')); return; }
    if (!camada || !defs.some(d => d.id === camada)) camada = defs[0].id;
    const def = defs.find(d => d.id === camada), uf = c.S.uf, modoUF = uf !== 'BR';
    const rot = (modoUF && def.rotM) || def.rot, fmt = (modoUF && def.fmtM) || def.fmt;

    const chips = el('div', {class: 'chips camadas', role: 'group', 'aria-label': 'Indicador do mapa'}, defs.map(d =>
      el('button', {class: 'chip', type: 'button', 'aria-pressed': String(d.id === camada), onclick: () => { camada = d.id; atualizar(); }}, icone(d.ico, 16), d.curto)));
    const caixa = el('div', {class: 'mapa-caixa'}, el('p', {class: 'indisponivel'}, modoUF ? 'Carregando o mapa dos municípios...' : 'Carregando o mapa...'));
    const lado = el('div', {class: 'mapa-lado'});
    raiz.append(chips, el('h3', {class: 'mapa-titulo'}, rot), el('div', {class: 'mapa-grade'}, caixa, lado));

    let valores = {}, nomeDe, semMunicipal = false, itens = null, ponto = null, vb = MAPA.viewBox;
    if (!modoUF) {
      Object.keys(c.UF_NOMES).forEach(u => { valores[u] = def.uf(u); });
      nomeDe = k => c.UF_NOMES[k];
    } else {
      nomeDe = k => c.MUN.get(k)?.nome || k;
      if (def.mun) { const r = await def.mun(uf); if (r) valores = r; else semMunicipal = true; } else semMunicipal = true;
      const fc = await malhaUF(uf);
      if (meu !== ficha) return;
      if (!fc) { limpar(caixa).append(el('p', {class: 'aviso'}, 'Não foi possível carregar a malha municipal do IBGE agora. Os rankings e as tabelas continuam disponíveis abaixo.')); }
      else { const pj = projetar(fc); itens = pj.itens; vb = pj.viewBox; ponto = pj.ponto; }
    }
    if (meu !== ficha) return;

    const {classe, legenda} = faixas(Object.values(valores), fmt);
    const texto = k => { const v = valores[k]; return `${nomeDe(k)}: ${v == null ? 'sem dado' : fmt(v)}`; };
    const dica = el('div', {class: 'dica', role: 'status', hidden: true});
    const svg = svgEl('svg', {viewBox: vb, class: 'mapa-svg', role: 'group', 'aria-label': modoUF ? `Mapa dos municípios de ${c.UF_NOMES[uf]}` : 'Mapa dos estados do Brasil'});
    const mostrar = (e, k) => {
      dica.textContent = texto(k); dica.hidden = false;
      const r = caixa.getBoundingClientRect(), x = (e.clientX ?? r.left + r.width / 2) - r.left, y = (e.clientY ?? r.top + 40) - r.top;
      dica.style.left = Math.min(Math.max(x, 70), r.width - 70) + 'px'; dica.style.top = Math.max(y - 12, 24) + 'px';
    };
    const esconder = () => { dica.hidden = true; };

    const desenhar = (k, d, i) => {
      const cl = classe(valores[k]);
      const sel = modoUF ? k === c.S.mun : k === uf;
      const p = svgEl('path', {d, class: `area e${cl == null ? 0 : cl + 1}${sel ? ' sel' : ''}`, tabindex: '0', role: 'button', 'aria-label': texto(k) + (modoUF ? '. Abrir este município' : '. Abrir este estado'), style: `--i:${Math.min(i, 40)}`});
      const ir = () => (modoUF ? c.selecionarMun(k) : c.selecionarUF(k));
      p.addEventListener('click', ir);
      p.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ir(); } });
      p.addEventListener('pointermove', e => mostrar(e, k)); p.addEventListener('pointerleave', esconder);
      p.addEventListener('focus', () => { const b = p.getBoundingClientRect(); mostrar({clientX: b.left + b.width / 2, clientY: b.top}, k); }); p.addEventListener('blur', esconder);
      return p;
    };
    if (!modoUF) MAPA.locations.forEach((l, i) => { const k = l.id.toUpperCase(); svg.append(desenhar(k, l.path, i)); });
    else if (itens) {
      itens.forEach((it, i) => svg.append(desenhar(it.cod, it.d, i)));
      svg.querySelectorAll('.sel').forEach(n => n.parentNode.append(n));
      if (c.minhaPos && ponto) { const [px, py] = ponto(c.minhaPos.lon, c.minhaPos.lat); svg.append(svgEl('circle', {cx: px, cy: py, r: 3.2, class: 'pino'}), svgEl('circle', {cx: px, cy: py, r: 3.2, class: 'pino-onda'})); }
    }
    if (!modoUF || itens) limpar(caixa).append(svg, dica);

    // painel lateral
    const lista = Object.entries(valores).filter(([, v]) => v != null && isFinite(v)).sort((a, b) => b[1] - a[1]);
    const topo = lista[0]?.[1] || 1;
    const linha = ([k, v]) => ({nome: nomeDe(k), valor: v, rotulo: fmt(v)});
    lado.append(escala(legenda, Object.values(valores).some(v => v == null) || !lista.length));
    if (modoUF) lado.append(el('button', {class: 'botao botao-icone', type: 'button', onclick: () => c.selecionarUF('BR')}, icone('voltar', 16), 'Ver o Brasil'));
    const alvo = modoUF ? (c.S.mun || null) : null;
    if (alvo && valores[alvo] != null) {
      const pos = lista.findIndex(([k]) => k === alvo) + 1;
      lado.append(el('div', {class: 'cartao-mun'}, el('h3', null, nomeDe(alvo)), el('p', {class: 'kpi-grande'}, fmt(valores[alvo])), el('p', {class: 'fonte'}, `${pos}º entre ${inteiro(lista.length)} municípios com dado neste indicador.`)));
    } else if (!modoUF) lado.append(el('p', {class: 'fonte'}, 'Toque ou clique em um estado para abrir o mapa dos seus municípios.'));
    if (semMunicipal) lado.append(el('p', {class: 'aviso', role: 'note'}, 'Este indicador não tem detalhe por município na fonte. Escolha outro indicador para colorir os municípios.'));
    if (lista.length > 1) {
      lado.append(el('h3', null, 'Maiores valores'), ranking(lista.slice(0, 5).map(linha), {max: topo}),
        el('h3', null, 'Menores valores'), ranking(lista.slice(-5).reverse().map(linha), {max: topo}));
    }
    lado.append(verTabela('Ver todos em tabela', [modoUF ? 'Município' : 'Estado', 'Valor'], lista.map(([k, v]) => [nomeDe(k), fmt(v)]), [1]));
    document.getElementById('fonte-mapa').textContent = `Fonte: ${def.fonte}. Cinco faixas por quantis (cada faixa reúne cerca de 20% dos territórios). Cores mais escuras indicam valores maiores.`;
    api.fato = lista.length > 1 ? `${def.curto}: o maior valor é ${nomeDe(lista[0][0])} (${fmt(lista[0][1])}) e o menor, ${nomeDe(lista[lista.length - 1][0])} (${fmt(lista[lista.length - 1][1])}).` : null;
    c.aoMapa?.();
  }
  const api = {atualizar, fato: null};
  return api;
}
