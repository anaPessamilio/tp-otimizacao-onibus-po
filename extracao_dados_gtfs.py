import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString

from config import LINHAS_CORREDOR, MARGEM_TERMINAL, VARIANTES_EXCLUIDAS


# 1. Download e Extração Automática do GTFS
gtfs_folder = Path("./gtfs_bhtrans")
gtfs_folder.mkdir(parents=True, exist_ok=True)

# URL alternativa do GTFS da BHTRANS
url_gtfs = (
    "https://s3.amazonaws.com/mobilibus-uploads/"
    "gtfs/GTFSBHTRANS.zip"
)

arquivos_obrigatorios = [
    "routes.txt",
    "trips.txt",
    "shapes.txt",
    "stop_times.txt",
    "calendar.txt",
]

print("Verificando arquivos do GTFS...")

faltantes = [
    arquivo
    for arquivo in arquivos_obrigatorios
    if not (gtfs_folder / arquivo).exists()
]

if faltantes:
    print("Baixando dados do GTFS da BHTRANS...")

    try:
        response = requests.get(url_gtfs, timeout=120)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as arquivo_zip:
            # Verifica se o ZIP contém os arquivos necessários.
            nomes_zip = [
                nome
                for nome in arquivo_zip.namelist()
                if not nome.endswith("/")
            ]

            nomes_por_base = {
                Path(nome).name: nome
                for nome in nomes_zip
            }

            faltantes_zip = [
                arquivo
                for arquivo in arquivos_obrigatorios
                if arquivo not in nomes_por_base
            ]

            if faltantes_zip:
                raise RuntimeError(
                    f"Arquivos ausentes no ZIP: {faltantes_zip}"
                )

            # Extrai apenas os arquivos necessários.
            for arquivo in arquivos_obrigatorios:
                nome_interno = nomes_por_base[arquivo]
                destino = gtfs_folder / arquivo

                with arquivo_zip.open(nome_interno) as origem:
                    destino.write_bytes(origem.read())

        print("Download e extração concluídos com sucesso!")

    except Exception as e:
        print(f"Erro ao obter o GTFS: {e}")
        print(
            "Verifique a conexão ou baixe o GTFS manualmente."
        )
        sys.exit(1)

else:
    print("Arquivos do GTFS já encontrados na pasta local!")

# Validação final antes de continuar.
faltantes = [
    arquivo
    for arquivo in arquivos_obrigatorios
    if not (gtfs_folder / arquivo).exists()
]

if faltantes:
    print(f"Arquivos não encontrados: {faltantes}")
    sys.exit(1)


# 2. Carregamento das tabelas do GTFS
print("\nCarregando tabelas do GTFS...")

routes = pd.read_csv(
    gtfs_folder / "routes.txt",
    dtype={"route_id": str, "route_short_name": str},
)

trips = pd.read_csv(
    gtfs_folder / "trips.txt",
    dtype={"route_id": str, "trip_id": str, "shape_id": str},
)

shapes = pd.read_csv(
    gtfs_folder / "shapes.txt",
    dtype={"shape_id": str},
)

stop_times = pd.read_csv(
    gtfs_folder / "stop_times.txt",
    dtype={"trip_id": str},
)

# Normalização dos identificadores e nomes.
routes["route_short_name"] = (
    routes["route_short_name"].astype(str).str.strip()
)

routes["route_id"] = routes["route_id"].astype(str)
trips["route_id"] = trips["route_id"].astype(str)
trips["trip_id"] = trips["trip_id"].astype(str)
trips["shape_id"] = trips["shape_id"].astype(str)
stop_times["trip_id"] = stop_times["trip_id"].astype(str)
shapes["shape_id"] = shapes["shape_id"].astype(str)


# 3. Filtragem do corredor Av. Antônio Carlos
# Principais linhas troncais consideradas no modelo.
linhas_corredor = LINHAS_CORREDOR

routes_filtradas = routes[
    routes["route_short_name"].isin(linhas_corredor)
].copy()

if routes_filtradas.empty:
    print(
        "Nenhuma das linhas informadas foi encontrada no GTFS."
    )
    print(
        "Verifique os nomes disponíveis em routes.txt "
        "e confirme se o feed corresponde à versão desejada."
    )
    print(
        "Alguns nomes encontrados:",
        routes["route_short_name"].dropna().unique()[:30],
    )
    sys.exit(1)

