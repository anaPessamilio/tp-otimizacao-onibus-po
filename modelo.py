"""
Modelo PLIM de otimização de frequências e tipos de veículo (implementação
única, usada por todos os scripts de análise).

Conjuntos: linhas l, faixas t = 0..23, tipos de veículo k.

    min Z = α1 Σ_{l,t,k} c_ltk f_ltk + α2 Σ_{l,t} w_lt

    (R1) Σ_l Σ_s ω(t-s, n_ls) f_lsk <= F_k          ∀ t, k   frota acumulada
    (R2) Σ_k C_k f_ltk + w_lt >= d_lt + w_l,t-1      ∀ l, t   atendimento
         (o termo w_l,t-1 só existe no modo "espera"; no modo "perda" é 0)
    (R3) Σ_l Σ_k f_ltk <= CAP                         ∀ t      corredor
    (R4) f_min_lt <= Σ_k f_ltk <= f_max_lt            ∀ l, t   padrão de serviço
         f_ltk inteiro >= 0, w_lt >= 0

c_ltk = D_lt × custo/km do tipo k. ω(k, n) = fração média da faixa s + k em
que um ônibus que partiu na faixa s (instante uniforme) com ciclo n ainda está
em operação; Σ_k ω(k, n) = n. O dia é cíclico em R1.

d_lt é a carga no trecho crítico (Ceder, 2016). No modo "espera", w_lt são os
passageiros que terminam a faixa t ainda esperando; Σ w = passageiro-hora de
espera excedente.
"""

import math
from functools import lru_cache

import gurobipy as gp
import numpy as np
import pandas as pd
from gurobipy import GRB

import config

COLUNAS_OBRIGATORIAS = [
    "route_short_name", "faixa_horaria", "viagens_gtfs", "extensao_km",
    "tempo_ciclo_horas", "d_lt", "f_min", "f_max",
]
N_HORAS = 24


# ------------------------------------------------------------------ frota acumulada
@lru_cache(maxsize=None)
def peso_ocupacao(k, ciclo_horas):
    """ω(k, n): fração média da faixa (s + k) ocupada por um ônibus que
    partiu na faixa s num instante uniforme u ∈ [0, 1), com ciclo n horas."""
    u = (np.arange(4000) + 0.5) / 4000
    sobreposicao = np.minimum(u + ciclo_horas, k + 1) - np.maximum(u, k)
    return float(np.clip(sobreposicao, 0.0, None).mean())


def _pesos_frota(pares, n):
    """Para cada faixa t: lista de (par_origem, peso) que ocupam frota em t."""
    max_k = math.ceil(max(n.values())) + 1
    por_faixa = {t: [] for t in range(N_HORAS)}
    for (l, s) in pares:
        for k in range(max_k + 1):
            peso = peso_ocupacao(k, round(n[(l, s)], 4))
            if peso > 1e-9:
                por_faixa[(s + k) % N_HORAS].append(((l, s), peso))
    return por_faixa


def frota_em_operacao(df, coluna_freq):
    """Veículos em operação por faixa para as frequências de `coluna_freq`."""
    dados = df.set_index(["route_short_name", "faixa_horaria"])
    n = dados["tempo_ciclo_horas"].to_dict()
    freq = dados[coluna_freq].fillna(0).to_dict()
    pesos = _pesos_frota(list(dados.index), n)
    return pd.Series(
        {t: sum(p * freq[par] for par, p in termos) for t, termos in pesos.items()}
    ).sort_index()


# ------------------------------------------------------------------ parâmetros derivados
def frota_grade_atual(df):
    """Frota máxima em operação exigida pela grade atual (GTFS)."""
    return math.ceil(frota_em_operacao(df, "viagens_gtfs").max() - 1e-9)


def capacidade_corredor(df, valor=None):
    valor = config.CAP_CORREDOR if valor is None else valor
    if valor == "grade_atual":
        return int(df.groupby("faixa_horaria")["viagens_gtfs"].sum().max())
    return None if valor is None else int(valor)


def resolver_tipos(df, tipos=None):
    """Converte TIPOS_VEICULO em valores numéricos (frota "grade_atual" etc.)."""
    tipos = config.TIPOS_VEICULO if tipos is None else tipos
    saida = {}
    for k, t in tipos.items():
        frota = frota_grade_atual(df) if t["frota"] == "grade_atual" else int(t["frota"])
        saida[k] = {"capacidade": t["capacidade"], "custo_km": t["custo_km"], "frota": frota}
    return saida


