// Geografia: malhas do IBGE (carregadas no navegador), projecao para SVG e localizacao do visitante.
// A posicao do visitante fica so no navegador: nao e enviada nem gravada. O IBGE recebe apenas o pedido da malha.
export const COD_UF = {RO: 11, AC: 12, AM: 13, RR: 14, PA: 15, AP: 16, TO: 17, MA: 21, PI: 22, CE: 23, RN: 24, PB: 25, PE: 26, AL: 27, SE: 28, BA: 29, MG: 31, ES: 32, RJ: 33, SP: 35, PR: 41, SC: 42, RS: 43, MS: 50, MT: 51, GO: 52, DF: 53};
export const UF_POR_COD = Object.fromEntries(Object.entries(COD_UF).map(([s, c]) => [String(c), s]));

const BASE = 'https://servicodados.ibge.gov.br/api/v3/malhas';
const memo = new Map();
function pedir(url) {
  if (!memo.has(url)) {
    const p = fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(j => (j && Array.isArray(j.features) && j.features.length) ? j : null).catch(() => null);
    memo.set(url, p);
    p.then(v => { if (!v) memo.delete(url); });
  }
  return memo.get(url);
}
export const malhaBR = () => pedir(`${BASE}/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF`);
export const malhaUF = uf => COD_UF[uf] ? pedir(`${BASE}/estados/${COD_UF[uf]}?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio`) : Promise.resolve(null);

export const codigoArea = f => String(f?.properties?.codarea ?? f?.properties?.CD_MUN ?? f?.properties?.codigo ?? '');
const poligonos = g => !g ? [] : g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];

// Projecao equiretangular corrigida pela latitude media. Devolve caminhos SVG por codigo e a funcao ponto(lon, lat).
export function projetar(fc, largura = 600, altura = 560) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  fc.features.forEach(f => poligonos(f.geometry).forEach(p => p.forEach(r => r.forEach(([x, y]) => {
    if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
  }))));
  const fx = Math.cos(((y0 + y1) / 2) * Math.PI / 180);
  const k = Math.min(largura / ((x1 - x0) * fx), altura / (y1 - y0));
  const w = (x1 - x0) * fx * k, h = (y1 - y0) * k, pad = 4;
  const ponto = (lon, lat) => [(lon - x0) * fx * k + pad, (y1 - lat) * k + pad];
  const itens = fc.features.map(f => {
    let d = '';
    poligonos(f.geometry).forEach(p => p.forEach(anel => {
      let ult = '';
      const pts = [];
      anel.forEach(([x, y]) => { const [a, b] = ponto(x, y), s = a.toFixed(1) + ' ' + b.toFixed(1); if (s !== ult) { pts.push(s); ult = s; } });
      if (pts.length > 2) d += 'M' + pts.join('L') + 'Z';
    }));
    return {cod: codigoArea(f), d};
  }).filter(i => i.d);
  return {viewBox: `0 0 ${(w + 2 * pad).toFixed(1)} ${(h + 2 * pad).toFixed(1)}`, itens, ponto};
}

function dentroAnel(x, y, anel) {
  let dentro = false;
  for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) {
    const [xi, yi] = anel[i], [xj, yj] = anel[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}
export const pontoNaFeicao = (lon, lat, f) => poligonos(f.geometry).some(p => dentroAnel(lon, lat, p[0]) && !p.slice(1).some(h => dentroAnel(lon, lat, h)));

export function localizar() {
  return new Promise((ok, erro) => {
    if (!navigator.geolocation) return erro(new Error('indisponivel'));
    navigator.geolocation.getCurrentPosition(p => ok({lat: p.coords.latitude, lon: p.coords.longitude}), e => erro(e), {enableHighAccuracy: false, timeout: 12000, maximumAge: 600000});
  });
}

// Descobre estado e municipio (codigo de 7 digitos) de um ponto. municipios: lista da base territorial.
export async function descobrirTerritorio(lat, lon, municipios) {
  const br = await malhaBR();
  if (!br) throw new Error('malha');
  const fUF = br.features.find(f => pontoNaFeicao(lon, lat, f));
  const uf = fUF && UF_POR_COD[codigoArea(fUF).slice(0, 2)];
  if (!uf) return null;
  const mu = await malhaUF(uf);
  let cod = null;
  if (mu) {
    const fm = mu.features.find(f => pontoNaFeicao(lon, lat, f));
    if (fm) { const c = codigoArea(fm); cod = c.length === 7 ? c : (municipios.find(m => m.cod.startsWith(c))?.cod || null); }
  }
  return {uf, cod};
}
