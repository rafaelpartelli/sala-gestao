// Animacoes: entrada dos blocos, barras que crescem e numeros que sobem. Respeitam "reduzir movimento".
export const semMovimento = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let obs = null;
function observador() {
  if (!obs && 'IntersectionObserver' in window) {
    obs = new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) return;
      e.target.classList.add('vis');
      obs.unobserve(e.target);
      if (e.target.classList.contains('kpi')) contar(e.target.querySelector('.val'));
    }), {threshold: 0.12});
  }
  return obs;
}

// Marca como visiveis (com animacao) os elementos .rev ainda nao revelados.
export function revelar(raiz = document) {
  raiz.querySelectorAll('.rev:not(.vis)').forEach(n => {
    const o = observador();
    if (o && !semMovimento()) o.observe(n); else n.classList.add('vis');
  });
}

// Anima o primeiro numero do texto (formato pt-BR) de 0 ate o valor, mantendo prefixo e sufixo.
export function contar(no) {
  if (!no || no.dataset.ok || semMovimento()) return;
  no.dataset.ok = '1';
  const txt = no.textContent;
  const m = txt.match(/\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?/);
  if (!m) return;
  const alvo = parseFloat(m[0].replace(/\./g, '').replace(',', '.'));
  if (!isFinite(alvo) || alvo === 0) return;
  const dec = m[0].includes(',') ? m[0].split(',')[1].length : 0;
  const pre = txt.slice(0, m.index), pos = txt.slice(m.index + m[0].length);
  const t0 = performance.now(), dur = 900;
  const passo = t => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    no.textContent = k < 1 ? pre + (alvo * e).toLocaleString('pt-BR', {minimumFractionDigits: dec, maximumFractionDigits: dec}) + pos : txt;
    if (k < 1) requestAnimationFrame(passo);
  };
  requestAnimationFrame(passo);
}
