import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# 1. Carrega a instância base tratada
df_base = pd.read_csv("instancia_modelo_bhtrans.csv")

# Tratamento rigoroso dos nomes das linhas para evitar falha no .map()
df_base["route_short_name"] = (
    df_base["route_short_name"].astype(str).str.strip()
)

# 2. Definição dos 4 Cenários de Teste
cenarios = {
    "Cenario_0_Baseline": {
        "frota_max": 90,
        "capacidades": {"51": 130, "52": 85, "63": 85, "64": 85, "67": 85},
        "custo_km": {"51": 12.50, "52": 9.50, "63": 9.50, "64": 9.50, "67": 9.50},
    },
    "Cenario_1_Frota_Mista_MOVE": {
        "frota_max": 90,
        "capacidades": {"51": 130, "52": 130, "63": 130, "64": 85, "67": 85},
        "custo_km": {
            "51": 12.50,
            "52": 12.50,
            "63": 12.50,
            "64": 9.50,
            "67": 9.50,
        },
    },
    "Cenario_2_100pct_Articulados": {
        "frota_max": 90,
        "capacidades": {"51": 130, "52": 130, "63": 130, "64": 130, "67": 130},
        "custo_km": {
            "51": 12.50,
            "52": 12.50,
            "63": 12.50,
            "64": 12.50,
            "67": 12.50,
        },
    },
    "Cenario_3_Expansao_Frota_110": {
        "frota_max": 110,
        "capacidades": {"51": 130, "52": 85, "63": 85, "64": 85, "67": 85},
        "custo_km": {"51": 12.50, "52": 9.50, "63": 9.50, "64": 9.50, "67": 9.50},
    },
}

resultados_globais = []
detalhamento_linhas = []

alpha_1 = 1.0  # Peso do Custo Operacional (R$/viagem)
alpha_2 = 25.0  # Penalidade Social (R$/passageiro deixado)

D_L = 34.0  # Extensão do itinerário ida + volta (km) - Seção 3 do relatório

# 3. Looping de Execução dos Cenários no Gurobi
for nome_cenario, config in cenarios.items():
    df_cenario = df_base.copy()

    # Recalcular capacidade e custo por viagem de forma totalmente segura
    df_cenario["capacidade_C"] = (
        df_cenario["route_short_name"]
        .map(config["capacidades"])
        .fillna(85)
        .astype(int)
    )
    df_cenario["custo_por_km"] = (
        df_cenario["route_short_name"]
        .map(config["custo_km"])
        .fillna(9.50)
        .astype(float)
    )
    # c_l = D_l (ida + volta) x Custo/km da tipologia
    df_cenario["c_lt"] = (D_L * df_cenario["custo_por_km"]).round(2)

    df_indexed = df_cenario.set_index(["route_short_name", "faixa_horaria"])

    c_l = df_indexed["c_lt"].to_dict()
    n_lt = df_indexed["tempo_ciclo_horas"].to_dict()
    C_l = df_indexed["capacidade_C"].to_dict()
    d_lt = df_indexed["d_lt"].to_dict()
    f_min = df_indexed["f_min"].to_dict()
    f_max = df_indexed["f_max"].to_dict()

    linhas = df_cenario["route_short_name"].unique().tolist()
    faixas = df_cenario["faixa_horaria"].unique().tolist()
    pares_validos = list(c_l.keys())
    Frota_Max = config["frota_max"]

    # Instanciar Modelo Gurobi
    model = gp.Model(nome_cenario)
    model.Params.OutputFlag = 0  # Silenciar log no terminal

    # Variáveis de Decisão
    f = model.addVars(
        pares_validos,
        vtype=GRB.INTEGER,
        lb={p: f_min[p] for p in pares_validos},
        ub={p: f_max[p] for p in pares_validos},
        name="frequencia",
    )

    w = model.addVars(
        pares_validos,
        vtype=GRB.CONTINUOUS,
        lb=0.0,
        name="passageiros_represados",
    )

    # Função Objetivo
    custo_operacional = gp.quicksum(
        c_l[pair] * f[pair] for pair in pares_validos
    )
    penalidade_deficit = gp.quicksum(w[pair] for pair in pares_validos)

    model.setObjective(
        alpha_1 * custo_operacional + alpha_2 * penalidade_deficit, GRB.MINIMIZE
    )

    # Restrição R1: Limite da Frota Máxima Simultânea
    for t in faixas:
        linhas_na_faixa_t = [l for (l, f_t) in pares_validos if f_t == t]
        if linhas_na_faixa_t:
            model.addConstr(
                gp.quicksum(n_lt[(l, t)] * f[l, t] for l in linhas_na_faixa_t)
                <= Frota_Max
            )

    # Restrição R2: Cobertura da Demanda + Déficit
    for l, t in pares_validos:
        model.addConstr((f[l, t] * C_l[(l, t)]) + w[l, t] >= d_lt[(l, t)])

    model.optimize()

    # Coleta de Resultados
    if model.Status == GRB.OPTIMAL:
        custo_op_val = custo_operacional.getValue()
        deficit_val = penalidade_deficit.getValue()
        z_val = model.ObjVal

        resultados_globais.append(
            {
                "cenario": nome_cenario,
                "frota_max": Frota_Max,
                "custo_operacional_R$": round(custo_op_val, 2),
                "passageiros_represados": round(deficit_val, 0),
                "valor_obj_Z": round(z_val, 2),
            }
        )

        for l in linhas:
            viagens = sum(f[l, t].X for t in faixas if (l, t) in pares_validos)
            deficit_linha = sum(
                w[l, t].X for t in faixas if (l, t) in pares_validos
            )
            custo_linha = sum(
                f[l, t].X * c_l[(l, t)]
                for t in faixas
                if (l, t) in pares_validos
            )

            detalhamento_linhas.append(
                {
                    "cenario": nome_cenario,
                    "linha": l,
                    "tipologia": (
                        "Articulado"
                        if config["capacidades"][l] == 130
                        else "Padron"
                    ),
                    "viagens_totais": int(viagens),
                    "passageiros_represados": round(deficit_linha, 1),
                    "custo_linha_R$": round(custo_linha, 2),
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