route_ids = routes_filtradas["route_id"].unique()

print(
    f"\nLinhas encontradas: "
    f"{routes_filtradas['route_short_name'].unique().tolist()}"
)
print(f"Quantidade de route_id identificados: {len(route_ids)}")

# Serviços de dia útil (segunda a sexta, sem sábado/domingo).
# Exclui fins de semana e as tabelas especiais de Carnaval.
calendar = pd.read_csv(gtfs_folder / "calendar.txt", dtype={"service_id": str})
dias_uteis = ["monday", "tuesday", "wednesday", "thursday", "friday"]
servicos_dia_util = calendar.loc[
    (calendar[dias_uteis].sum(axis=1) == 5)
    & (calendar["saturday"] == 0)
    & (calendar["sunday"] == 0),
    "service_id",
].tolist()
print(f"Serviços de dia útil considerados: {servicos_dia_util}")

# Viagens de dia útil associadas às linhas selecionadas.
trips_filtradas = trips[
    trips["route_id"].isin(route_ids)
    & trips["service_id"].astype(str).isin(servicos_dia_util)
].copy()

if trips_filtradas.empty:
    print("Nenhuma viagem de dia útil encontrada para as linhas selecionadas.")
    sys.exit(1)

# Variantes de itinerário: todas as variantes regulares de dia útil entram
# (Direta Manhã/Tarde, retornos na Av. Dom Pedro II, Madrugão etc.), pois
# fazem parte da operação real. Carnaval já foi excluído pelo calendário.
# Variantes listadas em VARIANTES_EXCLUIDAS (config.py) são removidas.
if VARIANTES_EXCLUIDAS:
    padrao = "|".join(VARIANTES_EXCLUIDAS)
    excluir = trips_filtradas["trip_headsign"].str.contains(
        padrao, case=False, na=False
    )
    print(f"Viagens removidas por VARIANTES_EXCLUIDAS: {int(excluir.sum())}")
    trips_filtradas = trips_filtradas[~excluir].copy()

trips_filtradas = trips_filtradas.merge(
    routes_filtradas[["route_id", "route_short_name"]], on="route_id"
)
print("\nViagens de dia útil por linha e variante:")
print(
    trips_filtradas.groupby(["route_short_name", "trip_headsign"])
    .size()
    .to_string()
)


# 4. Cálculo da Extensão das Viagens (D_l, ida + volta)
print("\nCalculando extensão geométrica das linhas (km)...")

# Ordenação dos pontos de cada geometria.
shapes_sorted = shapes.sort_values(
    by=["shape_id", "shape_pt_sequence"]
).copy()

# Conversão de latitude/longitude para coordenadas métricas.
gdf_shapes = gpd.GeoDataFrame(
    shapes_sorted,
    geometry=gpd.points_from_xy(
        shapes_sorted["shape_pt_lon"],
        shapes_sorted["shape_pt_lat"],
    ),
    crs="EPSG:4326",
).to_crs("EPSG:31983")

# Criação das geometrias lineares por shape_id.
lines_by_shape = (
    gdf_shapes.groupby("shape_id")["geometry"]
    .apply(
        lambda pontos: (
            LineString(pontos.tolist())
            if len(pontos) > 1
            else None
        )
    )
    .dropna()
)

df_shapes_len = gpd.GeoDataFrame(
    {"shape_id": lines_by_shape.index},
    geometry=lines_by_shape.to_numpy(),
    crs="EPSG:31983",
)

df_shapes_len["extensao_km"] = (
    df_shapes_len.geometry.length / 1000.0
)

# Associa a extensão do trajeto a cada viagem.
trips_com_extensao = trips_filtradas.merge(
    df_shapes_len[["shape_id", "extensao_km"]],
    on="shape_id",
    how="inner",
)

if trips_com_extensao.empty:
    print(
        "Nenhuma viagem pôde ser associada a uma geometria. "
        "Verifique os shape_id em trips.txt e shapes.txt."
    )
    sys.exit(1)

# A extensão fica por viagem; a média por (linha, faixa) é feita no passo 5,
# ponderada pelo número de viagens de cada variante naquela faixa.


