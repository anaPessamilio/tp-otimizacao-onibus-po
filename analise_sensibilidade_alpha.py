import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# ==========================================
# Análise de sensibilidade do peso α2 (penalidade por passageiro no ponto)
# Mostra o trade-off custo operacional x nível de serviço da F.O. bi-objetivo:
#   Min Z = α1 Σ c_l f_lt + α2 Σ w_lt
# Usa a mesma instância de otimizacao.py (parâmetros do relatório).
# ==========================================
df = pd.read_csv("instancia_modelo_bhtrans.csv")
df_indexed = df.set_index(["route_short_name", "faixa_horaria"])

c_l = df_indexed["c_lt"].to_dict()
n_lt = df_indexed["tempo_ciclo_horas"].to_dict()
C_l = df_indexed["capacidade_C"].to_dict()
d_lt = df_indexed["d_lt"].to_dict()
f_min = df_indexed["f_min"].to_dict()
f_max = df_indexed["f_max"].to_dict()

faixas = df["faixa_horaria"].unique().tolist()
pares_validos = list(c_l.keys())
demanda_total = sum(d_lt.values())

Frota_Max = 90
alpha_1 = 1.0
valores_alpha_2 = [0.5, 1.0, 2.0, 2.5, 3.0, 5.0, 10.0, 25.0, 50.0]

resultados = []

for alpha_2 in valores_alpha_2:
    model = gp.Model(f"Sensibilidade_alpha2_{alpha_2}")
    model.Params.OutputFlag = 0

    f = model.addVars(
        pares_validos,
        vtype=GRB.INTEGER,
        lb={p: f_min[p] for p in pares_validos},
        ub={p: f_max[p] for p in pares_validos},
        name="frequencia",
    )
    w = model.addVars(pares_validos, vtype=GRB.CONTINUOUS, lb=0.0, name="w")

    custo_operacional = gp.quicksum(c_l[p] * f[p] for p in pares_validos)
    deficit = gp.quicksum(w[p] for p in pares_validos)
    model.setObjective(alpha_1 * custo_operacional + alpha_2 * deficit, GRB.MINIMIZE)

    for t in faixas:
        linhas_t = [l for (l, ft) in pares_validos if ft == t]
        model.addConstr(
            gp.quicksum(n_lt[(l, t)] * f[l, t] for l in linhas_t) <= Frota_Max
        )
    for l, t in pares_validos:
        model.addConstr(f[l, t] * C_l[(l, t)] + w[l, t] >= d_lt[(l, t)])

    model.optimize()

    if model.Status != GRB.OPTIMAL:
        print(f"alpha_2 = {alpha_2}: sem solução ótima (status {model.Status})")
        continue

    viagens = sum(f[p].X for p in pares_validos)
    represados = deficit.getValue()
    # Faixa saturada: a frota restante não comporta nem mais uma viagem
    # da linha de menor tempo de ciclo naquela faixa.
    faixas_frota_saturada = 0
    for t in faixas:
        pares_t = [(l, ft) for (l, ft) in pares_validos if ft == t]
        uso = sum(n_lt[p] * f[p].X for p in pares_t)
        if Frota_Max - uso < min(n_lt[p] for p in pares_t) - 1e-6:
            faixas_frota_saturada += 1

    resultados.append(
        {
            "alpha_2": alpha_2,
            "viagens_totais": int(round(viagens)),
            "custo_operacional_R$": round(custo_operacional.getValue(), 2),
            "passageiros_represados": round(represados, 0),
            "pct_demanda_nao_atendida": round(100 * represados / demanda_total, 1),
            "faixas_frota_saturada": faixas_frota_saturada,
            "valor_obj_Z": round(model.ObjVal, 2),
        }
    )

df_res = pd.DataFrame(resultados)
df_res.to_csv("sensibilidade_alpha2.csv", index=False)

print("=== ANÁLISE DE SENSIBILIDADE DE α2 (α1 = 1,0 | Frota = 90) ===")
print(f"Custo por viagem c_l = R$ {df['c_lt'].iloc[0]:.2f} | "
      f"Capacidade C_l = {df['capacidade_C'].iloc[0]} pas")
print(f"Ponto de equilíbrio teórico: α2 = c_l / C_l = "
      f"R$ {df['c_lt'].iloc[0] / df['capacidade_C'].iloc[0]:.2f}/passageiro\n")
print(df_res.to_string(index=False))
print("\nArquivo 'sensibilidade_alpha2.csv' gerado com sucesso!")
