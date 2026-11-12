"""
Resolve a instância principal (config.py) e exporta os resultados.
O log do Gurobi desta execução é salvo em log_gurobi.txt (status, nós,
cortes, gap); o arquivo é recriado a cada execução.
"""

from pathlib import Path

import pandas as pd

import config
from cria_instancia_teste import lambda_efetivo
from modelo import faixas_frota_saturada, resolver_modelo

df_instancia = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})

Path("log_gurobi.txt").unlink(missing_ok=True)  # o Gurobi acrescenta ao arquivo
res = resolver_modelo(df_instancia, nome="Otimizacao_Frequencia_MOVE", log=True,
                      arquivo_log="log_gurobi.txt")

if "detalhe" not in res:
    raise SystemExit(f"O modelo não encontrou solução ótima. Status: {res['status']}")

print("\n" + "=" * 60)
print(f"SOLUÇÃO ÓTIMA (λ = {lambda_efetivo():.3f}, modo {config.NAO_ATENDIDOS})")
print("=" * 60)
print(f"Z = R$ {res['valor_obj_Z']:,.2f}   (limitante inferior R$ {res['limitante']:,.2f}, "
      f"gap {100 * res['gap']:.4f}%, {res['nos']:.0f} nó(s), {res['tempo_s']:.2f} s)")
print(f"  Custo operacional: R$ {res['custo_operacional']:,.2f}")
if res["espera_media_min"] is not None:
    print(f"  Espera excedente: {res['passageiros_represados']:,.0f} passageiro-hora "
          f"= {res['espera_media_min']:.2f} min por passageiro (demanda {res['demanda_total']:,})")
else:
    print(f"  Passageiros perdidos: {res['passageiros_represados']:,.0f} "
          f"({res['pct_perdidos']:.2f}% da demanda {res['demanda_total']:,})")
for k, t in res["tipos"].items():
    if t["frota"] > 0:
        print(f"  Frota {k}: limite {t['frota']}, máximo usado {res['frota_por_tipo'][k].max():.1f}")
print(f"  Corredor: {res['cap_corredor']} partidas/h (máximo usado "
      f"{res['detalhe'].groupby('faixa_horaria')['frequencia_otima'].sum().max()})")
print(f"  Faixas com frota no limite: {faixas_frota_saturada(res)}")

df_resultados = res["detalhe"]
df_resultados.to_csv("resultados_otimizacao_bhtrans.csv", index=False)

print("\n--- RESUMO POR LINHA (VALORES DIÁRIOS) ---")
resumo = df_resultados.groupby("linha").agg(
    viagens_otimas=("frequencia_otima", "sum"), viagens_gtfs=("viagens_gtfs", "sum"),
    demanda=("demanda", "sum"), capacidade_ofertada=("capacidade_ofertada", "sum"),
    espera=("passageiros_represados", "sum"), custo=("custo_operacional_R$", "sum"),
).reset_index()
print(resumo.to_string(index=False))
print("\nArquivos: 'resultados_otimizacao_bhtrans.csv' e 'log_gurobi.txt'.")
