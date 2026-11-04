// Graficos simples em HTML e SVG: barras de ranking, barra empilhada de niveis e miniserie.
import {el} from './util.js';

// itens: [{nome, valor, rotulo}] ja ordenados. Uma cor, barra ancorada na linha de base.
export function ranking(itens, {max} = {}) {
  const topo = (max ?? Math.max(...itens.map(i => i.valor), 0)) || 1;
  return el('ol', {class: 'rank'}, itens.map(i =>
    el('li', {title: `${i.nome}: ${i.rotulo}`},
      el('span', {class: 'nome'}, i.nome),
      el('span', {class: 'trilho', 'aria-hidden': 'true'}, el('span', {class: 'barra', style: `width:${Math.max(0, i.valor) / topo * 100}%`})),
      el('span', {class: 'num'}, i.rotulo))));
}

export const NIVEIS = [
  {k: '1', nome: 'Nível 1 (verde)', cls: 'n1'},
  {k: '2', nome: 'Nível 2 (amarelo)', cls: 'n2'},
  {k: '3', nome: 'Nível 3 (laranja)', cls: 'n3'},
  {k: '4', nome: 'Nível 4 (vermelho)', cls: 'n4'},
  {k: 'sem_dado', nome: 'Sem dado', cls: 'n0'}
];

// niveis: {'1':n,'2':n,...}. Barra empilhada com legenda que traz a contagem (a cor nunca e a unica pista).
export function pilhaNiveis(niveis) {
  const total = NIVEIS.reduce((s, n) => s + (niveis[n.k] || 0), 0) || 1;
  const barra = el('div', {class: 'pilha', role: 'img', 'aria-label': 'Municípios por nível de alerta: ' + NIVEIS.map(n => `${n.nome} ${niveis[n.k] || 0}`).join(', ')},
    NIVEIS.filter(n => niveis[n.k]).map(n => el('span', {class: n.cls, style: `width:${niveis[n.k] / total * 100}%`, title: `${n.nome}: ${niveis[n.k]}`})));
  const leg = el('ul', {class: 'legenda'}, NIVEIS.map(n => el('li', null, el('i', {class: n.cls}), `${n.nome}: ${(niveis[n.k] || 0).toLocaleString('pt-BR')}`)));
  return el('div', null, barra, leg);
}

// serie: lista de numeros. SVG com linha de 2 px e ponto final.
export function miniserie(serie, {largura = 220, altura = 48} = {}) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${largura} ${altura}`);
  svg.setAttribute('class', 'spark');
  svg.setAttribute('width', largura);
  svg.setAttribute('height', altura);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Casos estimados nas últimas semanas: ' + serie.join(', '));
  if (serie.length < 2) return svg;
  const max = Math.max(...serie, 1), p = 5;
  const pts = serie.map((v, i) => [p + i * (largura - 2 * p) / (serie.length - 1), altura - p - v / max * (altura - 2 * p)]);
  const linha = document.createElementNS(NS, 'polyline');
  linha.setAttribute('points', pts.map(q => q.map(n => n.toFixed(1)).join(',')).join(' '));
  linha.setAttribute('fill', 'none'); linha.setAttribute('stroke', 'var(--barra)'); linha.setAttribute('stroke-width', '2');
  linha.setAttribute('stroke-linejoin', 'round'); linha.setAttribute('stroke-linecap', 'round');
  const ult = pts[pts.length - 1];
  const c = document.createElementNS(NS, 'circle');
  c.setAttribute('cx', ult[0]); c.setAttribute('cy', ult[1]); c.setAttribute('r', '4'); c.setAttribute('fill', 'var(--barra)');
  c.setAttribute('stroke', 'var(--superficie)'); c.setAttribute('stroke-width', '2');
  svg.append(linha, c);
  return svg;
}
