"""
Validação: compara a solução ótima com a grade atual programada (GTFS), por
linha e por faixa horária, na instância do config. A grade atual é avaliada
com as mesmas regras do modelo (avaliar_grade): custo, passageiros não
atendidos (modos "espera" e "perda"), frota em operação e partidas/h.
"""

import pandas as pd

from modelo import avaliar_grade, capacidade_corredor, frota_grade_atual

inst = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
otimo = pd.read_csv("resultados_otimizacao_bhtrans.csv", dtype={"linha": str})

grade_espera = avaliar_grade(inst, nao_atendidos="espera")
grade_perda = avaliar_grade(inst, nao_atendidos="perda")

# ---------------------------------------------------------------- por linha
g_esp = grade_espera["detalhe"].groupby("linha")
g_per = grade_perda["detalhe"].groupby("linha")
o = otimo.groupby("linha")
por_linha = pd.DataFrame({
    "viagens_gtfs": g_esp["frequencia"].sum(),
    "viagens_otimo": o["frequencia_otima"].sum(),
    "custo_gtfs": g_esp["custo_operacional_R$"].sum().round(2),
    "custo_otimo": o["custo_operacional_R$"].sum().round(2),
    "nao_atendidos_gtfs_espera": g_esp["passageiros_represados"].sum().round(0),
    "nao_atendidos_gtfs_perda": g_per["passageiros_represados"].sum().round(0),
    "nao_atendidos_otimo": o["passageiros_represados"].sum().round(0),
    "demanda": o["demanda"].sum(),
}).reset_index().rename(columns={"index": "linha"})
por_linha["variacao_viagens_pct"] = (
    100 * (por_linha["viagens_otimo"] / por_linha["viagens_gtfs"] - 1)).round(1)

# ---------------------------------------------------------------- por hora
frota_otimo = otimo.groupby("faixa_horaria")["veiculos_em_operacao"].sum()
por_hora = pd.DataFrame({
    "partidas_gtfs": grade_espera["partidas_por_hora"],
    "partidas_otimo": otimo.groupby("faixa_horaria")["frequencia_otima"].sum(),
    "frota_gtfs": grade_espera["frota_por_faixa"].round(1),
    "frota_otimo": frota_otimo.round(1),
    "demanda": otimo.groupby("faixa_horaria")["demanda"].sum(),
}).reset_index().rename(columns={"index": "faixa_horaria"})

por_linha.to_csv("validacao_grade_linhas.csv", index=False)
por_hora.to_csv("validacao_grade_horas.csv", index=False)

print("=== VALIDAÇÃO: ÓTIMO x GRADE ATUAL (GTFS) ===")
print(f"Frota exigida pela grade atual: {frota_grade_atual(inst)} | "
      f"pico de partidas/h: {capacidade_corredor(inst, 'grade_atual')}")
print(por_linha.to_string(index=False))
tot = por_linha.sum(numeric_only=True)
print(f"\nTotal: {tot.viagens_gtfs:.0f} viagens (GTFS) -> {tot.viagens_otimo:.0f} (ótimo), "
      f"{100 * (tot.viagens_otimo / tot.viagens_gtfs - 1):+.1f}%")
print(f"Custo: R$ {tot.custo_gtfs:,.2f} (GTFS) -> R$ {tot.custo_otimo:,.2f} (ótimo)")
print(f"Não atendidos GTFS: {tot.nao_atendidos_gtfs_espera:,.0f} (espera) / "
      f"{tot.nao_atendidos_gtfs_perda:,.0f} (perda); ótimo: {tot.nao_atendidos_otimo:,.0f}")
print("\nPor hora:")
print(por_hora.to_string(index=False))
