import gurobipy as gp
from gurobipy import GRB
import pandas as pd

# ==========================================
# 1. CARREGAMENTO DA INSTÂNCIA
# ==========================================
df_instancia = pd.read_csv("instancia_modelo_bhtrans.csv")

# Conjuntos (Índices do Modelo)
linhas = df_instancia["route_short_name"].unique().tolist()
faixas = df_instancia["faixa_horaria"].unique().tolist()

# Transformar dataframe em dicionários indexados por (linha, faixa_horaria)
df_indexed = df_instancia.set_index(["route_short_name", "faixa_horaria"])

c_l = df_indexed["c_lt"].to_dict()  # Custo operacional por viagem (R$)
n_lt = df_indexed[
    "tempo_ciclo_horas"
].to_dict()  # Tempo de ciclo (conversão em veículos)
C_l = df_indexed["capacidade_C"].to_dict()  # Capacidade do ônibus (pas/veíc)
d_lt = df_indexed[
    "d_lt"
].to_dict()  # Demanda estimada de passageiros (pas/hora)
f_min = df_indexed["f_min"].to_dict()  # Frequência mínima contratual
f_max = df_indexed["f_max"].to_dict()  # Frequência máxima física

# Parâmetros Globais do Corredor
Frota_Max = 90  # Limite de frota total em circulação no corredor Antônio Carlos

# Pesos da Função Objetivo Bi-Objetivo
alpha_1 = 1.0  # Peso do custo operacional (R$/viagem)
alpha_2 = 25.0  # Penalidade por passageiro deixado no ponto (R$/pas)

# ==========================================
# 2. CONSTRUÇÃO DO MODELO GUROBI
# ==========================================
model = gp.Model("Otimizacao_Frequencia_BHTRANS")
model.Params.OutputFlag = 1

# Conjunto de pares (linha, faixa) VÁLIDOS no dataset
pares_validos = list(c_l.keys())

# Variáveis de Decisão criadas apenas para combinações (l, t) existentes
f = model.addVars(
    pares_validos,
    vtype=GRB.INTEGER,
    lb={pair: f_min[pair] for pair in pares_validos},
    ub={pair: f_max[pair] for pair in pares_validos},
    name="frequencia",
)

w = model.addVars(
    pares_validos,
    vtype=GRB.CONTINUOUS,
    lb=0.0,
    name="passageiros_represados",
)

# ==========================================
# 3. FUNÇÃO OBJETIVO
# ==========================================
custo_operacional = gp.quicksum(c_l[pair] * f[pair] for pair in pares_validos)
penalidade_deficit = gp.quicksum(w[pair] for pair in pares_validos)

model.setObjective(
    alpha_1 * custo_operacional + alpha_2 * penalidade_deficit, GRB.MINIMIZE
)

# ==========================================
# 4. RESTRIÇÕES OPERACIONAIS
# ==========================================

# R1: Limite da Frota Máxima do Corredor por Faixa Horária
for t in faixas:
    # Agrupa apenas as linhas que operam na faixa t
    linhas_na_faixa_t = [l for (l, f_t) in pares_validos if f_t == t]
    if linhas_na_faixa_t:
        model.addConstr(
            gp.quicksum(n_lt[(l, t)] * f[l, t] for l in linhas_na_faixa_t)
            <= Frota_Max,
            name=f"Limite_Frota_t{t}",
        )

# R2: Atendimento da Demanda + Déficit
for l, t in pares_validos:
    model.addConstr(
        (f[l, t] * C_l[(l, t)]) + w[l, t] >= d_lt[(l, t)],
        name=f"Atendimento_l{l}_t{t}",
    )

# ==========================================
# 5. RESOLUÇÃO DO MODELO
# ==========================================
model.optimize()

# ==========================================
# 6. EXTRAÇÃO E EXPORTAÇÃO DOS RESULTADOS
# ==========================================
if model.Status == GRB.OPTIMAL:
    print("\n" + "=" * 50)
    print("SOLUÇÃO ÓTIMA ENCONTRADA COM SUCESSO!")
    print("=" * 50)
    print(f"Valor da Função Objetivo (Z): R$ {model.ObjVal:,.2f}")
    print(
        f"  - Custo Operacional Total:  R$ {custo_operacional.getValue():,.2f}"
    )
    print(
        f"  - Passageiros Não Atendidos: {penalidade_deficit.getValue():,.0f} passageiros"
    )

    # Coletar valores otimizados
    resultados = []

    for l, t in pares_validos:
        f_val = f[l, t].X
        w_val = w[l, t].X
        d_val = d_lt[(l, t)]
        cap_ofertada = f_val * C_l[(l, t)]
        custo_faixa = f_val * c_l[(l, t)]
        veiculos_alocados = f_val * n_lt[(l, t)]

        resultados.append(
            {
                "linha": l,
                "faixa_horaria": t,
                "frequencia_otima": int(f_val),
                "demanda": d_val,
                "capacidade_ofertada": int(cap_ofertada),
                "passageiros_represados": round(w_val, 1),
                "veiculos_simultaneos": round(veiculos_alocados, 2),
                "custo_operacional_R$": round(custo_faixa, 2),
            }
        )

    df_resultados = pd.DataFrame(resultados)
    df_resultados.to_csv("resultados_otimizacao_bhtrans.csv", index=False)

    print("\n--- RESUMO OPERACIONAL POR LINHA (VALORES TOTAIS DIÁRIOS) ---")
    resumo = (
        df_resultados.groupby("linha")
        .agg(
            viagens_totais=("frequencia_otima", "sum"),
            demanda_total=("demanda", "sum"),
            capacidade_ofertada_total=("capacidade_ofertada", "sum"),
            passageiros_represados_totais=("passageiros_represados", "sum"),
            custo_operacional_total=("custo_operacional_R$", "sum"),
        )
        .reset_index()
    )
    print(resumo.to_string(index=False))
    print(
        "\nArquivo detalhado 'resultados_otimizacao_bhtrans.csv' gerado com sucesso!"
    )

else:
    print("\nO modelo não encontrou solução ótima. Status:", model.Status)

