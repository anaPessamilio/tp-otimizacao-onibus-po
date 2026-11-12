import pandas as pd

from config import (
    ALPHA_1,
    ALPHA_2,
    CAP_ARTICULADO,
    CAP_PADRON,
    CUSTO_KM_ARTICULADO,
    CUSTO_KM_MEDIO,
    CUSTO_KM_PADRON,
    D_L_RELATORIO,
    FROTA_MAX,
    LINHAS_CORREDOR,
    USAR_EXTENSAO_GTFS,
)
from modelo import resolver_modelo

# 1. Carrega a instância base tratada
df_base = pd.read_csv("instancia_modelo_bhtrans.csv")

# O read_csv lê as linhas como inteiros; os dicionários usam chaves texto.
df_base["route_short_name"] = df_base["route_short_name"].astype(str).str.strip()


# 2. Definição dos Cenários de Teste
def frota(articulados, custo_art=CUSTO_KM_ARTICULADO, custo_pad=CUSTO_KM_PADRON):
    """Monta capacidades e custo/km por linha: articulado nas linhas
    indicadas, padron nas demais."""
    capacidades = {
        l: CAP_ARTICULADO if l in articulados else CAP_PADRON
        for l in LINHAS_CORREDOR
    }
    custo_km = {
        l: custo_art if l in articulados else custo_pad
        for l in LINHAS_CORREDOR
    }
    return {"capacidades": capacidades, "custo_km": custo_km}


cenarios = {
    # Mesma configuração de otimizacao.py: 100% articulado com custo/km
    # médio (R$ 11,00). Serve de referência e validação cruzada.
    "Cenario_R_Relatorio": {
        "frota_max": FROTA_MAX,
        **frota(LINHAS_CORREDOR, CUSTO_KM_MEDIO, CUSTO_KM_MEDIO),
    },
    # Demais cenários: custo/km por tipologia (articulado x padron).
    "Cenario_0_Baseline": {
        "frota_max": FROTA_MAX,
        **frota(["51"]),
    },
    "Cenario_1_Frota_Mista_MOVE": {
        "frota_max": FROTA_MAX,
        **frota(["51", "52", "63"]),
    },
    "Cenario_2_100pct_Articulados": {
        "frota_max": FROTA_MAX,
        **frota(LINHAS_CORREDOR),
    },
    "Cenario_3_Expansao_Frota_110": {
        "frota_max": 110,
        **frota(["51"]),
    },
}

resultados_globais = []
detalhamento_linhas = []

# 3. Execução dos cenários (modelo em modelo.py)
for nome_cenario, cfg in cenarios.items():
    df_cenario = df_base.copy()

    df_cenario["capacidade_C"] = (
        df_cenario["route_short_name"].map(cfg["capacidades"]).astype(int)
    )
    custo_por_km = df_cenario["route_short_name"].map(cfg["custo_km"]).astype(float)
    # c_l = D_l (ida + volta) x Custo/km da tipologia
    D_l = df_cenario["extensao_km"] if USAR_EXTENSAO_GTFS else D_L_RELATORIO
    df_cenario["c_lt"] = (D_l * custo_por_km).round(2)

    res = resolver_modelo(
        df_cenario,
        frota_max=cfg["frota_max"],
        alpha_1=ALPHA_1,
        alpha_2=ALPHA_2,
        nome=nome_cenario,
    )

    if "detalhe" not in res:
        print(f"{nome_cenario}: sem solução ótima (status {res['status']})")
        continue

    resultados_globais.append(
        {
            "cenario": nome_cenario,
            "frota_max": cfg["frota_max"],
            "custo_operacional_R$": round(res["custo_operacional"], 2),
            "passageiros_represados": round(res["passageiros_represados"], 0),
            "pct_nao_atendida": round(
                100 * res["passageiros_represados"] / res["demanda_total"], 1
            ),
            "valor_obj_Z": round(res["valor_obj_Z"], 2),
        }
    )

    por_linha = res["detalhe"].groupby("linha").agg(
        viagens_totais=("frequencia_otima", "sum"),
        passageiros_represados=("passageiros_represados", "sum"),
        custo_linha=("custo_operacional_R$", "sum"),
    )
    for l, v in por_linha.iterrows():
        detalhamento_linhas.append(
            {
                "cenario": nome_cenario,
                "linha": l,
                "tipologia": (
                    "Articulado" if cfg["capacidades"][l] == CAP_ARTICULADO else "Padron"
                ),
                "viagens_totais": int(v["viagens_totais"]),
                "passageiros_represados": round(v["passageiros_represados"], 1),
                "custo_linha_R$": round(v["custo_linha"], 2),
            }
        )

# 4. Salva e Exibe as Tabelas de Resumo
df_resumo_cenarios = pd.DataFrame(resultados_globais)
df_detalhamento = pd.DataFrame(detalhamento_linhas)

df_resumo_cenarios.to_csv("comparativo_resumo_cenarios.csv", index=False)
df_detalhamento.to_csv("comparativo_detalhado_linhas.csv", index=False)

print("=== COMPARATIVO DE CENÁRIOS EXECUTADO COM SUCESSO ===")
print("\n--- RESUMO EXECUTIVO DOS CENÁRIOS: ---")
print(df_resumo_cenarios.to_string(index=False))
