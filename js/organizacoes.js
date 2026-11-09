"use strict";
(function () {
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function get(url) { return fetch(url, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(url); return r.json(); }); }
  function dataBr(iso) { try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return iso || ""; } }

  // Abas acessíveis
  var abas = [["t-os", "p-os"], ["t-cebas", "p-cebas"]];
  abas.forEach(function (par) {
    $(par[0]).addEventListener("click", function () {
      abas.forEach(function (o) { $(o[0]).setAttribute("aria-selected", o[0] === par[0] ? "true" : "false"); $(o[1]).hidden = o[1] !== par[1]; });
    });
  });

  function estado(p) {
    if (p.acessado === false && /bloqueia/.test(p.robots || "")) return ["e-bloqueada", "Bloqueada para leitura automática"];
    if (p.acessado === false) return ["e-validar", "Sem acesso nesta rodada"];
    return ["e-aberta", "Página pública acessível"];
  }
  function cartao(titulo, p, extra) {
    var e = estado(p), links = (p.links_de_interesse || []).slice(0, 5).map(function (l) {
      return "<li><a href='" + esc(l.href) + "' rel='noopener'>" + esc(l.texto || l.href) + "</a></li>";
    }).join("");
    return "<div class='cartao-fonte'><h3>" + esc(titulo) + "</h3><span class='selo-estado " + e[0] + "'>" + e[1] + "</span>" +
      "<p class='fonte'>Verificado em " + dataBr(p.verificado_em) + ". " + esc(p.robots || "") + (extra || "") + "</p>" + (links ? "<ul>" + links + "</ul>" : "") + "</div>";
  }

  Promise.all([get("../dados/fontes_portais_uf.json").catch(function () { return null; }), get("../dados/fontes_siscebas.json").catch(function () { return null; })]).then(function (v) {
    var pt = v[0], sc = v[1], ultima = "";
    $("portais").innerHTML = pt ? pt.portais.map(function (p) {
      return cartao("Portal de transparência: " + p.nome, p, p.status_cadastro ? " Endereço: " + p.status_cadastro + "." : "");
    }).join("") : "<p>A verificação dos portais estaduais ainda não rodou.</p>";
    $("siscebas").innerHTML = sc ? sc.paginas.map(function (p) { return cartao(p.titulo || p.url, p); }).join("") +
      "<div class='cartao-fonte'><h3>Dados abertos sobre CEBAS</h3><p>" + esc(sc.conclusao) + "</p></div>" : "<p>A verificação do SisCEBAS ainda não rodou.</p>";
    ultima = (sc && sc.gerado_em) || (pt && pt.gerado_em) || "";
    $("selo").textContent = ultima ? "Fontes verificadas em " + dataBr(ultima) + ". Atualização semanal, conforme a disponibilidade da fonte oficial." : "Fontes ainda não verificadas.";
  });
})();
