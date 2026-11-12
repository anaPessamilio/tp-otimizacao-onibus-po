"""
Demanda real das linhas troncais do MOVE Antônio Carlos a partir dos
relatórios mensais publicados pela BHTRANS ("Sistema de Transporte por Ônibus
Convencional e MOVE de BH"), seção "PASSAGEIROS DO MOVE - CORREDOR ANTÔNIO
CARLOS - ACOMPANHAMENTO MENSAL".

Fonte (PDF mensal, um por mês):
  https://prefeitura.pbh.gov.br/sites/default/files/estrutura-de-governo/
  bhtrans/<ANO>/relatorio-de-<mes>-<ano>-para_publicacao.pdf

O servidor da PBH bloqueia downloads automatizados (HTTP 403). Se o download
falhar, baixe o PDF pelo navegador e salve em dados_pbh/ (qualquer nome .pdf).

Como a demanda é montada
------------------------
No MOVE, quem embarca numa estação passa pela catraca da estação: esse
passageiro é registrado na estação (AC01-AC25) ou nas linhas de bloqueio/
acesso das estações de integração (2000/2001, 6000/6001, 7000/7001), e não
na linha troncal. Por isso:

  demanda_dia_util(l) = registro_no_onibus(l)
                        + rateio(l) x embarques_nas_estacoes

com rateio proporcional às viagens programadas de cada troncal em dia útil
(GTFS), entre as linhas do modelo. Usa-se a média de dias úteis (MÉDIA DU)
dos meses disponíveis no relatório.

Saídas (em dados_pbh/):
  passageiros_corredor_antonio_carlos.csv   tabela extraída (longa)
  demanda_diaria_linhas.csv                 demanda por linha (dia útil)
"""

import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import requests

from config import LINHAS_CORREDOR

PASTA = Path("dados_pbh")
PASTA.mkdir(exist_ok=True)

URL_RELATORIO = (
    "https://prefeitura.pbh.gov.br/sites/default/files/estrutura-de-governo/"
    "bhtrans/2026/relatorio-de-agosto-2026-para_publicacao.pdf"
)

# Códigos que representam embarques registrados nas estações do corredor.
ESTACOES = [f"AC{i:02d}" for i in range(1, 26)] + [
    "2000", "2001",  # bloqueio Estação Venda Nova
    "6000", "6001",  # acesso / bloqueio Estação Pampulha
    "7000", "7001",  # acesso / bloqueio Estação Vilarinho
]

TITULO_SECAO = "PASSAGEIROS DO MOVE - CORREDOR ANTÔNIO CARLOS"


# ------------------------------------------------------------------ 1. PDF
def obter_pdf():
    existentes = sorted(PASTA.glob("*.pdf"))
    if existentes:
        print(f"Usando relatório(s) local(is): {[p.name for p in existentes]}")
        return existentes

    print(f"Baixando relatório da BHTRANS:\n  {URL_RELATORIO}")
    try:
        r = requests.get(URL_RELATORIO, timeout=120)
        if r.ok and r.content[:4] == b"%PDF":
            destino = PASTA / Path(URL_RELATORIO).name
            destino.write_bytes(r.content)
            return [destino]
        print(f"Download recusado pelo servidor (HTTP {r.status_code}).")
    except requests.RequestException as e:
        print(f"Falha no download: {e}")

    print(
        "\nBaixe o PDF manualmente pelo navegador (link acima) e salve na "
        f"pasta '{PASTA}/'. Depois rode este script novamente."
    )
    sys.exit(1)


# ------------------------------------------------------------------ 2. extração
NUM = r"(?:\d{1,3}(?:\.\d{3})*|\*)"
LINHA_RE = re.compile(rf"^(\S+)\s+(.+?)\s*((?:{NUM}\s+){{11}}{NUM})\s*$")
MESES_RE = re.compile(r"([A-ZÇ]+)/(\d{4})")


def para_int(token):
    return None if token == "*" else int(token.replace(".", ""))


def extrair_tabela(pdf_path):
    # A página da tabela contém o título da seção e o cabeçalho "MÉDIA DU"
    # (o sumário na página 1 também cita o título, mas não tem a tabela).
    with pdfplumber.open(pdf_path) as pdf:
        textos = (p.extract_text() or "" for p in pdf.pages)
        pagina = next(
            (t for t in textos if TITULO_SECAO in t and "MÉDIA DU" in t), None
        )
    if pagina is None:
        raise ValueError(f"Seção '{TITULO_SECAO}' não encontrada em {pdf_path}")

    linhas = pagina.split("\n")
    meses = MESES_RE.findall(
        next(l for l in linhas if l.startswith("LINHAS") and MESES_RE.search(l))
    )
    meses = [f"{m}/{a}" for m, a in meses]

    registros = []
    for texto in linhas:
        if texto.startswith("TOTAIS"):
            break  # fim da tabela de troncais e estações
        m = LINHA_RE.match(texto)
        if not m:
            continue
        codigo, nome, numeros = m.group(1), m.group(2), m.group(3).split()
        for i, mes in enumerate(meses):
            registros.append({
                "codigo": codigo,
                "nome": nome,
                "mes": mes,
                "total_mes": para_int(numeros[2 * i]),
                "media_dia_util": para_int(numeros[2 * i + 1]),
                "arquivo": Path(pdf_path).name,
            })
    return pd.DataFrame(registros)


