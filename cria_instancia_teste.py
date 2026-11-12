"""
Monta a instância do modelo (linhas x 24 faixas horárias) a partir de:
  parametros_gtfs_extraidos.csv          (extracao_dados_gtfs.py) [GTFS]
  dados_pbh/demanda_diaria_linhas.csv    (demanda_pbh.py)         [BHTRANS]
e dos parâmetros de config.py.

Uso como módulo: montar_instancia(lambda_demanda=..., perfil=...) devolve o
DataFrame da instância (usado nas análises de demanda e robustez).
Uso como script: grava instancia_modelo_bhtrans.csv com os valores do config.
"""

import math
import sys

import numpy as np
import pandas as pd

import config


def _carregar_gtfs():
    df_gtfs = pd.read_csv("parametros_gtfs_extraidos.csv")
    df_gtfs["route_short_name"] = df_gtfs["route_short_name"].astype(str).str.strip()
    sem_gtfs = sorted(set(config.LINHAS_CORREDOR) - set(df_gtfs["route_short_name"]))
    if sem_gtfs:
        raise SystemExit(f"ERRO: linhas sem dados no GTFS: {sem_gtfs}")
    return df_gtfs


def _limites_demanda():
    try:
        dem = pd.read_csv("dados_pbh/demanda_diaria_linhas.csv", dtype={"linha": str})
    except FileNotFoundError:
        raise SystemExit("ERRO: rode antes 'python demanda_pbh.py'.")
    dem = dem.set_index("linha")
    faltam = sorted(set(config.LINHAS_CORREDOR) - set(dem.index))
    if faltam:
        raise SystemExit(f"ERRO: linhas sem demanda em demanda_diaria_linhas.csv: {faltam}")
    inf = dem["demanda_dia_util_inferior"].reindex(config.LINHAS_CORREDOR)
    sup = dem["demanda_dia_util_superior"].reindex(config.LINHAS_CORREDOR)
    viagens = dem["viagens_gtfs_dia_util"].reindex(config.LINHAS_CORREDOR)
    return inf * config.FATOR_TRECHO_CRITICO, sup * config.FATOR_TRECHO_CRITICO, viagens


def calibracao_lambda():
    """
    λ calibrado: capacidade total da grade atual (viagens GTFS x capacidade do
    articulado) = demanda total (ocupação média de 100%). Devolve também, por
    linha, o λ em que a grade atual daquela linha satura -- que mostra o quanto
    o rateio dos embarques das estações difere entre as linhas.
    """
    inf, sup, viagens = _limites_demanda()
    cap = config.TIPOS_VEICULO["articulado"]["capacidade"]
    lam_total = (cap * viagens.sum() - inf.sum()) / (sup.sum() - inf.sum())
    lam_linha = (cap * viagens - inf) / (sup - inf)
    return float(lam_total), lam_linha


def lambda_efetivo(lambda_demanda=None):
    lam = config.LAMBDA_DEMANDA if lambda_demanda is None else lambda_demanda
    if lam == "calibrado":
        lam = round(calibracao_lambda()[0], 3)
    return float(lam)


def demanda_diaria(lambda_demanda=None):
    """Demanda diária por linha (pas/dia útil, já convertida pelo fator de
    trecho crítico): inf + λ (sup - inf)."""
    if config.FONTE_DEMANDA == "hipotese":
        return pd.Series({l: config.DEMANDA_PICO_LINHA[l] * sum(config.FATORES_DEMANDA.values())
                          for l in config.LINHAS_CORREDOR})
    lam = lambda_efetivo(lambda_demanda)
    inf, sup, _ = _limites_demanda()
    return inf + lam * (sup - inf)


def _arredondar_mantendo_soma(valores, total):
    """Arredondamento pelo maior resto: inteiros que somam exatamente `total`."""
    base = np.floor(valores).astype(int)
    falta = int(round(total)) - base.sum()
    if falta > 0:
        ordem = np.argsort(-(valores - base))[:falta]
        base[ordem] += 1
    return base


def f_min_padrao(hora, opera):
    """f_min pelo intervalo máximo entre ônibus (padrão de serviço)."""
    if not opera:
        return 0
    if hora in config.HORAS_PICO:
        periodo = "pico"
    elif hora in config.HORAS_DIA:
        periodo = "dia"
    else:
        periodo = "noite"
    return math.ceil(60 / config.INTERVALO_MAX_MIN[periodo])


