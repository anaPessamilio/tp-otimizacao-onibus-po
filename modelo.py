"""
Modelo PLIM de otimização de frequências (única implementação, usada por
otimizacao.py, gera_instancias.py e analise_sensibilidade_alpha.py).

    Min Z = α1 Σ_{l,t} c_lt f_lt + α2 Σ_{l,t} w_lt
    s.a.  Σ_l Σ_k ω(k, n_{l,t-k}) f_{l,t-k} <= Frota_Max   para toda faixa t (R1)
          C_l f_lt + w_lt >= d_lt                          para todo (l, t)  (R2)
          f_min_lt <= f_lt <= f_max_lt,  f_lt inteiro
          w_lt >= 0

R1 (frota acumulada): um ônibus que parte na faixa s fica em operação durante
o seu tempo de ciclo n, ocupando também as faixas seguintes. ω(k, n) é a
fração média da faixa s + k em que esse ônibus está rodando, supondo partidas
distribuídas uniformemente dentro da hora. Assim, a frota em t soma os ônibus
que partiram em t e os que partiram antes e ainda não voltaram. Para
frequência constante, Σ_k ω(k, n) = n e R1 recai na fórmula clássica n·f.
O dia é tratado como cíclico (a faixa 0h recebe ônibus que saíram às 23h).

d_lt é interpretado como a carga no trecho crítico (passageiros/hora no ponto
de maior lotação), que é o que precisa caber em C_l · f_lt (Ceder, 2016).
"""

import math
from functools import lru_cache

import gurobipy as gp
import numpy as np
import pandas as pd
from gurobipy import GRB

COLUNAS_OBRIGATORIAS = [
    "route_short_name",
    "faixa_horaria",
    "tempo_ciclo_horas",
    "capacidade_C",
    "c_lt",
    "d_lt",
    "f_min",
    "f_max",
]

N_HORAS = 24


@lru_cache(maxsize=None)
def peso_ocupacao(k, ciclo_horas):
    """
    ω(k, n): fração média da faixa (s + k) em que um ônibus que partiu na
    faixa s, num instante uniforme u ∈ [0, 1), está em operação por n horas.
    Intervalo ocupado: [u, u + n]; faixa avaliada: [k, k + 1].
    """
    u = (np.arange(4000) + 0.5) / 4000  # pontos médios em [0, 1)
    sobreposicao = np.minimum(u + ciclo_horas, k + 1) - np.maximum(u, k)
    return float(np.clip(sobreposicao, 0.0, None).mean())


def _pesos_frota(pares, n):
    """Para cada faixa t, lista de (par_origem, peso) que ocupam frota em t."""
    max_k = math.ceil(max(n.values())) + 1
    por_faixa = {t: [] for t in range(N_HORAS)}
    for (l, s) in pares:
        for k in range(max_k + 1):
            peso = peso_ocupacao(k, round(n[(l, s)], 4))
            if peso > 1e-9:
                por_faixa[(s + k) % N_HORAS].append(((l, s), peso))
    return por_faixa


