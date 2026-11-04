#!/usr/bin/env python3
"""Equipamentos de saude por municipio (CNES, arquivos EQ do FTP do DATASUS).
Soma existentes, em uso e disponiveis ao SUS por grupo de equipamento (TIPEQUIP), por municipio, por estado e por natureza do estabelecimento.
Guarda tambem o total por tipo e codigo (TIPEQUIP-CODEQUIP) por estado, para detalhar equipamentos especificos depois de conferir a tabela oficial.
Nao guarda nomes de estabelecimentos. Saida: dados/equipamentos.json."""
import os, sys
import cnes_ftp, dbc
from comum import escrever_json, ler_json, agora, resumo_actions

# Grupos do campo TIPEQUIP (tabela de dominio do CNES). Conferir com a tabela oficial antes de decidir com base nelas.
TIPOS = {"1": "Diagnóstico por imagem", "2": "Infraestrutura", "3": "Métodos ópticos", "4": "Métodos gráficos",
         "5": "Manutenção da vida", "6": "Outros equipamentos", "7": "Odontologia", "8": "Audiologia"}
NATUREZAS = ("Pública", "Privada com fins lucrativos", "Privada sem fins lucrativos", "Pessoa física", "Outra")
CAMPOS = ["CNES", "CODUFMUN", "TIPEQUIP", "CODEQUIP", "QT_EXIST", "QT_USO", "IND_SUS", "NAT_JUR"]

def inteiro(v):
    try:
        return int(str(v).strip() or 0)
    except ValueError:
        return 0

def natureza(nat_jur):
    c = (nat_jur or "").strip()[:1]
    return NATUREZAS[int(c) - 1] if c in ("1", "2", "3", "4") else "Outra"

def agregar(registros, mapa6):
    """Devolve (por_mun, por_item, por_natureza, lidos, sem). por_mun[cod7][tipo]=[existe, em_uso, sus]."""
    por, itens, nats, lidos, sem = {}, {}, {}, 0, 0
    for r in registros:
        lidos += 1
        cod = mapa6.get((r.get("CODUFMUN") or "")[:6])
        if not cod:
            sem += 1
            continue
        tipo = (r.get("TIPEQUIP") or "").strip().lstrip("0") or "0"
        ex, uso = inteiro(r.get("QT_EXIST")), inteiro(r.get("QT_USO"))
        sus = ex if (r.get("IND_SUS") or "").strip().upper() in ("1", "S") else 0
        a = por.setdefault(cod, {}).setdefault(tipo, [0, 0, 0])
        a[0] += ex; a[1] += uso; a[2] += sus
        chave = f"{tipo}-{(r.get('CODEQUIP') or '').strip()}"
        b = itens.setdefault(chave, [0, 0, 0])
        b[0] += ex; b[1] += uso; b[2] += sus
        n = nats.setdefault(natureza(r.get("NAT_JUR")), {}).setdefault(tipo, 0)
        nats[natureza(r.get("NAT_JUR"))][tipo] = n + ex
    return por, itens, nats, lidos, sem

def main():
    terr = ler_json("dados/territorio.json")
    mapa6 = {m["cod"][:6]: m["cod"] for m in terr["municipios"]}
    uf_de = {m["cod"]: m["uf"] for m in terr["municipios"]}
    ufs = sorted(set(uf_de.values()))
    por_comp = cnes_ftp.agrupar(cnes_ftp.listar("EQ"), "EQ")
    comp = os.environ.get("COMPETENCIA") or cnes_ftp.competencia_completa(por_comp)
    if not comp:
        print("sem competencia completa no FTP")
        return 1
    mun, itens, nats, lidos, sem, falhas = {}, {}, {}, 0, 0, {}
    for uf in ufs:
        try:
            p, i, n, l, s = agregar(dbc.registros(cnes_ftp.baixar_arquivo("EQ", uf, comp), CAMPOS), mapa6)
            mun.update(p)
            for k, v in i.items():
                t = itens.setdefault(k, [0, 0, 0])
                for x in range(3):
                    t[x] += v[x]
            for nome, o in n.items():
                for tp, q in o.items():
                    nats.setdefault(nome, {})[tp] = nats.setdefault(nome, {}).get(tp, 0) + q
            lidos += l; sem += s
            print(f"{uf}: {l} linhas", flush=True)
        except Exception as e:
            falhas[uf] = f"{type(e).__name__}: {str(e)[:120]}"
            print("FALHA", uf, falhas[uf], flush=True)
    if len(falhas) > 2 or not mun:
        print("validacao falhou", falhas)
        return 1
    ufs_tot = {}
    for cod, d in mun.items():
        a = ufs_tot.setdefault(uf_de[cod], {})
        for t, v in d.items():
            x = a.setdefault(t, [0, 0, 0])
            for k in range(3):
                x[k] += v[k]
    total = sum(v[0] for d in mun.values() for v in d.values())
    escrever_json("dados/equipamentos.json", {"gerado_em": agora(), "fonte": "CNES, arquivos EQ do FTP do DATASUS (Ministério da Saúde)", "competencia": comp,
        "tipos": TIPOS, "campos": ["existentes", "em_uso", "disponiveis_ao_sus"], "observacao": "Equipamentos cadastrados no CNES por grupo. Grupos conforme a tabela de domínio do CNES (conferir com a tabela oficial).",
        "total_existentes": total, "ufs": dict(sorted(ufs_tot.items())), "natureza": nats, "itens": dict(sorted(itens.items())), "ufs_faltando": sorted(falhas), "mun": dict(sorted(mun.items()))})
    resumo_actions("Equipamentos (CNES, EQ)", [f"Competência: {comp}", f"Equipamentos existentes: {total}", f"Linhas lidas: {lidos}", f"Sem município: {sem}", f"Falhas: {falhas or 'nenhuma'}"])
    print(f"equipamentos={total} municipios={len(mun)} lidas={lidos}")
    return 1 if falhas else 0

if __name__ == "__main__":
    sys.exit(main())