def montar_instancia(lambda_demanda=None, perfil=None):
    perfil = config.PERFIL_HORARIO if perfil is None else perfil
    df_gtfs = _carregar_gtfs()

    # Grade completa: todas as linhas x 24 faixas horárias
    grade = pd.MultiIndex.from_product(
        [config.LINHAS_CORREDOR, range(24)], names=["route_short_name", "faixa_horaria"]
    ).to_frame(index=False)
    df = grade.merge(df_gtfs, on=["route_short_name", "faixa_horaria"], how="left")
    df["opera_no_gtfs"] = df["tempo_ciclo_horas"].notna().astype(int)
    df["viagens_gtfs"] = df["viagens_gtfs"].fillna(0).astype(int)

    # Faixas sem viagem no GTFS: extensão e ciclo médios da linha (ponderados)
    def media_pond(g, col):
        return (g[col] * g["viagens_gtfs"]).sum() / g["viagens_gtfs"].sum()

    por_linha = pd.DataFrame({
        "extensao_linha": df_gtfs.groupby("route_short_name").apply(media_pond, "extensao_km", include_groups=False),
        "ciclo_medio": df_gtfs.groupby("route_short_name").apply(media_pond, "tempo_ciclo_horas", include_groups=False),
    }).reset_index()
    df = df.merge(por_linha, on="route_short_name", how="left")
    df["extensao_km"] = df["extensao_km"].fillna(df["extensao_linha"].round(3))
    df["tempo_ciclo_horas"] = df["tempo_ciclo_horas"].fillna(df["ciclo_medio"].round(2))
    if not config.USAR_EXTENSAO_GTFS:
        df["extensao_km"] = config.D_L_RELATORIO

    # Demanda: total diário da linha distribuído pelas 24 faixas
    diaria = demanda_diaria(lambda_demanda)
    if perfil == "gtfs":
        peso = df["viagens_gtfs"].astype(float)
    elif perfil == "tipico":
        peso = df["faixa_horaria"].map(config.FATORES_DEMANDA).astype(float)
    else:
        raise ValueError(f"Perfil horário inválido: {perfil}")
    df["d_lt"] = 0
    for l, idx in df.groupby("route_short_name").groups.items():
        w = peso.loc[idx].to_numpy()
        valores = diaria[l] * w / w.sum()
        df.loc[idx, "d_lt"] = _arredondar_mantendo_soma(valores, diaria[l])

    # Padrão de serviço (f_min) e limite físico por linha (f_max)
    df["f_min"] = [f_min_padrao(h, o) for h, o in zip(df["faixa_horaria"], df["opera_no_gtfs"])]
    if config.OPERAR_FORA_DO_HORARIO_GTFS:
        df["f_max"] = config.F_MAX
    else:
        df["f_max"] = config.F_MAX * df["opera_no_gtfs"]

    colunas = ["route_short_name", "faixa_horaria", "opera_no_gtfs", "viagens_gtfs",
               "extensao_km", "tempo_ciclo_horas", "d_lt", "f_min", "f_max"]
    return df[colunas].sort_values(["route_short_name", "faixa_horaria"]).reset_index(drop=True)


if __name__ == "__main__":
    from modelo import capacidade_corredor, frota_grade_atual

    inst = montar_instancia()
    inst.to_csv("instancia_modelo_bhtrans.csv", index=False)
    print("=== INSTÂNCIA CONSOLIDADA ===")
    print(inst.head(12).to_string(index=False))
    lam_tot, lam_lin = calibracao_lambda()
    print(f"\nλ usado: {lambda_efetivo():.3f} (config: {config.LAMBDA_DEMANDA})")
    print(f"λ calibrado (grade atual com ocupação média de 100%): {lam_tot:.3f}")
    print("λ em que a grade de cada linha satura:", lam_lin.round(3).to_dict())
    print(f"Demanda total: {inst['d_lt'].sum():,} pas/dia útil")
    print("Demanda por linha:", inst.groupby("route_short_name")["d_lt"].sum().to_dict())
    print(f"Frota exigida pela grade atual (GTFS): {frota_grade_atual(inst)} veículos")
    print(f"Capacidade do corredor (partidas/h): {capacidade_corredor(inst)}")
    print("\nArquivo 'instancia_modelo_bhtrans.csv' gerado!")
    sys.exit(0)
