"""
Cenários de disponibilidade de frota e de infraestrutura, em dois níveis de
demanda (λ calibrado e λ = 1). Em todos o modelo DECIDE quantas viagens de
cada tipo de veículo cada linha faz em cada faixa; o cenário só muda o que
está disponível.

Para os cenários com Padron, o custo operacional NÃO inclui aquisição nem
tripulação dos veículos extras. Por isso calcula-se o custo diário de
equilíbrio por Padron: o maior custo fixo diário por veículo que ainda faria o
cenário valer a pena em Z. E testa-se a sensibilidade ao custo/km do Padron.
"""

import copy

import pandas as pd

import config
from cria_instancia_teste import lambda_efetivo, montar_instancia
from modelo import capacidade_corredor, frota_grade_atual, resolver_modelo

LAMBDAS = [lambda_efetivo(), 1.0]


def tipos(art, pad, custo_pad=None):
    t = copy.deepcopy(config.TIPOS_VEICULO)
    t["articulado"]["frota"] = art
    t["padron"]["frota"] = pad
    if custo_pad is not None:
        t["padron"]["custo_km"] = custo_pad
    return t


def relaxar_padrao(df):
    d = df.copy()
    d["f_min"] = (d["f_min"] > 0).astype(int)
    return d


resumo, detalhe = [], []
for lam in LAMBDAS:
    df_base = montar_instancia(lambda_demanda=lam)
    F0 = frota_grade_atual(df_base)
    CAP0 = capacidade_corredor(df_base)
    cp = config.TIPOS_VEICULO["padron"]["custo_km"]
    cenarios = [
        (f"Base: {F0} articulados", df_base, tipos(F0, 0), "config"),
        ("90 articulados (proposta inicial)", df_base, tipos(90, 0), "config"),
        (f"+10 articulados ({F0 + 10})", df_base, tipos(F0 + 10, 0), "config"),
        (f"+15 Padron (R$ {cp:.2f}/km)".replace(".", ","), df_base, tipos(F0, 15), "config"),
        ("+15 Padron (R$ 11,00/km)", df_base, tipos(F0, 15, 11.00), "config"),
        ("+15 Padron (R$ 12,50/km)", df_base, tipos(F0, 15, 12.50), "config"),
        (f"Troca: {F0 - 20} art. + 30 Padron", df_base, tipos(F0 - 20, 30), "config"),
        (f"Corredor +20% ({round(CAP0 * 1.2)}/h)", df_base, tipos(F0, 0), round(CAP0 * 1.2)),
        ("Padrão de serviço relaxado", relaxar_padrao(df_base), tipos(F0, 0), "config"),
    ]
    z_base = None
    for nome, df, tp, cap in cenarios:
        res = resolver_modelo(df, tipos=tp, cap_corredor=cap, nome=nome[:40])
        if "detalhe" not in res:
            print(f"[λ={lam}] {nome}: sem solução ótima (status {res['status']})")
            continue
        det = res["detalhe"]
        z_base = res["valor_obj_Z"] if z_base is None else z_base
        pad_max = res["frota_por_tipo"]["padron"].max() if "padron" in res["frota_por_tipo"] else 0
        # custo de equilíbrio só faz sentido quando a frota é apenas acrescida
        so_acrescimo = tp["articulado"]["frota"] >= F0
        extra = (tp["articulado"]["frota"] - F0 + tp["padron"]["frota"]) if so_acrescimo else 0
        resumo.append({
            "lambda": round(lam, 3),
            "cenario": nome,
            "frota_articulado": tp["articulado"]["frota"],
            "frota_padron": tp["padron"]["frota"],
            "cap_corredor": res["cap_corredor"],
            "viagens": int(det["frequencia_otima"].sum()),
            "viagens_padron": int(det["f_padron"].sum()),
            "padron_em_operacao_max": round(pad_max, 1),
            "custo_operacional_R$": round(res["custo_operacional"], 2),
            "passageiros_represados": round(res["passageiros_represados"], 0),
            "espera_media_min": round(res["espera_media_min"], 2),
            "valor_obj_Z": round(res["valor_obj_Z"], 2),
            "reducao_Z_vs_base": round(z_base - res["valor_obj_Z"], 2),
            # maior custo fixo diário por veículo extra que ainda compensa em Z
            "equilibrio_R$_por_veiculo_dia": round((z_base - res["valor_obj_Z"]) / extra, 2) if extra else None,
            "menor_freq_pico": int(det[det["faixa_horaria"].isin(config.HORAS_PICO)]["frequencia_otima"].min()),
            "gap_pct": round(100 * res["gap"], 3),
            "otimo_provado": res["otimo_provado"],
        })
        g = det.groupby("linha").agg(viagens=("frequencia_otima", "sum"),
                                     viagens_padron=("f_padron", "sum"),
                                     espera=("passageiros_represados", "sum"),
                                     custo=("custo_operacional_R$", "sum"))
        for l, r in g.iterrows():
            detalhe.append({"lambda": round(lam, 3), "cenario": nome, "linha": l, **r.round(1).to_dict()})

df_resumo = pd.DataFrame(resumo)
df_resumo.to_csv("comparativo_resumo_cenarios.csv", index=False)
pd.DataFrame(detalhe).to_csv("comparativo_detalhado_linhas.csv", index=False)

print("=== CENÁRIOS (o modelo escolhe o tipo de veículo) ===")
print(df_resumo.drop(columns=["valor_obj_Z", "cap_corredor"]).to_string(index=False))
