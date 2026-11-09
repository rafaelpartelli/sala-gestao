"use strict";
(function () {
  var R = null, P = null, T = null;
  var $ = function (id) { return document.getElementById(id); };
  var brl = function (v) { return v == null ? "sem dado" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }); };
  var pct = function (v) { return v == null ? "sem dado" : v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%"; };
  var FAIXAS = { ok: ["Dentro do limite", "✓"], alerta: ["Alerta (90% do limite)", "!"], prudencial: ["Prudencial (95% do limite)", "!!"], excedido: ["Limite excedido", "✕"] };

  function get(url) { return fetch(url, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(url); return r.json(); }); }
  function idx(campos, nome) { return campos.indexOf(nome); }
  function dataBr(iso) { try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return iso; } }

  function faixa(p) { // p = [dtp, rcl, limite_maximo, ...]
    if (!p || !p[2]) return null;
    var u = p[0] / p[2];
    return u > 1 ? "excedido" : u >= 0.95 ? "prudencial" : u >= 0.90 ? "alerta" : "ok";
  }

  function linhas(uf) {
    var cr = R.campos, cp = P ? P.campos : [];
    return T.municipios.filter(function (m) { return m.uf === uf && R.mun[String(m.cod)]; }).map(function (m) {
      var r = R.mun[String(m.cod)], p = P && P.mun[String(m.cod)];
      var tot = r[idx(cr, "total")], pop = r[idx(cr, "populacao")];
      return {
        nome: m.nome || String(m.cod), total: tot, pop: pop,
        percapita: pop ? tot / pop : null,
        dep: tot ? r[idx(cr, "transf_correntes")] / tot * 100 : null,
        trib: tot ? r[idx(cr, "tributaria")] / tot * 100 : null,
        pes: p ? p[idx(cp, "pct_rcl")] : null, faixa: faixa(p)
      };
    });
  }

  function desenhar() {
    var uf = $("selUF").value, ls = linhas(uf), ord = $("selOrd").value;
    ls.sort(function (a, b) {
      if (ord === "nome") return a.nome.localeCompare(b.nome, "pt-BR");
      var x = a[ord] == null ? -Infinity : a[ord], y = b[ord] == null ? -Infinity : b[ord];
      return y === x ? 0 : y > x ? 1 : -1;
    });
    var est = R.estados[uf], soma = ls.reduce(function (s, l) { return s + (l.total || 0); }, 0);
    $("kpis").innerHTML =
      kpi("Municípios com receita informada", ls.length + " de " + R.municipios_consultados, "SICONFI, RREO Anexo 01") +
      kpi("Receita realizada dos municípios", brl(soma), "Soma dos entregues, exercício " + R.exercicio) +
      kpi("Receita realizada do estado", est ? brl(est[0]) : "sem dado", "Governo estadual, mesmo exercício");
    var h = "<table><thead><tr><th>Município</th><th>Receita realizada</th><th>Por habitante</th><th>Dependência de transferências</th><th>Receita tributária</th><th>Pessoal (% da RCL)</th></tr></thead><tbody>";
    ls.forEach(function (l) {
      var f = l.faixa ? FAIXAS[l.faixa] : null;
      h += "<tr><th scope='row'>" + l.nome + "</th><td>" + brl(l.total) + "</td><td>" + brl(l.percapita) + "</td><td>" + pct(l.dep) + "</td><td>" + pct(l.trib) + "</td><td>" +
        (l.pes == null ? "sem dado" : pct(l.pes) + (f ? " <span class='faixa f-" + l.faixa + "'><span aria-hidden='true'>" + f[1] + "</span> " + f[0] + "</span>" : "")) + "</td></tr>";
    });
    $("tabela").innerHTML = h + "</tbody></table>";
    $("fonte").textContent = "Fonte: " + R.fonte + (P ? "; " + P.fonte : "") + ". Exercício " + R.exercicio + ", bimestre " + R.bimestre + ". " + R.observacao;
    var d = R.gerado_em;
    $("selo").textContent = "Dados do SICONFI atualizados em " + dataBr(d) + ". Atualização diária, conforme a disponibilidade da fonte oficial.";
  }

  function kpi(r, v, n) { return "<div class='kpi'><div class='rot'>" + r + "</div><div class='val'>" + v + "</div><div class='nota'>" + n + "</div></div>"; }

  Promise.all([get("../dados/receita.json"), get("../dados/pessoal.json").catch(function () { return null; }), get("../dados/territorio.json")]).then(function (v) {
    R = v[0]; P = v[1]; T = v[2];
    var sel = $("selUF");
    R.ufs.forEach(function (u) { var o = document.createElement("option"); o.value = u; o.textContent = u; sel.appendChild(o); });
    sel.addEventListener("change", desenhar); $("selOrd").addEventListener("change", desenhar);
    desenhar();
  }).catch(function () {
    $("selo").textContent = "Os dados ainda não foram coletados. Execute o workflow “Coletar receita e pessoal (SICONFI)” no GitHub.";
  });
})();
