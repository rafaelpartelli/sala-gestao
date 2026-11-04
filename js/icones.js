// Icones de traço (24 x 24), todos desenhados para este painel. Textos fixos, sem dado externo.
const P = {
  resumo: '<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"/>',
  mapa: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  dengue: '<ellipse cx="12" cy="14" rx="2.8" ry="5"/><circle cx="12" cy="7" r="1.9"/><path d="M9.3 12 4 8M14.7 12 20 8M9.3 15.5 4 18M14.7 15.5 20 18M12 5.2V3"/>',
  chik: '<circle cx="12" cy="12" r="4"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
  rede: '<path d="M4 21V7l8-4 8 4v14M2 21h20M12 9v6M9 12h6"/>',
  pessoal: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2c2.8.3 5 2.7 5 5.8"/>',
  leitos: '<path d="M3 6v14M3 16h18v4M21 16v-3a3 3 0 0 0-3-3h-7v6"/><circle cx="7" cy="12" r="2"/>',
  fin: '<circle cx="12" cy="12" r="9"/><path d="M9 9.5c0-1 1.3-2 3-2s3 .8 3 2-1.3 1.8-3 2.3-3 1.2-3 2.3 1.3 2 3 2 3-1 3-2M12 6v1.5M12 16.5V18"/>',
  em: '<path d="M7 3h8l4 4v14H7zM15 3v4h4M10 14l2 2 4-4"/>',
  rec: '<path d="M3 10l9-6 9 6zM5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
  planos: '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6zM9 12l2 2 4-4"/>',
  aps: '<path d="M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.5A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z"/>',
  notas: '<path d="M4 4h12v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM16 8h4v10a2 2 0 0 1-2 2M7 8h6M7 12h6M7 16h4"/>',
  local: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2" fill="currentColor"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
  dado: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.2" fill="currentColor"/><circle cx="16" cy="8" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="8" cy="16" r="1.2" fill="currentColor"/><circle cx="16" cy="16" r="1.2" fill="currentColor"/>',
  check: '<path d="M5 12.5l5 5 9-10"/>',
  trilha: '<path d="M5 21V4M5 4h12l-2 4 2 4H5"/>',
  voltar: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  seta: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  cima: '<path d="M6 15l6-6 6 6"/>',
  taca: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 13v4M8 21h8M10 17h4"/>',
  fechar: '<path d="M6 6l12 12M18 6L6 18"/>'
};

export function icone(nome, tam = 20) {
  const t = document.createElement('template');
  t.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${tam}" height="${tam}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" class="icone">${P[nome] || P.resumo}</svg>`;
  return t.content.firstChild;
}

// Preenche todo elemento com data-ico="nome" (cabecalhos e botoes fixos do HTML).
export function preencherIcones(raiz = document) {
  raiz.querySelectorAll('[data-ico]:not([data-ico-ok])').forEach(n => {
    n.prepend(icone(n.dataset.ico, +n.dataset.tam || 20));
    n.setAttribute('data-ico-ok', '1');
  });
}
