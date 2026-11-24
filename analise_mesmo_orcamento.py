"""
Comparação com a grade atual SEM gastar mais: qual o menor número de
passageiros não atendidos que se consegue com o mesmo orçamento da grade
programada pela BHTRANS (GTFS)?

Para cada caso resolve-se, lexicograficamente,
    1) min Σ w            s.a. custo <= custo da grade atual
                               Σ f   <= viagens da grade atual
                               + todas as restrições do modelo
    2) min custo          s.a. o mesmo, com Σ w no valor ótimo de (1).

Variantes:
  "mesmo orçamento":                 o modelo pode realocar viagens entre linhas
                                     e entre horas;
  "mesmo orçamento e viagens/linha": cada linha mantém o total diário de
                                     viagens da grade atual -- só a distribuição
                                     HORÁRIA muda. Separa o ganho de realocar
                                     entre linhas (que depende do rateio dos
                                     embarques das estações) do ganho de
                                     redistribuir no tempo.

Para que a grade atual seja uma solução viável do modelo (e o ótimo nunca seja
pior que ela), f_min é limitado às viagens do GTFS nos pares em que a grade
atual fica abaixo do padrão de serviço; a frota (97) e o corredor (64/h) já
são, por definição, os valores exigidos pela grade atual. A grade atual entra
como solução inicial (MIP start), de modo que mesmo com tempo limite o
resultado é pelo menos tão bom quanto ela.

Casos: perfil horário do GTFS em vários λ; perfil horário típico (independente
da grade) no λ calibrado; modos "perda" e "espera".
"""

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

from cria_instancia_teste import lambda_efetivo, montar_instancia
from modelo import avaliar_grade, construir_modelo, tem_solucao

LAM_CAL = lambda_efetivo()
LAMBDAS = sorted({0.0, 0.25, LAM_CAL, 0.5, 0.75, 1.0})
VARIANTES = {"mesmo orçamento": False, "mesmo orçamento e viagens/linha": True}
MODOS = ["perda", "espera"]


def instancia_comparavel(inst):
    """f_min <= viagens do GTFS onde a linha opera hoje: a grade atual passa a
    ser viável no modelo. Devolve a instância e os pares ajustados."""
    d = inst.copy()
    abaixo = (d["opera_no_gtfs"] == 1) & (d["viagens_gtfs"] < d["f_min"])
    ajustados = d.loc[abaixo, ["route_short_name", "faixa_horaria", "viagens_gtfs", "f_min"]]
    d.loc[abaixo, "f_min"] = d.loc[abaixo, "viagens_gtfs"]
    return d, ajustados


def resolver_mesmo_orcamento(inst, modo, viagens_por_linha_fixas):
    grade = avaliar_grade(inst, nao_atendidos=modo)
    m = construir_modelo(inst, 1.0, 0.0, nao_atendidos=modo, nome="mesmo_orcamento")
    model, f, K = m["model"], m["f"], m["K"]
    model.addConstr(m["custo_operacional"] <= grade["custo_operacional"] + 1e-6, name="orcamento")
    model.addConstr(gp.quicksum(f.values()) <= grade["viagens"], name="viagens")
    if viagens_por_linha_fixas:
        for l, g in inst.groupby("route_short_name"):
            model.addConstr(gp.quicksum(f[l, t, k] for t in g["faixa_horaria"] for k in K)
                            == int(g["viagens_gtfs"].sum()), name=f"viagens_l{l}")

    # grade atual como solução inicial (articulados)
    gtfs = inst.set_index(["route_short_name", "faixa_horaria"])["viagens_gtfs"].to_dict()
    for (l, t, k), var in f.items():
        var.Start = gtfs[(l, t)] if k == "articulado" else 0

    # 1) menor não atendimento
    model.setObjective(m["deficit"], GRB.MINIMIZE)
    model.optimize()
    if not tem_solucao(model):
        raise RuntimeError(f"Sem solução (status {model.Status})")
    w_otimo, provado_1 = m["deficit"].getValue(), model.Status == GRB.OPTIMAL
    # 2) menor custo com esse atendimento
    model.addConstr(m["deficit"] <= w_otimo + 1e-6 + 1e-9 * abs(w_otimo), name="lex")
    model.setObjective(m["custo_operacional"], GRB.MINIMIZE)
    model.optimize()
    if not tem_solucao(model):
        raise RuntimeError(f"Sem solução na 2a etapa (status {model.Status})")

    det = pd.DataFrame([{"linha": l, "faixa_horaria": t,
                         "viagens": sum(round(f[l, t, k].X) for k in K),
                         "nao_atendidos": m["w"][l, t].X,
                         "custo": sum(m["c"][(l, t, k)] * round(f[l, t, k].X) for k in K)}
                        for (l, t) in m["pares"]])
    return grade, {
        "viagens": int(det["viagens"].sum()),
        "custo": m["custo_operacional"].getValue(),
        "nao_atendidos": m["deficit"].getValue(),
        "otimo_provado": provado_1 and model.Status == GRB.OPTIMAL,
        "detalhe": det,
    }