# ------------------------------------------------------------------ modelo
def construir_modelo(df, alpha_1, alpha_2, tipos=None, cap_corredor="config",
                     nao_atendidos=None, frota_extra=None, nome="Modelo", log=False):
    """
    Monta (sem resolver) o PLIM.

    tipos:         dict como config.TIPOS_VEICULO (default: o do config).
    cap_corredor:  "config" (usa config.CAP_CORREDOR), None (sem limite) ou número.
    nao_atendidos: "espera" ou "perda" (default: config.NAO_ATENDIDOS).
    frota_extra:   {(tipo, faixa): veículos a somar ao limite} (pós-otimização).
    """
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(f"Instância sem as colunas obrigatórias: {faltando}")

    dados = df.set_index(["route_short_name", "faixa_horaria"])
    if not dados.index.is_unique:
        raise ValueError("Há pares (linha, faixa) duplicados na instância.")

    tipos = resolver_tipos(df, tipos)
    cap = capacidade_corredor(df) if cap_corredor == "config" else (
        None if cap_corredor is None else int(cap_corredor))
    modo = config.NAO_ATENDIDOS if nao_atendidos is None else nao_atendidos
    frota_extra = frota_extra or {}

    pares = list(dados.index)
    linhas = sorted({l for (l, _) in pares})
    n = dados["tempo_ciclo_horas"].to_dict()
    D = dados["extensao_km"].to_dict()
    d = dados["d_lt"].to_dict()
    f_min = dados["f_min"].to_dict()
    f_max = dados["f_max"].to_dict()
    pesos = _pesos_frota(pares, n)
    K = list(tipos)
    c = {(l, t, k): round(D[(l, t)] * tipos[k]["custo_km"], 2) for (l, t) in pares for k in K}

    model = gp.Model(nome)
    model.Params.OutputFlag = 1 if log else 0

    idx = [(l, t, k) for (l, t) in pares for k in K]
    f = model.addVars(
        idx, vtype=GRB.INTEGER, lb=0,
        ub={(l, t, k): (f_max[(l, t)] if tipos[k]["frota"] > 0 else 0) for (l, t, k) in idx},
        name="f",
    )
    w = model.addVars(pares, lb=0.0, name="w")

    custo_operacional = gp.quicksum(c[i] * f[i] for i in idx)
    deficit = gp.quicksum(w[p] for p in pares)
    model.setObjective(alpha_1 * custo_operacional + alpha_2 * deficit, GRB.MINIMIZE)

    # R1: frota acumulada por tipo e faixa
    r1 = {}
    for k in K:
        if tipos[k]["frota"] <= 0:
            continue
        for t, termos in pesos.items():
            limite = tipos[k]["frota"] + frota_extra.get((k, t), 0)
            r1[(k, t)] = model.addConstr(
                gp.quicksum(p * f[l, s, k] for (l, s), p in termos) <= limite,
                name=f"Frota_{k}_t{t}",
            )

    # R2: atendimento (com fila no modo "espera")
    r2 = {}
    for (l, t) in pares:
        anterior = w[l, t - 1] if (modo == "espera" and t > 0 and (l, t - 1) in w) else 0
        r2[(l, t)] = model.addConstr(
            gp.quicksum(tipos[k]["capacidade"] * f[l, t, k] for k in K) + w[l, t]
            >= d[(l, t)] + anterior,
            name=f"Atendimento_l{l}_t{t}",
        )

    # R3: capacidade do corredor
    r3 = {}
    if cap is not None:
        for t in range(N_HORAS):
            r3[t] = model.addConstr(
                gp.quicksum(f[l, t, k] for l in linhas for k in K if (l, t) in dados.index) <= cap,
                name=f"Corredor_t{t}",
            )

    # R4: padrão de serviço
    for (l, t) in pares:
        total = gp.quicksum(f[l, t, k] for k in K)
        if f_min[(l, t)] > 0:
            model.addConstr(total >= f_min[(l, t)], name=f"Fmin_l{l}_t{t}")
        model.addConstr(total <= f_max[(l, t)], name=f"Fmax_l{l}_t{t}")

    model.update()
    return {
        "model": model, "f": f, "w": w, "r1": r1, "r2": r2, "r3": r3,
        "pares": pares, "pesos": pesos, "tipos": tipos, "cap": cap, "modo": modo,
        "c": c, "n": n, "d": d, "K": K,
        "custo_operacional": custo_operacional, "deficit": deficit,
    }


