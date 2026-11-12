"""
Cenários de disponibilidade de frota e de infraestrutura. Em todos eles o
modelo DECIDE quantas viagens de cada tipo de veículo (articulado / Padron)
cada linha faz em cada faixa; o cenário só muda o que está disponível.
"""

import copy

import pandas as pd

import config
from modelo import capacidade_corredor, frota_grade_atual, resolver_modelo

df_base = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
F0 = frota_grade_atual(df_base)
CAP0 = capacidade_corredor(df_base)


def tipos(art, pad):
    t = copy.deepcopy(config.TIPOS_VEICULO)
    t["articulado"]["frota"] = art
    t["padron"]["frota"] = pad
    return t


def relaxar_padrao(df):
    d = df.copy()
    d["f_min"] = (d["f_min"] > 0).astype(int)  # só 1 viagem/h onde opera
    return d


cenarios = [
    # nome, instância, tipos, capacidade do corredor
    (f"Base: {F0} articulados (grade atual)", df_base, tipos(F0, 0), "config"),
    ("Frota de 90 articulados (proposta inicial)", df_base, tipos(90, 0), "config"),
    (f"+10 articulados ({F0 + 10})", df_base, tipos(F0 + 10, 0), "config"),
    (f"+15 Padron ({F0} art. + 15 Padron)", df_base, tipos(F0, 15), "config"),
    (f"Troca de 20 art. por 30 Padron ({F0 - 20} + 30)", df_base, tipos(F0 - 20, 30), "config"),
    (f"Corredor +20% ({round(CAP0 * 1.2)} partidas/h)", df_base, tipos(F0, 0), round(CAP0 * 1.2)),
    ("Padrão de serviço relaxado (f_min = 1)", relaxar_padrao(df_base), tipos(F0, 0), "config"),
]

resumo, detalhe = [], []
for nome, df, tp, cap in cenarios:
    res = resolver_modelo(df, tipos=tp, cap_corredor=cap, nome=nome[:40])
    if "detalhe" not in res:
        print(f"{nome}: sem solução ótima (status {res['status']})")
        continue
    det = res["detalhe"]
    resumo.append({
        "cenario": nome,
        "frota_articulado": tp["articulado"]["frota"],
        "frota_padron": tp["padron"]["frota"],
        "cap_corredor": res["cap_corredor"],
        "viagens": int(det["frequencia_otima"].sum()),
        "viagens_padron": int(det["f_padron"].sum()),
        "custo_operacional_R$": round(res["custo_operacional"], 2),
        "passageiros_represados": round(res["passageiros_represados"], 0),
        "pct_nao_atendida": round(100 * res["passageiros_represados"] / res["demanda_total"], 2),
        "valor_obj_Z": round(res["valor_obj_Z"], 2),
        "menor_freq_pico": int(det[det["faixa_horaria"].isin(config.HORAS_PICO)]["frequencia_otima"].min()),
    })
    g = det.groupby("linha").agg(
        viagens=("frequencia_otima", "sum"), viagens_padron=("f_padron", "sum"),
        passageiros_represados=("passageiros_represados", "sum"),
        custo=("custo_operacional_R$", "sum"))
    for l, r in g.iterrows():
        detalhe.append({"cenario": nome, "linha": l, **r.round(1).to_dict()})

df_resumo = pd.DataFrame(resumo)
df_resumo.to_csv("comparativo_resumo_cenarios.csv", index=False)
pd.DataFrame(detalhe).to_csv("comparativo_detalhado_linhas.csv", index=False)

print("=== CENÁRIOS (o modelo escolhe o tipo de veículo) ===")
print(df_resumo.drop(columns=["valor_obj_Z"]).to_string(index=False))
