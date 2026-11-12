"""
Análise de dualidade e pós-otimização do modelo de frequências.

1. Relaxação linear (f contínuo): valor ótimo e gap de integralidade.
2. Preços-sombra (variáveis duais) da restrição de frota R1 em cada faixa:
   quanto Z diminui com 1 veículo a mais em operação naquela hora, e o
   intervalo do lado direito em que esse preço continua válido (ranging).
3. Duais da restrição de atendimento R2: custo marginal de 1 passageiro a
   mais em cada (linha, faixa).
4. Validação no problema inteiro: ΔZ real ao aumentar em 1 o limite de frota
   de cada faixa (re-otimizando o PLIM), comparado ao preço-sombra do PL.
"""

import pandas as pd
from gurobipy import GRB

from config import ALPHA_1, ALPHA_2, FROTA_MAX
from modelo import construir_modelo, resolver_modelo

df = pd.read_csv("instancia_modelo_bhtrans.csv")

# ---------------------------------------------------------------- PLIM
res_mip = resolver_modelo(df, FROTA_MAX, ALPHA_1, ALPHA_2, nome="PLIM")
z_mip = res_mip["valor_obj_Z"]

# ---------------------------------------------------------------- relaxação linear
m = construir_modelo(df, FROTA_MAX, ALPHA_1, ALPHA_2, nome="Relaxacao_PL")
m["model"].update()  # necessário para os nomes das restrições
lp = m["model"].relax()
lp.update()
lp.Params.OutputFlag = 0
lp.optimize()
if lp.Status != GRB.OPTIMAL:
    raise RuntimeError(f"Relaxação linear sem solução ótima (status {lp.Status})")
z_lp = lp.ObjVal

# ---------------------------------------------------------------- duais de R1
linhas_r1 = []
for t in sorted(m["r1"]):
    r = lp.getConstrByName(f"Limite_Frota_t{t}")
    usado = lp.getRow(r).getValue()
    linhas_r1.append({
        "faixa_horaria": t,
        "frota_em_operacao_PL": round(usado, 2),
        "folga": round(r.Slack, 2),
        # restrição <= num problema de minimização: Pi <= 0; o preço-sombra
        # (redução de Z por veículo adicional) é -Pi.
        "preco_sombra_R$_por_veiculo": round(max(0.0, -r.Pi), 2),
        "rhs_valido_de": round(r.SARHSLow, 2),
        "rhs_valido_ate": round(r.SARHSUp, 2) if r.SARHSUp < GRB.INFINITY else None,
    })
duais_r1 = pd.DataFrame(linhas_r1)

# ---------------------------------------------------------------- validação inteira (+1 veículo)
delta_mip = []
for t in duais_r1["faixa_horaria"]:
    limite = {s: FROTA_MAX for s in m["r1"]}
    limite[t] = FROTA_MAX + 1
    res_t = resolver_modelo(df, limite, ALPHA_1, ALPHA_2, nome=f"PLIM_mais1_t{t}")
    delta_mip.append(round(z_mip - res_t["valor_obj_Z"], 2))
duais_r1["reducao_Z_PLIM_+1_veiculo"] = delta_mip

# ---------------------------------------------------------------- duais de R2
alpha2 = ALPHA_2
linhas_r2 = []
for (l, t) in m["pares"]:
    r = lp.getConstrByName(f"Atendimento_l{l}_t{t}")
    pi = r.Pi  # restrição >=: Pi >= 0 = custo marginal de 1 passageiro a mais
    c_por_pas = m["c"][(l, t)] / m["C"][(l, t)]
    if m["d"][(l, t)] == 0:
        regime = "sem demanda"
    elif abs(pi - alpha2) < 1e-6:
        regime = "passageiro excedente não atendido (= α2)"
    elif abs(pi - c_por_pas) < 1e-6:
        regime = "atendido; frota com folga (= c/C)"
    elif pi > c_por_pas + 1e-6:
        regime = "atendido; frota no limite (> c/C)"
    else:
        regime = "outro (limites de f)"
    linhas_r2.append({
        "linha": l, "faixa_horaria": t, "demanda": m["d"][(l, t)],
        "dual_R$_por_passageiro": round(pi, 3),
        "custo_viagem_por_lugar": round(c_por_pas, 3),
        "regime": regime,
    })
duais_r2 = pd.DataFrame(linhas_r2)

duais_r1.to_csv("analise_dual_frota.csv", index=False)
duais_r2.to_csv("analise_dual_atendimento.csv", index=False)

# ---------------------------------------------------------------- relatório
print("=== DUALIDADE E PÓS-OTIMIZAÇÃO ===")
print(f"Z do PLIM (inteiro):        R$ {z_mip:,.2f}")
print(f"Z da relaxação linear (PL): R$ {z_lp:,.2f}")
print(f"Gap de integralidade:       {100 * (z_mip - z_lp) / z_mip:.2f}%")

print("\n--- R1: preço-sombra da frota por faixa horária ---")
print("(redução de Z, em R$, com 1 veículo a mais em operação na faixa)")
print(duais_r1.to_string(index=False))

ativas = duais_r1[duais_r1["preco_sombra_R$_por_veiculo"] > 1e-6]
print(f"\nFaixas com frota no limite (preço-sombra > 0): {ativas['faixa_horaria'].tolist()}")
if not ativas.empty:
    top = ativas.sort_values("preco_sombra_R$_por_veiculo", ascending=False).iloc[0]
    print(
        f"Maior valor marginal: {int(top.faixa_horaria)}h, "
        f"R$ {top['preco_sombra_R$_por_veiculo']:,.2f} por veículo "
        f"(válido para limite entre {top.rhs_valido_de} e {top.rhs_valido_ate})."
    )

print("\n--- R2: regime dos duais de atendimento ---")
print(duais_r2["regime"].value_counts().to_string())
print(
    "\nArquivos gerados: 'analise_dual_frota.csv' e 'analise_dual_atendimento.csv'."
)
