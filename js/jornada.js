// Jornada: o visitante percorre as paradas (blocos) da Sala. Cada parada visitada libera uma descoberta calculada com os dados reais.
import {el, limpar} from './util.js';
import {icone} from './icones.js';
import {semMovimento} from './efeitos.js';

const CHAVE = 'sala_jornada_v1';
const ler = () => { try { return new Set(JSON.parse(localStorage.getItem(CHAVE) || '[]')); } catch { return new Set(); } };
const gravar = s => { try { localStorage.setItem(CHAVE, JSON.stringify([...s])); } catch { /* sem armazenamento: segue na memoria */ } };

// c: {paradas: [{id, rot, ico, pergunta, disp(), fato()}], surpreender(), irPara(id)}
export function montarJornada(c) {
  const raiz = document.getElementById('jornada'), fim = document.getElementById('mod-fim');
  const vistas = ler(), timers = new Map();
  let aberto = false, concluiuAgora = false;
  const toast = el('div', {class: 'toast', role: 'status', 'aria-live': 'polite'});
  document.body.append(toast);
  let tt = 0;
  const avisar = t => { toast.textContent = t; toast.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => toast.classList.remove('on'), 4200); };

  const disp = () => c.paradas.filter(p => p.disp());
  const feitas = () => disp().filter(p => vistas.has(p.id));
  const proxima = () => disp().find(p => !vistas.has(p.id));

  function anel(n, t) {
    const R = 18, C = 2 * Math.PI * R, k = t ? n / t : 0;
    const NS = 'http://www.w3.org/2000/svg', s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 44 44'); s.setAttribute('class', 'j-anel'); s.setAttribute('aria-hidden', 'true');
    s.innerHTML = `<circle cx="22" cy="22" r="${R}" class="j-anel-fundo"/><circle cx="22" cy="22" r="${R}" class="j-anel-valor" transform="rotate(-90 22 22)" stroke-dasharray="${(C * k).toFixed(1)} ${C.toFixed(1)}"/>`;
    return s;
  }

  function desenhar() {
    const ds = disp(), f = feitas(), n = f.length, t = ds.length, prox = proxima(), completo = t > 0 && n === t;
    limpar(raiz);
    const painel = el('div', {class: 'j-painel', id: 'j-painel', hidden: !aberto},
      el('div', {class: 'j-topo'}, el('h2', null, 'Sua jornada pela Sala'), el('button', {class: 'j-fechar', type: 'button', 'aria-label': 'Fechar a jornada', onclick: () => alternar(false)}, icone('fechar', 18))),
      el('p', {class: 'fonte'}, `${n} de ${t} paradas visitadas. Cada parada libera uma descoberta calculada com os dados do seu território.`),
      el('ol', {class: 'j-lista'}, ds.map(p => {
        const ok = vistas.has(p.id), fato = ok ? p.fato() : null;
        return el('li', {class: 'j-item' + (ok ? ' ok' : '')},
          el('button', {class: 'j-ir', type: 'button', onclick: () => { alternar(false); c.irPara(p.id); }},
            el('span', {class: 'j-ico'}, ok ? icone('check', 18) : icone(p.ico, 18)),
            el('span', {class: 'j-txt'}, el('strong', null, p.rot), el('small', null, ok ? (fato || 'Parada visitada.') : p.pergunta))));
      })),
      el('div', {class: 'j-acoes'},
        el('button', {class: 'botao botao-icone', type: 'button', onclick: () => { alternar(false); c.surpreender(); }}, icone('dado', 16), 'Surpreenda-me com um estado'),
        n ? el('button', {class: 'botao-link', type: 'button', onclick: () => { vistas.clear(); gravar(vistas); concluiuAgora = false; desenhar(); atualizarFim(); }}, 'Recomeçar a jornada') : null));
    const barra = el('button', {class: 'j-barra' + (completo ? ' completo' : ''), type: 'button', 'aria-expanded': String(aberto), 'aria-controls': 'j-painel', onclick: () => alternar(!aberto)},
      anel(n, t), el('span', {class: 'j-resumo'}, el('strong', null, completo ? 'Jornada completa' : `Jornada: ${n} de ${t} paradas`),
        el('small', null, completo ? 'Veja as descobertas ao final da página' : (prox ? `Próxima parada: ${prox.rot}` : 'Aguardando dados'))), icone('cima', 18));
    raiz.append(painel, barra);
  }
  function alternar(v) { aberto = v; desenhar(); if (v) raiz.querySelector('.j-ir')?.focus(); }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && aberto) alternar(false); });

  function atualizarFim() {
    const ds = disp(), completo = ds.length > 0 && feitas().length === ds.length;
    fim.hidden = !completo;
    if (!completo) return;
    limpar(fim).append(el('h2', {id: 'h-fim'}, icone('taca', 22), 'Você percorreu a Sala inteira'),
      el('p', null, `Resumo do que apareceu em cada parada (dados de ${c.nomeTerritorio()}):`),
      el('ul', {class: 'fim-lista'}, ds.map(p => el('li', null, el('strong', null, p.rot + ': '), p.fato() || 'sem descoberta calculada para este território.'))),
      el('p', null, 'Os números mudam conforme o território. Compare com outro estado ou use a sua localização.'),
      el('div', {class: 'j-acoes'}, el('button', {class: 'botao botao-icone', type: 'button', onclick: () => c.surpreender()}, icone('dado', 16), 'Surpreenda-me com outro estado'),
        el('a', {class: 'botao botao-icone', href: 'https://partelli.pro/'}, icone('seta', 16), 'Conhecer o trabalho de Rafael Partelli')));
  }

  function marcar(id) {
    if (vistas.has(id)) return;
    const p = c.paradas.find(x => x.id === id);
    if (!p || !p.disp()) return;
    vistas.add(id); gravar(vistas); c.novaConclusao = true;
    const t = disp().length, n = feitas().length;
    avisar(n === t ? 'Última parada visitada. Jornada completa!' : `Parada visitada: ${p.rot}. Descoberta liberada (${n} de ${t}).`);
    desenhar(); atualizarFim();
  }

  // Uma parada conta quando fica visivel por 1,5 s.
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    const id = e.target.dataset.parada;
    const ve = e.isIntersecting && e.intersectionRect.height >= Math.min(e.boundingClientRect.height * 0.3, window.innerHeight * 0.4);
    if (ve && !timers.has(id)) timers.set(id, setTimeout(() => marcar(id), semMovimento() ? 800 : 1500));
    else if (!ve && timers.has(id)) { clearTimeout(timers.get(id)); timers.delete(id); }
  }), {threshold: [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1]}) : null;
  c.paradas.forEach(p => { const s = document.getElementById('mod-' + p.id); if (s) { s.dataset.parada = p.id; io?.observe(s); } });

  // Botao "Proxima parada" no fim de cada bloco.
  function proximas() {
    document.querySelectorAll('.proxima').forEach(n => n.remove());
    const ds = disp();
    ds.forEach((p, i) => {
      const sec = document.getElementById('mod-' + p.id), nx = ds[i + 1];
      if (!sec || !nx) return;
      sec.append(el('div', {class: 'proxima'}, el('button', {class: 'botao botao-icone', type: 'button', onclick: () => c.irPara(nx.id)}, 'Próxima parada: ' + nx.rot, icone('seta', 16)), el('span', {class: 'fonte'}, nx.pergunta)));
    });
  }

  return {avisar, atualizar() { desenhar(); atualizarFim(); proximas(); }};
}
