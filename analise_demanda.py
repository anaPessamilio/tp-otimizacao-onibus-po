"""
Resultados condicionados à demanda e testes de robustez.

1. Varredura de λ (demanda = inf + λ (sup - inf)): para cada nível de demanda,
   solução ótima, grade atual (GTFS) avaliada com as mesmas regras, frota
   necessária para o melhor atendimento possível e maior preço-sombra da frota.
2. Robustez no cenário central: perfil horário típico (independente da grade
   atual, para testar a circularidade da demanda) e modo "perda" (passageiro
   não atendido desiste) em vez de "espera".
"""

import pandas as pd
from gurobipy import GRB

import config
from cria_instancia_teste import lambda_efetivo, montar_instancia
from modelo import avaliar_grade, construir_modelo, resolver_modelo

LAMBDAS = sorted({0.0, 0.25, lambda_efetivo(), 0.5, 0.75, 1.0, 1.25})


def frota_necessaria(df):
    """Menor frota que alcança o menor nível de não atendimento possível
    (com frota ilimitada, mantidos corredor e padrão de serviço)."""
    tipos = {"articulado": dict(config.TIPOS_VEICULO["articulado"], frota=1000),
             "padron": dict(config.TIPOS_VEICULO["padron"], frota=0)}
    # 1) menor não atendimento possível
    m = construir_modelo(df, 1.0, 0.0, tipos=tipos, nome="w_min")
    m["model"].setObjective(m["deficit"], GRB.MINIMIZE)
    m["model"].optimize()
    w_min = m["deficit"].getValue()
    # 2) menor frota (variável Φ no lado direito de R1) com esse atendimento
    m = construir_modelo(df, 1.0, 0.0, tipos=tipos, nome="frota_min")
    model = m["model"]
    phi = model.addVar(lb=0, name="frota")
    for constr in m["r1"].values():
        model.chgCoeff(constr, phi, -1.0)
        constr.RHS = 0.0
    model.addConstr(m["deficit"] <= w_min + 1e-6)
    model.setObjective(phi, GRB.MINIMIZE)
    model.optimize()
    return phi.X, w_min


def maior_preco_sombra(df):
    m = construir_modelo(df, config.ALPHA_1, config.ALPHA_2, nome="relax")
    lp = m["model"].relax()
    lp.Params.OutputFlag = 0
    lp.optimize()
    precos = [-lp.getConstrByName(c.ConstrName).Pi for c in m["r1"].values()]
    return max(0.0, max(precos)), lp.ObjVal


linhas = []
for lam in LAMBDAS:
    inst = montar_instancia(lambda_demanda=lam)
    res = resolver_modelo(inst, nome=f"lambda_{lam}")
    grade = avaliar_grade(inst)
    frota_nec, w_min = frota_necessaria(inst)
    preco, z_lp = maior_preco_sombra(inst)
    dem = res["demanda_total"]
    viagens_gtfs = inst["viagens_gtfs"].sum()
    linhas.append({
        "lambda": lam,
        "demanda_dia": dem,
        "embarques_por_viagem_gtfs": round(dem / viagens_gtfs, 1),
        "viagens_otimo": int(res["detalhe"]["frequencia_otima"].sum()),
        "viagens_gtfs": int(viagens_gtfs),
        "custo_otimo": round(res["custo_operacional"], 2),
        "custo_gtfs": round(grade["custo_operacional"], 2),
        "nao_atendidos_otimo": round(res["passageiros_represados"], 0),
        "nao_atendidos_gtfs": round(grade["passageiros_represados"], 0),
        "espera_min_otimo": round(res["espera_media_min"], 2),
        "espera_min_gtfs": round(grade["espera_media_min"], 2),
        "Z_otimo": round(res["valor_obj_Z"], 2),
        "Z_gtfs": round(grade["valor_obj_Z"], 2),
        "frota_max_usada": round(res["frota_por_faixa"].max(), 1),
        "frota_necessaria": round(frota_nec, 1),
        "nao_atendidos_minimo_possivel": round(w_min, 0),
        # faixas em que o corredor está no limite na solução ótima: quando o
        # corredor passa a limitar, parte da espera é inevitável e a frota
        # necessária para o "melhor atendimento possível" pode até cair
        "faixas_corredor_no_limite": int((res["detalhe"].groupby("faixa_horaria")["frequencia_otima"].sum()
                                          >= res["cap_corredor"]).sum()),
        "maior_preco_sombra_frota": round(preco, 2),
        "gap_integralidade_pct": round(100 * (res["valor_obj_Z"] - z_lp) / res["valor_obj_Z"], 2),
    })

df_lam = pd.DataFrame(linhas)
df_lam.to_csv("analise_demanda_lambda.csv", index=False)

# ---------------------------------------------------------------- robustez (λ do config)
rob = []
casos = [
    ("Base (perfil GTFS, fila)", {}, {}),
    ("Perfil horário típico (independente da grade)", {"perfil": "tipico"}, {}),
    ("Não atendido desiste (modo perda)", {}, {"nao_atendidos": "perda"}),
]
for nome, kw_inst, kw_mod in casos:
    inst = montar_instancia(**kw_inst)
    res = resolver_modelo(inst, nome=nome[:30], **kw_mod)
    grade = avaliar_grade(inst, **kw_mod)
    rob.append({
        "caso": nome,
        "viagens_otimo": int(res["detalhe"]["frequencia_otima"].sum()),
        "custo_otimo": round(res["custo_operacional"], 2),
        "nao_atendidos_otimo": round(res["passageiros_represados"], 0),
        "indicador_otimo": round(res["espera_media_min"] if res["espera_media_min"] is not None
                                 else res["pct_perdidos"], 2),
        "unidade": "min/passageiro" if res["espera_media_min"] is not None else "% perdidos",
        "nao_atendidos_gtfs": round(grade["passageiros_represados"], 0),
        "frota_max_usada": round(res["frota_por_faixa"].max(), 1),
    })
df_rob = pd.DataFrame(rob)
df_rob.to_csv("analise_robustez.csv", index=False)

print("=== RESULTADOS POR NÍVEL DE DEMANDA (λ) ===")
print(df_lam.to_string(index=False))
print(f"\n=== ROBUSTEZ (λ = {lambda_efetivo():.3f}) ===")
print(df_rob.to_string(index=False))
print("\nArquivos: 'analise_demanda_lambda.csv' e 'analise_robustez.csv'.")
