"""
Validação: solução ótima x grade atual programada (GTFS), sempre no MESMO
modo de tratamento dos não atendidos ("espera" e "perda"), com custo, nível de
serviço e Z dos dois lados. A grade atual é avaliada com as mesmas regras do
modelo (avaliar_grade).

Inclui, por linha:
- Σ_t ceil(d_lt / C): mínimo de viagens para atender cada faixa isoladamente
  (sem frota nem corredor), para separar o efeito da regra de demanda do efeito
  do acoplamento pela frota;
- λ em que a grade atual daquela linha satura (calibracao_lambda), que mostra
  quanto a diferença entre linhas decorre do rateio dos embarques.

Atenção: como a demanda é rateada pelas viagens programadas, cada viagem da
grade recebe o mesmo número de embarques; o déficit da grade por linha é, por
construção, (embarques por viagem - capacidade) x viagens. Essa parte da
comparação recupera a regra de demanda e não é uma validação independente.
"""

import math

import pandas as pd

import config
from cria_instancia_teste import calibracao_lambda, lambda_efetivo
from modelo import avaliar_grade, resolver_modelo

inst = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
CAP = config.TIPOS_VEICULO["articulado"]["capacidade"]

comparacao, por_linha_modos = [], {}
for modo in ["espera", "perda"]:
    grade = avaliar_grade(inst, nao_atendidos=modo)
    otimo = resolver_modelo(inst, nao_atendidos=modo, nome=f"otimo_{modo}")
    for nome, r, viagens in [("Grade atual (GTFS)", grade, grade["viagens"]),
                             ("Solução ótima", otimo, otimo["detalhe"]["frequencia_otima"].sum())]:
        comparacao.append({
            "modo": modo, "solucao": nome, "viagens": int(viagens),
            "custo_operacional_R$": round(r["custo_operacional"], 2),
            "nao_atendidos": round(r["passageiros_represados"], 0),
            "espera_media_min": None if r["espera_media_min"] is None else round(r["espera_media_min"], 2),
            "pct_perdidos": None if r["pct_perdidos"] is None else round(r["pct_perdidos"], 2),
            "valor_obj_Z": round(r["valor_obj_Z"], 2),
        })
    por_linha_modos[modo] = (grade["detalhe"], otimo["detalhe"])
comp = pd.DataFrame(comparacao)

# ---------------------------------------------------------------- por linha (modo perda: comparável e sem fila acumulada)
g_det, o_det = por_linha_modos["perda"]
lam_tot, lam_lin = calibracao_lambda()
inst["min_viagens"] = (inst["d_lt"] / CAP).apply(math.ceil)
por_linha = pd.DataFrame({
    "viagens_gtfs": g_det.groupby("linha")["frequencia"].sum(),
    "viagens_otimo": o_det.groupby("linha")["frequencia_otima"].sum(),
    "soma_ceil_d_C": inst.groupby("route_short_name")["min_viagens"].sum(),
    "embarques_por_viagem_gtfs": (inst.groupby("route_short_name")["d_lt"].sum()
                                  / inst.groupby("route_short_name")["viagens_gtfs"].sum()).round(1),
    "lambda_saturacao": lam_lin.round(3),
    "perdidos_gtfs": g_det.groupby("linha")["passageiros_represados"].sum().round(0),
    "perdidos_otimo": o_det.groupby("linha")["passageiros_represados"].sum().round(0),
    "custo_gtfs": g_det.groupby("linha")["custo_operacional_R$"].sum().round(2),
    "custo_otimo": o_det.groupby("linha")["custo_operacional_R$"].sum().round(2),
})
por_linha.index.name = "linha"
por_linha = por_linha.reset_index()
por_linha["variacao_viagens_pct"] = (100 * (por_linha.viagens_otimo / por_linha.viagens_gtfs - 1)).round(1)

# ---------------------------------------------------------------- por hora (modo do config)
otimo_cfg = pd.read_csv("resultados_otimizacao_bhtrans.csv", dtype={"linha": str})
grade_cfg = avaliar_grade(inst)
por_hora = pd.DataFrame({
    "partidas_gtfs": grade_cfg["partidas_por_hora"],
    "partidas_otimo": otimo_cfg.groupby("faixa_horaria")["frequencia_otima"].sum(),
    "frota_gtfs": grade_cfg["frota_por_faixa"].round(1),
    "frota_otimo": otimo_cfg.groupby("faixa_horaria")["veiculos_em_operacao"].sum().round(1),
    "demanda": otimo_cfg.groupby("faixa_horaria")["demanda"].sum(),
})
por_hora.index.name = "faixa_horaria"

comp.to_csv("validacao_comparacao.csv", index=False)
por_linha.to_csv("validacao_grade_linhas.csv", index=False)
por_hora.reset_index().to_csv("validacao_grade_horas.csv", index=False)

print(f"=== VALIDAÇÃO (λ = {lambda_efetivo():.3f}) ===")
print(comp.to_string(index=False))
print(f"\nλ calibrado (grade com ocupação média 100%): {lam_tot:.3f}")
print("\nPor linha (modo perda):")
print(por_linha.to_string(index=False))
