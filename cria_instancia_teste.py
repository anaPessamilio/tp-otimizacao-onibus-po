
import pandas as pd

# 1. Carrega os parâmetros extraídos do GTFS
df_gtfs = pd.read_csv("parametros_gtfs_extraidos.csv")

# O read_csv lê as linhas como inteiros (51); os dicionários abaixo usam
# chaves texto ("51"). Sem esta conversão, todo .map() cai no fillna.
df_gtfs["route_short_name"] = (
    df_gtfs["route_short_name"].astype(str).str.strip()
)

# 2. Parâmetros do relatório (Seção 3 - BHTRANS / SUMOB)
D_L = 34.0  # Extensão do itinerário ida + volta (km por viagem troncal)
CUSTO_KM = 11.00  # Custo quilométrico médio Padron/Articulado MOVE (R$/km)
CAPACIDADE_PADRAO = 130  # Veículo articulado padronizado (passageiros)

# c_l = D_l x Custo/km = R$ 374,00 por viagem (igual para todas as linhas).
# A extensão do GTFS (extensao_km) é mantida só como informação; o custo
# segue o relatório. O tempo de ciclo continua vindo do GTFS.
df_gtfs["c_lt"] = round(D_L * CUSTO_KM, 2)

# C_l: capacidade padronizada de 130 passageiros em todas as linhas.
df_gtfs["capacidade_C"] = CAPACIDADE_PADRAO

# 3. Modelagem de Demanda Tipificada (Perfil Diário de Pico Antônio Carlos)

# Fatores multiplicadores de demanda por faixa horaria (0h as 23h)
fatores_demanda = {
    0: 0.05,
    1: 0.02,
    2: 0.01,
    3: 0.02,
    4: 0.15,
    5: 0.50,
    6: 1.00,  # Pico Manhã (100% da demanda máxima)
    7: 0.95,
    8: 0.70,
    9: 0.45,
    10: 0.40,
    11: 0.45,
    12: 0.50,
    13: 0.45,
    14: 0.45,
    15: 0.55,
    16: 0.75,
    17: 0.95,  # Pico Tarde
    18: 0.90,
    19: 0.60,
    20: 0.40,
    21: 0.30,
    22: 0.20,
    23: 0.10,
}

# Demanda base de pico por linha (passageiros/hora estimados)
demanda_pico_linha = {
    "51": 3200,  # Linha de maior volume do corredor
    "52": 1800,
    "63": 1400,
    "64": 1200,
    "67": 1100,
}

# Injeta a demanda d_lt no dataframe
# GTFS permite horários após 24:00 (ex.: 25:10 = 01:10 do dia seguinte),
# então usa-se a hora do relógio (módulo 24) para buscar o fator.
df_gtfs["fator_pico"] = (
    (df_gtfs["faixa_horaria"] % 24).map(fatores_demanda).fillna(0.1)
)
df_gtfs["demanda_pico_base"] = (
    df_gtfs["route_short_name"].map(demanda_pico_linha).fillna(1000)
)

# d_lt = Demanda em passageiros na faixa horária
df_gtfs["d_lt"] = (
    df_gtfs["demanda_pico_base"] * df_gtfs["fator_pico"]
).astype(int)

# 4. Parâmetros Contratuais de Frequência (f_min e f_max)
df_gtfs["f_min"] = 1  # Mínimo de 1 viagem/hora
df_gtfs["f_max"] = 24  # Máximo de 24 viagens/hora (intervalo de 2.5 min)

# 5. Limpar e exportar a instância consolidada
colunas_instancia = [
    "route_short_name",
    "faixa_horaria",
    "extensao_km",
    "tempo_ciclo_horas",
    "capacidade_C",
    "c_lt",
    "d_lt",
    "f_min",
    "f_max",
]

instancia_final = df_gtfs[colunas_instancia].sort_values(
    ["route_short_name", "faixa_horaria"]
)

instancia_final.to_csv("instancia_modelo_bhtrans.csv", index=False)

print("=== INSTÂNCIA CONSOLIDADA DO MODELO COM SUCESSO ===")
print(instancia_final.head(15).to_string(index=False))
print("\nArquivo 'instancia_modelo_bhtrans.csv' gerado!")