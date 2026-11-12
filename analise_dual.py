"""
Dualidade e pós-otimização.

Um PLIM não tem variáveis duais; por isso:
1. Resolve-se a relaxação linear (f contínuo) pelo simplex e extraem-se os
   duais (preços-sombra), as folgas e os intervalos do lado direito (RHS
   ranging) das restrições de frota (R1) e de corredor (R3), e os duais de
   atendimento (R2).
2. Valida-se cada preço-sombra no problema inteiro: re-otimiza-se o PLIM com
   +1 veículo (R1) ou +1 partida/h (R3) naquela faixa e mede-se a redução de Z.
"""

import pandas as pd
from gurobipy import GRB

import config
from modelo import construir_modelo, resolver_modelo

df = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})

res_mip = resolver_modelo(df, nome="PLIM")
z_mip = res_mip["valor_obj_Z"]

m = construir_modelo(df, config.ALPHA_1, config.ALPHA_2, nome="Relaxacao")
lp = m["model"].relax()
lp.Params.OutputFlag = 0
lp.optimize()
if lp.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Relaxação linear sem solução ótima (status {lp.Status})")
z_lp = lp.ObjVal


def linha_dual(constr_lp, rotulo, faixa, delta_mip):
    usado = lp.getRow(constr_lp).getValue()
    return {
        "restricao": rotulo, "faixa_horaria": faixa,
        "uso_PL": round(usado, 2), "limite": round(constr_lp.RHS, 2),
        "folga": round(constr_lp.Slack, 2),
        # restrição <= em minimização: Pi <= 0; preço-sombra = -Pi (redução de Z)
        "preco_sombra": round(max(0.0, -constr_lp.Pi), 2),
        "rhs_valido_de": round(constr_lp.SARHSLow, 2),
        "rhs_valido_ate": round(constr_lp.SARHSUp, 2) if constr_lp.SARHSUp < GRB.INFINITY else None,
        "reducao_Z_PLIM_+1": delta_mip,
    }


linhas = []
# R1: +1 veículo do tipo k na faixa t
for (k, t), c in sorted(m["r1"].items(), key=lambda x: x[0][1]):
    r = lp.getConstrByName(c.ConstrName)
    res_t = resolver_modelo(df, frota_extra={(k, t): 1}, nome=f"mais1_{k}_{t}")
    linhas.append(linha_dual(r, f"Frota ({k})", t, round(z_mip - res_t["valor_obj_Z"], 2)))
# R3: +1 partida/h no corredor na faixa t
for t, c in sorted(m["r3"].items()):
    r = lp.getConstrByName(c.ConstrName)
    mm = construir_modelo(df, config.ALPHA_1, config.ALPHA_2, nome=f"corredor_{t}")
    mm["r3"][t].RHS = m["cap"] + 1
    mm["model"].optimize()
    linhas.append(linha_dual(r, "Corredor", t, round(z_mip - mm["model"].ObjVal, 2)))
duais = pd.DataFrame(linhas)

# ---------------------------------------------------------------- R2: regimes
tipo_ref = next(k for k, v in m["tipos"].items() if v["frota"] > 0)
regimes = []
for (l, t), c in m["r2"].items():
    r = lp.getConstrByName(c.ConstrName)
    pi = r.Pi  # restrição >=: custo marginal de 1 passageiro a mais em (l, t)
    w_lp = lp.getVarByName(m["w"][l, t].VarName).X
    c_por_lugar = m["c"][(l, t, tipo_ref)] / m["tipos"][tipo_ref]["capacidade"]
    if m["d"][(l, t)] == 0 and abs(pi) < 1e-9:
        regime = "sem demanda"
    elif w_lp > 1e-6:
        regime = "fila: passageiros esperando"
    elif abs(pi - c_por_lugar) < 1e-4:
        regime = "= c/C: frota com folga"
    elif pi > c_por_lugar:
        regime = "> c/C: frota ou corredor no limite"
    else:
        regime = "< c/C: capacidade sobra (padrão de serviço)"
    regimes.append({"linha": l, "faixa_horaria": t, "demanda": m["d"][(l, t)],
                    "dual_R2": round(pi, 3), "c_por_lugar": round(c_por_lugar, 3),
                    "regime": regime})
duais_r2 = pd.DataFrame(regimes)

duais.to_csv("analise_dual_frota.csv", index=False)
duais_r2.to_csv("analise_dual_atendimento.csv", index=False)

print("=== DUALIDADE E PÓS-OTIMIZAÇÃO ===")
print(f"Z do PLIM: R$ {z_mip:,.2f} | Z da relaxação linear: R$ {z_lp:,.2f} | "
      f"gap de integralidade: {100 * (z_mip - z_lp) / z_mip:.2f}%")
ativos = duais[(duais.preco_sombra > 1e-6) | (duais["reducao_Z_PLIM_+1"] > 1e-6)]
print("\nRestrições com valor marginal positivo (PL ou PLIM):")
print(ativos.to_string(index=False))
print("\nRegimes dos duais de atendimento (R2):")
print(duais_r2["regime"].value_counts().to_string())
print("\nArquivos: 'analise_dual_frota.csv' e 'analise_dual_atendimento.csv'.")
