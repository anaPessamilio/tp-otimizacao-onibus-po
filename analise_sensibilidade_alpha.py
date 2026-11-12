import pandas as pd

from config import ALPHA_1, FROTA_MAX
from modelo import faixas_frota_saturada, resolver_modelo

# ==========================================
# Análise de sensibilidade do peso α2 (penalidade por passageiro no ponto)
# Mostra o trade-off custo operacional x nível de serviço da F.O. bi-objetivo:
#   Min Z = α1 Σ c_l f_lt + α2 Σ w_lt
# Usa a mesma instância e os mesmos parâmetros de otimizacao.py, variando α2.
# ==========================================
df = pd.read_csv("instancia_modelo_bhtrans.csv")

valores_alpha_2 = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 5.0, 10.0, 25.0, 50.0]
resultados = []

for alpha_2 in valores_alpha_2:
    res = resolver_modelo(
        df,
        frota_max=FROTA_MAX,
        alpha_1=ALPHA_1,
        alpha_2=alpha_2,
        nome=f"Sensibilidade_alpha2_{alpha_2}",
    )

    if "detalhe" not in res:
        print(f"alpha_2 = {alpha_2}: sem solução ótima (status {res['status']})")
        continue

    resultados.append(
        {
            "alpha_2": alpha_2,
            "viagens_totais": int(res["detalhe"]["frequencia_otima"].sum()),
            "custo_operacional_R$": round(res["custo_operacional"], 2),
            "passageiros_represados": round(res["passageiros_represados"], 0),
            "pct_demanda_nao_atendida": round(
                100 * res["passageiros_represados"] / res["demanda_total"], 1
            ),
            "faixas_frota_saturada": faixas_frota_saturada(res, FROTA_MAX),
            "valor_obj_Z": round(res["valor_obj_Z"], 2),
        }
    )

df_res = pd.DataFrame(resultados)
df_res.to_csv("sensibilidade_alpha2.csv", index=False)

print(f"=== ANÁLISE DE SENSIBILIDADE DE α2 (α1 = {ALPHA_1} | Frota = {FROTA_MAX}) ===")
# Ponto de equilíbrio por linha: abaixo de α2 = c_l / C_l, sai mais barato
# deixar o passageiro no ponto do que realizar a viagem.
equilibrio = (
    df.groupby("route_short_name")
    .agg(c_l=("c_lt", "first"), C_l=("capacidade_C", "first"))
    .assign(alpha2_equilibrio=lambda x: (x.c_l / x.C_l).round(2))
)
print("Ponto de equilíbrio por linha (α2 = c_l / C_l, R$/passageiro):")
print(equilibrio.to_string())
print()
print(df_res.to_string(index=False))
print("\nArquivo 'sensibilidade_alpha2.csv' gerado com sucesso!")