# ------------------------------------------------------------------ 3. demanda
def viagens_dia_util_gtfs(linhas, pasta_gtfs=Path("gtfs_bhtrans")):
    """Número de viagens programadas em dia útil por linha (route_short_name)."""
    routes = pd.read_csv(pasta_gtfs / "routes.txt", dtype=str)
    trips = pd.read_csv(pasta_gtfs / "trips.txt", dtype=str)
    calendar = pd.read_csv(pasta_gtfs / "calendar.txt", dtype={"service_id": str})
    uteis = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    servicos = calendar.loc[
        (calendar[uteis].sum(axis=1) == 5)
        & (calendar["saturday"] == 0)
        & (calendar["sunday"] == 0),
        "service_id",
    ]
    routes["route_short_name"] = routes["route_short_name"].str.strip()
    t = trips[trips["service_id"].isin(servicos)].merge(
        routes[["route_id", "route_short_name"]], on="route_id"
    )
    return (
        t[t["route_short_name"].isin(linhas)]
        .groupby("route_short_name")
        .size()
        .reindex(linhas)
        .fillna(0)
        .astype(int)
    )


def montar_demanda(tabela):
    media = (
        tabela.dropna(subset=["media_dia_util"])
        .drop_duplicates(["codigo", "mes"])
        .groupby("codigo")["media_dia_util"]
        .mean()
    )
    meses = sorted(tabela["mes"].unique())

    registro_proprio = {l: float(media.get(l, 0.0)) for l in LINHAS_CORREDOR}
    embarques_estacoes = float(media.reindex(ESTACOES).fillna(0).sum())

    # Os embarques das estações são rateados pelas viagens programadas em dia
    # útil (GTFS). Não se sabe quantos desses passageiros usam outras linhas
    # listadas pela BHTRANS no corredor (5250, 5550, 6031, 6350), então
    # geram-se dois limites:
    #   superior: rateio só entre as linhas do modelo;
    #   inferior: rateio entre as linhas do modelo e todas as demais do corredor.
    outras = sorted(set(tabela["codigo"]) - set(ESTACOES) - set(LINHAS_CORREDOR))
    viagens = viagens_dia_util_gtfs(list(LINHAS_CORREDOR) + outras)
    print("\nViagens de dia útil no GTFS usadas no rateio das estações:")
    print(viagens.to_string())

    v_modelo = viagens[list(LINHAS_CORREDOR)]
    rateio_sup = v_modelo / v_modelo.sum()
    rateio_inf = v_modelo / viagens.sum()

    demanda = pd.DataFrame({
        "linha": LINHAS_CORREDOR,
        "registro_no_onibus": [round(registro_proprio[l]) for l in LINHAS_CORREDOR],
        "viagens_gtfs_dia_util": v_modelo.values,
        "rateio_superior": rateio_sup.round(4).values,
        "rateio_inferior": rateio_inf.round(4).values,
    })
    for limite, col in [("superior", "rateio_superior"), ("inferior", "rateio_inferior")]:
        demanda[f"demanda_dia_util_{limite}"] = (
            demanda["registro_no_onibus"] + (demanda[col] * embarques_estacoes).round()
        ).astype(int)
    demanda["periodo"] = f"média de dias úteis ({', '.join(meses)})"
    return demanda, embarques_estacoes


if __name__ == "__main__":
    tabelas = [extrair_tabela(p) for p in obter_pdf()]
    tabela = pd.concat(tabelas, ignore_index=True)
    tabela.to_csv(PASTA / "passageiros_corredor_antonio_carlos.csv", index=False)

    demanda, estacoes = montar_demanda(tabela)
    demanda.to_csv(PASTA / "demanda_diaria_linhas.csv", index=False)

    print(f"\nRegistros extraídos: {len(tabela)} ({tabela['codigo'].nunique()} códigos)")
    print(f"Embarques médios nas estações do corredor (dia útil): {estacoes:,.0f}")
    print("\n=== DEMANDA DIÁRIA POR LINHA TRONCAL (DIA ÚTIL) ===")
    print(demanda.drop(columns="periodo").to_string(index=False))
    for lim in ["superior", "inferior"]:
        total = demanda[f"demanda_dia_util_{lim}"].sum()
        print(f"Total (limite {lim}): {total:,} passageiros/dia útil")
    print(f"Arquivos gerados em '{PASTA}/'.")