casos = [("gtfs", lam) for lam in LAMBDAS] + [("tipico", LAM_CAL)]
resumo, por_linha, ajustes = [], [], None
for perfil, lam in casos:
    inst, ajustados = instancia_comparavel(montar_instancia(lambda_demanda=lam, perfil=perfil))
    if perfil == "gtfs" and ajustes is None:
        ajustes = ajustados
    demanda = inst["d_lt"].sum()
    for modo in MODOS:
        for variante, fixa in VARIANTES.items():
            grade, ot = resolver_mesmo_orcamento(inst, modo, fixa)
            fator = 60 if modo == "espera" else 100  # min/passageiro ou % perdidos
            g_w = grade["passageiros_represados"]
            resumo.append({
                "perfil": perfil, "lambda": round(lam, 3), "modo": modo, "variante": variante,
                "demanda": demanda,
                "viagens_gtfs": int(grade["viagens"]), "viagens_otimo": ot["viagens"],
                "custo_gtfs": round(grade["custo_operacional"], 2), "custo_otimo": round(ot["custo"], 2),
                "nao_atendidos_gtfs": round(g_w, 1), "nao_atendidos_otimo": round(ot["nao_atendidos"], 1),
                "indicador_gtfs": round(fator * g_w / demanda, 2),
                "indicador_otimo": round(fator * ot["nao_atendidos"] / demanda, 2),
                "unidade": "min/passageiro" if modo == "espera" else "% perdidos",
                "reducao_pct": round(100 * (1 - ot["nao_atendidos"] / g_w), 1) if g_w > 1e-6 else None,
                "otimo_provado": ot["otimo_provado"],
            })
            if perfil == "gtfs" and abs(lam - LAM_CAL) < 1e-9 and modo == "perda" and not fixa:
                g = grade["detalhe"].groupby("linha")
                o = ot["detalhe"].groupby("linha")
                por_linha = pd.DataFrame({
                    "viagens_gtfs": g["frequencia"].sum().astype(int),
                    "viagens_otimo": o["viagens"].sum(),
                    "perdidos_gtfs": g["passageiros_represados"].sum().round(0),
                    "perdidos_otimo": o["nao_atendidos"].sum().round(0),
                    "custo_gtfs": g["custo_operacional_R$"].sum().round(2),
                    "custo_otimo": o["custo"].sum().round(2),
                })
            print(f"[{perfil}, λ={lam:.3f}, {modo}, {variante}] "
                  f"GTFS {g_w:,.0f} -> ótimo {ot['nao_atendidos']:,.0f} | "
                  f"custo R$ {grade['custo_operacional']:,.0f} -> R$ {ot['custo']:,.0f} | "
                  f"viagens {grade['viagens']:.0f} -> {ot['viagens']}")

df = pd.DataFrame(resumo)
df.to_csv("comparacao_mesmo_orcamento.csv", index=False)
por_linha.index.name = "linha"
por_linha.reset_index().to_csv("comparacao_mesmo_orcamento_linhas.csv", index=False)
ajustes.to_csv("comparacao_mesmo_orcamento_fmin_ajustado.csv", index=False)

print(f"\nPares em que a grade atual fica abaixo do padrão de serviço (f_min ajustado):")
print(ajustes.to_string(index=False))
print(f"\nPor linha (perfil GTFS, λ = {LAM_CAL:.3f}, modo perda, mesmo orçamento):")
print(por_linha.to_string())
print("\nArquivos: 'comparacao_mesmo_orcamento.csv', '..._linhas.csv' e '..._fmin_ajustado.csv'.")