def construir_modelo(df, frota_max, alpha_1, alpha_2, nome="Modelo", log=False):
    """
    Monta (sem resolver) o PLIM para a instância `df`.

    `frota_max` pode ser um número (mesmo limite em todas as faixas) ou um
    dicionário {faixa: limite}. Retorna um dicionário com o modelo gurobipy,
    as variáveis, as restrições R1 (por faixa) e R2 (por par) e os parâmetros.
    """
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(f"Instância sem as colunas obrigatórias: {faltando}")

    dados = df.set_index(["route_short_name", "faixa_horaria"])
    if not dados.index.is_unique:
        raise ValueError("Há pares (linha, faixa) duplicados na instância.")

    pares = list(dados.index)
    c = dados["c_lt"].to_dict()
    n = dados["tempo_ciclo_horas"].to_dict()
    C = dados["capacidade_C"].to_dict()
    d = dados["d_lt"].to_dict()
    f_min = dados["f_min"].to_dict()
    f_max = dados["f_max"].to_dict()
    pesos = _pesos_frota(pares, n)

    model = gp.Model(nome)
    model.Params.OutputFlag = 1 if log else 0

    f = model.addVars(
        pares,
        vtype=GRB.INTEGER,
        lb={p: f_min[p] for p in pares},
        ub={p: f_max[p] for p in pares},
        name="frequencia",
    )
    w = model.addVars(pares, vtype=GRB.CONTINUOUS, lb=0.0, name="represados")

    custo_operacional = gp.quicksum(c[p] * f[p] for p in pares)
    deficit = gp.quicksum(w[p] for p in pares)
    model.setObjective(alpha_1 * custo_operacional + alpha_2 * deficit, GRB.MINIMIZE)

    limite = frota_max if isinstance(frota_max, dict) else {t: frota_max for t in pesos}

    # R1: frota máxima simultânea por faixa horária (frota acumulada)
    r1 = {}
    for t, termos in pesos.items():
        if termos:
            r1[t] = model.addConstr(
                gp.quicksum(peso * f[p] for p, peso in termos) <= limite[t],
                name=f"Limite_Frota_t{t}",
            )

    # R2: atendimento da demanda (carga no trecho crítico) + déficit
    r2 = {}
    for p in pares:
        l, t = p
        r2[p] = model.addConstr(
            C[p] * f[p] + w[p] >= d[p], name=f"Atendimento_l{l}_t{t}"
        )

    return {
        "model": model, "f": f, "w": w, "r1": r1, "r2": r2,
        "pares": pares, "pesos": pesos, "c": c, "n": n, "C": C, "d": d,
        "custo_operacional": custo_operacional, "deficit": deficit,
    }


def resolver_modelo(df, frota_max, alpha_1, alpha_2, nome="Modelo", log=False):
    """
    Resolve o modelo para a instância `df` (uma linha por par linha x faixa).

    Retorna um dicionário com status, valor objetivo, custo operacional,
    passageiros represados, frota usada por faixa e o DataFrame `detalhe`
    por (linha, faixa). Sem solução ótima, retorna apenas {"status": ...}.
    """
    m = construir_modelo(df, frota_max, alpha_1, alpha_2, nome, log)
    model, f, w = m["model"], m["f"], m["w"]
    pares, pesos, c, n, C, d = (m[k] for k in ("pares", "pesos", "c", "n", "C", "d"))
    custo_operacional, deficit = m["custo_operacional"], m["deficit"]

    model.optimize()

    if model.Status != GRB.OPTIMAL:
        return {"status": model.Status}

    # Ônibus em operação de cada linha em cada faixa (inclui partidas anteriores)
    veiculos = {p: 0.0 for p in pares}
    for t, termos in pesos.items():
        for (l, s), peso in termos:
            if (l, t) in veiculos:
                veiculos[(l, t)] += peso * f[l, s].X

    detalhe = pd.DataFrame(
        [
            {
                "linha": l,
                "faixa_horaria": t,
                "frequencia_otima": int(round(f[l, t].X)),
                "demanda": d[(l, t)],
                "capacidade_ofertada": int(round(f[l, t].X * C[(l, t)])),
                "passageiros_represados": round(w[l, t].X, 1),
                "veiculos_em_operacao": round(veiculos[(l, t)], 2),
                "custo_operacional_R$": round(f[l, t].X * c[(l, t)], 2),
            }
            for (l, t) in pares
        ]
    )

    frota_por_faixa = detalhe.groupby("faixa_horaria")["veiculos_em_operacao"].sum()

    return {
        "status": model.Status,
        "valor_obj_Z": model.ObjVal,
        "custo_operacional": custo_operacional.getValue(),
        "passageiros_represados": deficit.getValue(),
        "demanda_total": sum(d.values()),
        "frota_por_faixa": frota_por_faixa,
        "detalhe": detalhe,
    }


def faixas_frota_saturada(res, frota_max, tolerancia=1.0):
    """Conta as faixas em que a frota em operação está a menos de
    `tolerancia` veículo(s) do limite."""
    return int((res["frota_por_faixa"] >= frota_max - tolerancia).sum())
