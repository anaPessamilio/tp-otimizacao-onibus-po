import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString



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
linhas_corredor = ["51", "52", "63", "64", "67"]

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

# Viagens associadas às linhas selecionadas.
trips_filtradas = trips[
    trips["route_id"].isin(route_ids)
].copy()

if trips_filtradas.empty:
    print("Nenhuma viagem encontrada para as linhas selecionadas.")
    sys.exit(1)


# 4. Cálculo da Extensão das Linhas (D_l)
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

# Extensão média por route_id.
extensao_media_por_linha = (
    trips_com_extensao.groupby("route_id")["extensao_km"]
    .mean()
    .reset_index()
)

extensao_media_por_linha = extensao_media_por_linha.merge(
    routes_filtradas[["route_id", "route_short_name"]],
    on="route_id",
    how="left",
)


# 5. Cálculo do Tempo de Ciclo e de Custo
print("\nCalculando tempos de ciclo e custos operacionais...")

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

# Faixa horária da primeira partida.
tempo_viagem["faixa_horaria"] = (
    tempo_viagem["horario_inicio"] // 60
).astype(int)

# ATENÇÃO:
# Essa parte considera ida + volta e 15% de margem para o terminal.
# Essa é uma hipótese de modelagem, não um ciclo medido
# diretamente pelo GTFS.
ciclo_por_faixa = (
    tempo_viagem.groupby(["route_id", "faixa_horaria"])[
        "duracao_viagem_min"
    ]
    .mean()
    .reset_index()
)

ciclo_por_faixa["tempo_ciclo_horas"] = (
    ciclo_por_faixa["duracao_viagem_min"] * 2 * 1.15 / 60.0
).round(2)

# Associação com as extensões médias.
parametros_linhas = ciclo_por_faixa.merge(
    extensao_media_por_linha[
        ["route_id", "route_short_name", "extensao_km"]
    ],
    on="route_id",
    how="inner",
)

# Custo operacional estimado.
custo_por_km = 11.00  # R$/km

parametros_linhas["c_lt"] = (
    parametros_linhas["extensao_km"] * custo_por_km
).round(2)


# 6. Resultados e Exportação dos Parâmetros
print("\n=== PARÂMETROS EXTRAÍDOS ===")

colunas_saida = [
    "route_short_name",
    "faixa_horaria",
    "extensao_km",
    "tempo_ciclo_horas",
    "c_lt",
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
