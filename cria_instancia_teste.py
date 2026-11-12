import sys

import pandas as pd

from config import (
    CAP_ARTICULADO,
    CUSTO_KM_MEDIO,
    D_L_RELATORIO,
    DEMANDA_PICO_LINHA,
    F_MAX,
    F_MIN,
    FATORES_DEMANDA,
    LINHAS_CORREDOR,
    OPERAR_FORA_DO_HORARIO_GTFS,
    USAR_EXTENSAO_GTFS,
)

# 1. Carrega os parâmetros extraídos do GTFS
df_gtfs = pd.read_csv("parametros_gtfs_extraidos.csv")

# O read_csv lê as linhas como inteiros (51); os dicionários do config usam
# chaves texto ("51"). Sem esta conversão, nenhum .map() encontra a linha.
df_gtfs["route_short_name"] = df_gtfs["route_short_name"].astype(str).str.strip()

# Validação: toda linha do corredor precisa ter dados no GTFS e demanda.
sem_gtfs = sorted(set(LINHAS_CORREDOR) - set(df_gtfs["route_short_name"]))
sem_demanda = sorted(set(LINHAS_CORREDOR) - set(DEMANDA_PICO_LINHA))
faixas_sem_fator = sorted(set(range(24)) - set(FATORES_DEMANDA))
if sem_gtfs or sem_demanda or faixas_sem_fator:
    print("ERRO na montagem da instância:")
    if sem_gtfs:
        print(f"  Linhas sem dados no GTFS: {sem_gtfs}")
    if sem_demanda:
        print(f"  Linhas sem DEMANDA_PICO_LINHA no config.py: {sem_demanda}")
    if faixas_sem_fator:
        print(f"  Horas sem FATORES_DEMANDA no config.py: {faixas_sem_fator}")
    sys.exit(1)

# 2. Grade completa: todas as linhas x 24 faixas horárias.
# Faixas sem viagem no GTFS não são descartadas (a demanda delas existe);
# o tratamento depende de OPERAR_FORA_DO_HORARIO_GTFS (ver config.py).
grade = pd.MultiIndex.from_product(
    [LINHAS_CORREDOR, range(24)], names=["route_short_name", "faixa_horaria"]
).to_frame(index=False)

df = grade.merge(df_gtfs, on=["route_short_name", "faixa_horaria"], how="left")
df["opera_no_gtfs"] = df["tempo_ciclo_horas"].notna().astype(int)

# Faixas sem viagem no GTFS recebem a extensão e o ciclo médios da linha,
# ponderados pelo número de viagens de cada faixa.
def media_ponderada(g, coluna):
    return (g[coluna] * g["viagens_gtfs"]).sum() / g["viagens_gtfs"].sum()


por_linha = pd.DataFrame(
    {
        "extensao_linha": df_gtfs.groupby("route_short_name").apply(
            media_ponderada, "extensao_km", include_groups=False
        ),
        "ciclo_medio": df_gtfs.groupby("route_short_name").apply(
            media_ponderada, "tempo_ciclo_horas", include_groups=False
        ),
    }
).reset_index()
df = df.merge(por_linha, on="route_short_name", how="left")
df["extensao_km"] = df["extensao_km"].fillna(df["extensao_linha"].round(3))
df["tempo_ciclo_horas"] = df["tempo_ciclo_horas"].fillna(df["ciclo_medio"].round(2))

# 3. Custo por viagem e capacidade (parâmetros em config.py)
# c_l = D_l x Custo/km. D_l é a extensão ida + volta da variante principal
# de cada linha (GTFS) ou o valor único do relatório, conforme config.
if USAR_EXTENSAO_GTFS:
    df["c_lt"] = (df["extensao_km"] * CUSTO_KM_MEDIO).round(2)
else:
    df["c_lt"] = round(D_L_RELATORIO * CUSTO_KM_MEDIO, 2)

# C_l: veículo articulado padronizado em todas as linhas (relatório).
df["capacidade_C"] = CAP_ARTICULADO

# 4. Demanda d_lt (HIPÓTESE definida em config.py, não extraída de dados)
df["d_lt"] = (
    df["route_short_name"].map(DEMANDA_PICO_LINHA)
    * df["faixa_horaria"].map(FATORES_DEMANDA)
).astype(int)

# 5. Limites de frequência
# Faixas com viagem no GTFS: mínimo contratual F_MIN.
# Faixas sem viagem: o modelo pode criar serviço (f_min = 0) ou não (f = 0).
df["f_min"] = F_MIN * df["opera_no_gtfs"]
df["f_max"] = F_MAX if OPERAR_FORA_DO_HORARIO_GTFS else F_MAX * df["opera_no_gtfs"]

# 6. Exporta a instância consolidada
colunas_instancia = [
    "route_short_name",
    "faixa_horaria",
    "opera_no_gtfs",
    "extensao_km",
    "tempo_ciclo_horas",
    "capacidade_C",
    "c_lt",
    "d_lt",
    "f_min",
    "f_max",
]

instancia_final = df[colunas_instancia].sort_values(["route_short_name", "faixa_horaria"])
instancia_final.to_csv("instancia_modelo_bhtrans.csv", index=False)

fora = instancia_final[instancia_final["opera_no_gtfs"] == 0]
print("=== INSTÂNCIA CONSOLIDADA DO MODELO COM SUCESSO ===")
print(instancia_final.head(15).to_string(index=False))
print(
    f"\n{len(fora)} pares (linha, faixa) sem viagem no GTFS, com "
    f"{fora['d_lt'].sum()} passageiros de demanda "
    f"({'modelo pode operar' if OPERAR_FORA_DO_HORARIO_GTFS else 'f = 0, demanda não atendida'})."
)
print("\nArquivo 'instancia_modelo_bhtrans.csv' gerado!")
