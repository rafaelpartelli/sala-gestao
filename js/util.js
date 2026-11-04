// Funcoes de apoio: formatacao em pt-BR, criacao segura de elementos e leitura dos arquivos de dados.
export const UF_NOMES = {AC:'Acre',AL:'Alagoas',AM:'Amazonas',AP:'Amapá',BA:'Bahia',CE:'Ceará',DF:'Distrito Federal',ES:'Espírito Santo',GO:'Goiás',MA:'Maranhão',MG:'Minas Gerais',MS:'Mato Grosso do Sul',MT:'Mato Grosso',PA:'Pará',PB:'Paraíba',PE:'Pernambuco',PI:'Piauí',PR:'Paraná',RJ:'Rio de Janeiro',RN:'Rio Grande do Norte',RO:'Rondônia',RR:'Roraima',RS:'Rio Grande do Sul',SC:'Santa Catarina',SE:'Sergipe',SP:'São Paulo',TO:'Tocantins'};

const nf = new Intl.NumberFormat('pt-BR');
export const inteiro = v => (v == null || isNaN(v)) ? 'sem dado' : nf.format(Math.round(v));
export const decimal = (v, d = 1) => (v == null || isNaN(v)) ? 'sem dado' : v.toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
export const pct = (v, d = 1) => (v == null || isNaN(v)) ? 'sem dado' : decimal(v * 100, d) + '%';

export function moeda(v) {
  if (v == null || isNaN(v)) return 'sem dado';
  const a = Math.abs(v);
  if (a >= 1e9) return 'R$ ' + decimal(v / 1e9, 2) + ' bi';
  if (a >= 1e6) return 'R$ ' + decimal(v / 1e6, 1) + ' mi';
  if (a >= 1e3) return 'R$ ' + decimal(v / 1e3, 0) + ' mil';
  return 'R$ ' + decimal(v, 0);
}

export function dataBR(iso) {
  if (!iso) return 'sem data';
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
  if (!m) return String(iso);
  return m[3] + '/' + m[2] + '/' + m[1] + (m[4] ? ' ' + m[4] + ':' + m[5] : '');
}

// Cria elemento sem usar innerHTML (os textos vem de fontes externas e nunca sao interpretados como HTML).
export function el(tag, attrs, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'texto') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const f of filhos.flat()) if (f != null) e.append(f.nodeType ? f : document.createTextNode(String(f)));
  return e;
}

export const limpar = no => { while (no.firstChild) no.removeChild(no.firstChild); return no; };
export const seguro = url => /^https?:\/\//i.test(url || '') ? url : null;

const cache = new Map();
// Le um JSON de dados. Devolve null se o arquivo nao existir (modulo ainda nao coletado).
export function carregar(caminho) {
  if (!cache.has(caminho)) {
    cache.set(caminho, fetch(caminho, {cache: 'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null));
  }
  return cache.get(caminho);
}

export function tabela(colunas, linhas, numericas = []) {
  const t = el('table', null,
    el('thead', null, el('tr', null, colunas.map((c, i) => el('th', {scope: 'col', class: numericas.includes(i) ? 'n' : ''}, c)))),
    el('tbody', null, linhas.map(l => el('tr', null, l.map((c, i) => el('td', {class: numericas.includes(i) ? 'n' : ''}, c))))));
  return el('div', {class: 'tabela-rolavel'}, t);
}

export function verTabela(titulo, colunas, linhas, numericas) {
  return el('details', null, el('summary', null, titulo || 'Ver os números em tabela'), tabela(colunas, linhas, numericas));
}