def _extrair(m, df):
    """Monta o dicionário de resultados a partir de um modelo resolvido."""
    f, w, K, pares, pesos = m["f"], m["w"], m["K"], m["pares"], m["pesos"]
    tipos, d, c = m["tipos"], m["d"], m["c"]
    gtfs = df.set_index(["route_short_name", "faixa_horaria"])["viagens_gtfs"].fillna(0).to_dict()

    veic = {(l, t): 0.0 for (l, t) in pares}
    frota_tipo = {k: pd.Series(0.0, index=range(N_HORAS)) for k in K}
    for t, termos in pesos.items():
        for (l, s), p in termos:
            for k in K:
                v = p * f[l, s, k].X
                veic[(l, t)] += v
                frota_tipo[k][t] += v

    linhas_det = []
    for (l, t) in pares:
        reg = {"linha": l, "faixa_horaria": t}
        total = 0
        for k in K:
            reg[f"f_{k}"] = int(round(f[l, t, k].X))
            total += reg[f"f_{k}"]
        reg.update({
            "frequencia_otima": total,
            "viagens_gtfs": int(gtfs[(l, t)]),
            "demanda": d[(l, t)],
            "capacidade_ofertada": int(round(sum(tipos[k]["capacidade"] * f[l, t, k].X for k in K))),
            "passageiros_represados": round(w[l, t].X, 1),
            "veiculos_em_operacao": round(veic[(l, t)], 2),
            "custo_operacional_R$": round(sum(c[(l, t, k)] * f[l, t, k].X for k in K), 2),
        })
        linhas_det.append(reg)
    detalhe = pd.DataFrame(linhas_det)
    model = m["model"]
    return {
        "status": model.Status,
        "valor_obj_Z": model.ObjVal,
        "limitante": model.ObjBound,
        "gap": model.MIPGap,
        "nos": model.NodeCount,
        "tempo_s": model.Runtime,
        "custo_operacional": m["custo_operacional"].getValue(),
        "passageiros_represados": m["deficit"].getValue(),
        "demanda_total": sum(d.values()),
        "frota_por_faixa": detalhe.groupby("faixa_horaria")["veiculos_em_operacao"].sum(),
        "frota_por_tipo": frota_tipo,
        "tipos": tipos,
        "cap_corredor": m["cap"],
        "detalhe": detalhe,
    }


def resolver_modelo(df, alpha_1=None, alpha_2=None, nome="Modelo", log=False,
                    arquivo_log=None, **kwargs):
    """Constrói e resolve o PLIM. Retorna {"status": ...} se não for ótimo."""
    alpha_1 = config.ALPHA_1 if alpha_1 is None else alpha_1
    alpha_2 = config.ALPHA_2 if alpha_2 is None else alpha_2
    m = construir_modelo(df, alpha_1, alpha_2, nome=nome, log=log, **kwargs)
    if arquivo_log:
        m["model"].Params.LogFile = arquivo_log
    m["model"].optimize()
    if m["model"].Status != GRB.OPTIMAL:
        return {"status": m["model"].Status}
    res = _extrair(m, df)
    res["modelo"] = m
    return res


def faixas_frota_saturada(res, tolerancia=1.0):
    """Faixas em que algum tipo de veículo está a menos de `tolerancia`
    veículo(s) do limite de frota."""
    saturadas = set()
    for k, serie in res["frota_por_tipo"].items():
        F = res["tipos"][k]["frota"]
        if F > 0:
            saturadas |= set(serie[serie >= F - tolerancia].index)
    return len(saturadas)


# ------------------------------------------------------------------ avaliação da grade atual
def avaliar_grade(df, coluna_freq="viagens_gtfs", tipo="articulado", alpha_1=None,
                  alpha_2=None, nao_atendidos=None):
    """
    Avalia uma grade fixa (ex.: a atual, do GTFS) com as mesmas regras do
    modelo: custo, passageiros em espera/perdidos, frota em operação e
    partidas por hora no corredor. A grade usa um único tipo de veículo.
    """
    alpha_1 = config.ALPHA_1 if alpha_1 is None else alpha_1
    alpha_2 = config.ALPHA_2 if alpha_2 is None else alpha_2
    modo = config.NAO_ATENDIDOS if nao_atendidos is None else nao_atendidos
    tp = resolver_tipos(df)[tipo]
    linhas_det = []
    for l, g in df.sort_values("faixa_horaria").groupby("route_short_name"):
        espera = 0.0
        for _, r in g.iterrows():
            freq = 0 if pd.isna(r[coluna_freq]) else r[coluna_freq]
            carga = r.d_lt + (espera if modo == "espera" else 0)
            w = max(0.0, carga - tp["capacidade"] * freq)
            espera = w
            linhas_det.append({
                "linha": l, "faixa_horaria": int(r.faixa_horaria), "frequencia": freq,
                "demanda": r.d_lt, "passageiros_represados": w,
                "custo_operacional_R$": freq * r.extensao_km * tp["custo_km"],
            })
    det = pd.DataFrame(linhas_det)
    frota = frota_em_operacao(df, coluna_freq)
    custo, deficit = det["custo_operacional_R$"].sum(), det["passageiros_represados"].sum()
    return {
        "valor_obj_Z": alpha_1 * custo + alpha_2 * deficit,
        "custo_operacional": custo,
        "passageiros_represados": deficit,
        "demanda_total": det["demanda"].sum(),
        "viagens": det["frequencia"].sum(),
        "frota_por_faixa": frota,
        "partidas_por_hora": det.groupby("faixa_horaria")["frequencia"].sum(),
        "detalhe": det,
    }