# 5. Cálculo do Tempo de Ciclo (n_lt)
print("\nCalculando tempos de ciclo...")

# Associação dos horários às viagens selecionadas.
st_trips = stop_times.merge(
    trips_filtradas[["trip_id", "route_id", "direction_id"]],
    on="trip_id",
    how="inner",
)


def hora_para_minutos(hora_str):
    """
    Converte horários GTFS para minutos.
    Aceita horários superiores a 24:00:00.
    """
    try:
        partes = str(hora_str).split(":")

        if len(partes) != 3:
            return np.nan

        h, m, s = int(partes[0]), int(partes[1]), float(partes[2])

        if m < 0 or m >= 60 or s < 0 or s >= 60 or h < 0:
            return np.nan

        return h * 60 + m + s / 60.0

    except (ValueError, TypeError):
        return np.nan


st_trips["arr_min"] = st_trips["arrival_time"].apply(
    hora_para_minutos
)

st_trips["dep_min"] = st_trips["departure_time"].apply(
    hora_para_minutos
)

# Descarta registros sem horários válidos.
st_trips = st_trips.dropna(
    subset=["arr_min", "dep_min"]
)

# Duração de cada viagem: primeira partida até última chegada.
tempo_viagem = (
    st_trips.groupby(["trip_id", "route_id"])
    .agg(
        horario_inicio=("dep_min", "min"),
        horario_fim=("arr_min", "max"),
    )
    .reset_index()
)

tempo_viagem["duracao_viagem_min"] = (
    tempo_viagem["horario_fim"]
    - tempo_viagem["horario_inicio"]
)

# Remove durações inválidas.
tempo_viagem = tempo_viagem[
    tempo_viagem["duracao_viagem_min"] >= 0
].copy()

# Faixa horária da primeira partida, na hora do relógio (0-23).
# O GTFS usa horários após 24:00 para viagens que passam da meia-noite
# (ex.: 25:10 = 01:10); o módulo 24 junta essas viagens à faixa correta.
tempo_viagem["faixa_horaria"] = (
    (tempo_viagem["horario_inicio"] // 60) % 24
).astype(int)

# Junta duração e extensão de cada viagem.
tempo_viagem = tempo_viagem.merge(
    trips_com_extensao[["trip_id", "route_short_name", "extensao_km"]],
    on="trip_id",
    how="inner",
)

# Médias por (linha, faixa), ponderadas pelas viagens de cada variante
# (ex.: no pico da linha 51 entram as viagens Direta, mais curtas).
# Tempo de ciclo: as viagens do GTFS da BHTRANS são circulares (saem e
# voltam à mesma estação), logo a duração já é o ciclo ida + volta.
# Soma-se apenas a margem de regulação no terminal (MARGEM_TERMINAL).
parametros_linhas = (
    tempo_viagem.groupby(["route_short_name", "faixa_horaria"])
    .agg(
        duracao_viagem_min=("duracao_viagem_min", "mean"),
        extensao_km=("extensao_km", "mean"),
        viagens_gtfs=("trip_id", "count"),
    )
    .reset_index()
)

parametros_linhas["tempo_ciclo_horas"] = (
    parametros_linhas["duracao_viagem_min"] * MARGEM_TERMINAL / 60.0
).round(2)
parametros_linhas["extensao_km"] = parametros_linhas["extensao_km"].round(3)
# O custo por viagem (c_lt) é calculado em cria_instancia_teste.py.


# 6. Resultados e Exportação dos Parâmetros
print("\n=== PARÂMETROS EXTRAÍDOS ===")

colunas_saida = [
    "route_short_name",
    "faixa_horaria",
    "extensao_km",
    "tempo_ciclo_horas",
    "viagens_gtfs",
]

print(
    parametros_linhas[colunas_saida]
    .sort_values(["route_short_name", "faixa_horaria"])
    .head(15)
    .to_string(index=False)
)

arquivo_saida = "parametros_gtfs_extraidos.csv"

parametros_linhas[colunas_saida].to_csv(
    arquivo_saida,
    index=False,
    encoding="utf-8-sig",
)

print(f"\nArquivo '{arquivo_saida}' gerado com sucesso!")
