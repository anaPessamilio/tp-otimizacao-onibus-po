"""
Sensibilidade do peso α2 (penalidade por passageiro-hora não atendido),
mantidos α1 e os demais parâmetros do config. Cada ponto é uma solução da
soma ponderada; a fronteira completa está em analise_pareto.py.
"""

import pandas as pd

import config
from modelo import faixas_frota_saturada, resolver_modelo

df = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
valores_alpha_2 = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 5.0, 10.0, 25.0, 50.0]

resultados = []
for a2 in valores_alpha_2:
    res = resolver_modelo(df, alpha_2=a2, nome=f"alpha2_{a2}")
    if "detalhe" not in res:
        print(f"α2 = {a2}: sem solução ótima (status {res['status']})")
        continue
    resultados.append({
        "alpha_2": a2,
        "viagens_totais": int(res["detalhe"]["frequencia_otima"].sum()),
        "custo_operacional_R$": round(res["custo_operacional"], 2),
        "passageiros_represados": round(res["passageiros_represados"], 0),
        "pct_demanda_nao_atendida": round(100 * res["passageiros_represados"] / res["demanda_total"], 2),
        "faixas_frota_saturada": faixas_frota_saturada(res),
        "valor_obj_Z": round(res["valor_obj_Z"], 2),
    })

df_res = pd.DataFrame(resultados)
df_res.to_csv("sensibilidade_alpha2.csv", index=False)

# Ponto de equilíbrio: abaixo de α2 = c/C, deixar o passageiro esperar custa
# menos que uma viagem a mais (por tipo de veículo).
eq = []
for k, t in config.TIPOS_VEICULO.items():
    custo = df["extensao_km"] * t["custo_km"] / t["capacidade"]
    eq.append(f"{k}: R$ {custo.min():.2f} a R$ {custo.max():.2f}")
print(f"=== SENSIBILIDADE DE α2 (α1 = {config.ALPHA_1}) ===")
print("Ponto de equilíbrio c/C por passageiro:", "; ".join(eq))
print(df_res.to_string(index=False))
print("\nArquivo 'sensibilidade_alpha2.csv' gerado.")
