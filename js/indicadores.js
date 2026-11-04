// Camadas do mapa: cada indicador sabe calcular seu valor por estado e, quando a fonte permite, por municipio.
import {decimal} from './util.js';

const div = (a, b, f = 1) => (a != null && b) ? a / b * f : null;
const soma = v => (v || []).reduce((a, b) => a + b, 0);

// c: contexto do app {D, dengueUF, chikUF, redeUF, profUF}. Devolve so as camadas que tem dado.
export function indicadores(c) {
  const D = c.D, L = [];
  if (!D.terr) return L;
  const pop = u => D.terr.por_uf[u]?.pop_soma || 0;
  const porMun = (u, f) => { const o = {}; D.terr.municipios.forEach(m => { if (m.uf === u) o[m.cod] = f(m); }); return o; };

  if (D.leitos) {
    const ix = Object.fromEntries(D.leitos.campos.map((x, i) => [x, i]));
    L.push({id: 'leitos', ico: 'leitos', curto: 'Leitos SUS', rot: 'Leitos SUS por 1.000 habitantes', fmt: v => decimal(v, 2), fonte: D.leitos.fonte,
      uf: u => div(D.leitos.ufs[u]?.[ix.SUS], pop(u), 1000),
      mun: async u => porMun(u, m => div(D.leitos.mun[m.cod]?.[ix.SUS] ?? 0, m.pop, 1000))});
  }
  if (D.profRes) {
    L.push({id: 'medicos', ico: 'pessoal', curto: 'Médicos no SUS', rot: 'Vínculos de médicos que atendem o SUS por 1.000 habitantes', fmt: v => decimal(v, 2), fonte: D.profRes.fonte,
      uf: u => div(D.profRes.ufs[u]?.['Médicos']?.[1], pop(u), 1000),
      mun: async u => { const r = await c.profUF(u); return r ? porMun(u, m => div(r.m?.[m.cod]?.['Médicos']?.[1] ?? 0, m.pop, 1000)) : null; }});
  }
  if (D.redeRes) {
    L.push({id: 'rede', ico: 'rede', curto: 'Rede', rot: 'Estabelecimentos ativos por 10 mil habitantes', fmt: v => decimal(v, 1), fonte: D.redeRes.fonte,
      uf: u => div(D.redeRes.ufs[u]?.ativos, pop(u), 10000),
      mun: async u => { const r = await c.redeUF(u); return r ? porMun(u, m => div(r.m?.[m.cod]?.ativos ?? 0, m.pop, 10000)) : null; }});
  }
  if (D.equipes) {
    const aps = o => (o?.['70'] || 0) + (o?.['76'] || 0);
    L.push({id: 'aps', ico: 'aps', curto: 'Equipes de APS', rot: 'Equipes de Saúde da Família e de Atenção Primária por 10 mil habitantes', fmt: v => decimal(v, 2), fonte: D.equipes.fonte,
      uf: u => div(aps(D.equipes.ufs[u]), pop(u), 10000),
      mun: async u => porMun(u, m => div(aps(D.equipes.mun[m.cod]), m.pop, 10000))});
  }
  if (D.dengueRes) {
    L.push({id: 'dengue', ico: 'dengue', curto: 'Dengue', rot: 'Municípios em nível 3 ou 4 de dengue (%)', rotM: 'Dengue: incidência estimada por 100 mil habitantes', fmt: v => decimal(v, 0) + '%', fmtM: v => decimal(v, 0), fonte: D.dengueRes.fonte,
      uf: u => { const x = D.dengueRes.ufs[u]; return x?.municipios ? ((+x.niveis?.['3'] || 0) + (+x.niveis?.['4'] || 0)) / x.municipios * 100 : null; },
      mun: async u => { const dg = await c.dengueUF(u); if (!dg) return null; const o = {}; dg.m.forEach(l => { o[l[0]] = l[5]; }); return o; }});
  }
  if (D.chikRes) {
    L.push({id: 'chik', ico: 'chik', curto: 'Chikungunya', rot: 'Municípios em nível 3 ou 4 de chikungunya (%)', rotM: 'Chikungunya: incidência estimada por 100 mil habitantes', fmt: v => decimal(v, 0) + '%', fmtM: v => decimal(v, 0), fonte: D.chikRes.fonte,
      uf: u => { const x = D.chikRes.ufs[u]; return x?.municipios ? ((+x.niveis?.['3'] || 0) + (+x.niveis?.['4'] || 0)) / x.municipios * 100 : null; },
      mun: async u => { const dg = await c.chikUF(u); if (!dg) return null; const o = {}; dg.m.forEach(l => { o[l[0]] = l[5]; }); return o; }});
  }
  if (D.fin) {
    // Recursos ordinarios (fundo a fundo) dos fundos municipais, sem o Fundo Estadual: mesma metodologia do Radar de Recursos.
    L.push({id: 'fin', ico: 'fin', curto: 'Repasses', rot: 'Repasses fundo a fundo aos municípios por habitante no ano (R$)', fmt: v => 'R$ ' + decimal(v, 0), fonte: D.fin.fonte,
      uf: u => { const x = D.fin.dados.uf[u]; return x?.pop ? (x.fb - (x.fbEst || 0)) / x.pop : null; },
      mun: async u => { const r = c.recursosUF ? await c.recursosUF(u) : null; return r ? porMun(u, m => r.m?.[m.cod] ? div(r.m[m.cod].fb, m.pop) : null) : null; }});
    L.push({id: 'emendas', ico: 'rec', curto: 'Emendas pagas', rot: 'Emendas parlamentares pagas por habitante, pelo ano da proposta (R$)', fmt: v => 'R$ ' + decimal(v, 0), fonte: D.fin.fonte,
      uf: u => { const x = D.fin.dados.uf[u]; return x?.pop ? x.eg / x.pop : null; },
      mun: async u => { const r = c.recursosUF ? await c.recursosUF(u) : null; return r ? porMun(u, m => r.m?.[m.cod] ? div(r.m[m.cod].em[2], m.pop) : null) : null; }});
  }
  if (D.equip) {
    const tot = o => Object.values(o || {}).reduce((a, v) => a + (v[0] || 0), 0);
    L.push({id: 'equip', ico: 'rede', curto: 'Equipamentos', rot: 'Equipamentos de saúde cadastrados por 1.000 habitantes', fmt: v => decimal(v, 1), fonte: D.equip.fonte,
      uf: u => div(tot(D.equip.ufs[u]), pop(u), 1000),
      mun: async u => porMun(u, m => div(tot(D.equip.mun[m.cod]), m.pop, 1000))});
  }
  if (D.transf) {
    L.push({id: 'transf', ico: 'rec', curto: 'Transferências', rot: `Transferências da União em saúde por habitante (${D.transf.meses.length} meses, R$)`, fmt: v => 'R$ ' + decimal(v, 0), fonte: D.transf.fonte,
      uf: u => div(soma(D.transf.ufs[u]), pop(u)),
      mun: async u => porMun(u, m => div(soma(D.transf.mun[m.cod]), m.pop))});
  }
  if (D.desp) {
    L.push({id: 'desp', ico: 'fin', curto: 'Despesa', rot: `Despesa paga em saúde por habitante em ${D.desp.exercicio} (R$)`, fmt: v => 'R$ ' + decimal(v, 0), fonte: D.desp.fonte,
      uf: u => div(D.desp.ufs[u]?.[2], D.desp.ufs[u]?.[3]),
      mun: async u => porMun(u, m => { const a = D.desp.mun[m.cod]; return a ? div(a[2], a[3]) : null; })});
  }
  if (D.cauc) {
    L.push({id: 'cauc', ico: 'em', curto: 'CAUC', rot: 'Municípios com pendência no CAUC (%)', rotM: 'Itens com pendência no CAUC (quantidade)', fmt: v => decimal(v, 0) + '%', fmtM: v => decimal(v, 0), fonte: D.cauc.fonte,
      uf: u => { const x = D.cauc.ufs[u]; return x?.municipios ? x.com_pendencia / x.municipios * 100 : null; },
      mun: async u => porMun(u, m => (D.cauc.mun[m.cod] || []).length)});
  }
  if (D.ans) {
    L.push({id: 'planos', ico: 'planos', curto: 'Planos privados', rot: 'Cobertura de planos de assistência médica (%)', fmt: v => decimal(v, 1) + '%', fonte: D.ans.fonte,
      uf: u => div(D.ans.ufs[u]?.[0], D.ans.ufs[u]?.[1], 100),
      mun: async u => porMun(u, m => { const a = D.ans.mun[m.cod]; return a ? div(a[0], a[1], 100) : null; })});
  }
  return L;
}
