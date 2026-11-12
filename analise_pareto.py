"""
Fronteira de Pareto custo operacional x passageiros não atendidos pelo método
ε-restrição (Chankong & Haimes; ver Arenales et al., 2007):

    min  custo operacional
    s.a. Σ w_lt <= ε   + todas as restrições do modelo

1. Extremo "serviço": min Σ w (lexicográfico: depois, min custo com Σ w no
   mínimo) -> menor nível de não atendimento possível com a frota disponível.
2. Extremo "custo": min custo sem limite de Σ w (só o padrão de serviço).
3. Pontos intermediários: ε entre os dois extremos.

Também registra as soluções da soma ponderada (α2 variando) para comparação:
elas são pontos da mesma fronteira (as suportadas).
"""

import numpy as np
import pandas as pd
from gurobipy import GRB

from modelo import construir_modelo, tem_solucao

df = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
N_PONTOS = 14


def resolver(objetivo, eps=None, custo_teto=None):
    m = construir_modelo(df, 1.0, 0.0, nome="Pareto")
    model = m["model"]
    if objetivo == "deficit":
        model.setObjective(m["deficit"], GRB.MINIMIZE)
    else:
        model.setObjective(m["custo_operacional"], GRB.MINIMIZE)
    if eps is not None:
        model.addConstr(m["deficit"] <= eps, name="epsilon")
    model.optimize()
    if not tem_solucao(model):
        return None
    return {
        "custo_operacional_R$": m["custo_operacional"].getValue(),
        "passageiros_represados": m["deficit"].getValue(),
        "viagens": sum(v.X for v in m["f"].values()),
    }


demanda = df["d_lt"].sum()

# Extremo de serviço (lexicográfico)
w_min = resolver("deficit")["passageiros_represados"]
ext_servico = resolver("custo", eps=w_min + 1e-6)
# Extremo de custo
ext_custo = resolver("custo")
w_max = ext_custo["passageiros_represados"]

# Faixa relevante: do mínimo possível até 30% da demanda em passageiro-hora
# (espera média de 18 min por passageiro; além disso as filas
# acumuladas perdem sentido prático). Espaçamento geométrico para detalhar a
# região de alto nível de serviço.
w_teto = min(w_max, 0.30 * demanda)
pontos = []
for eps in np.geomspace(w_min, w_teto, N_PONTOS):
    r = resolver("custo", eps=eps + 1e-6)
    if r:
        r["epsilon"] = eps
        pontos.append(r)

fronteira = pd.DataFrame(pontos).drop_duplicates(subset=["custo_operacional_R$"])
fronteira["espera_media_min"] = 60 * fronteira["passageiros_represados"] / demanda
fronteira["metodo"] = "epsilon-restricao"

pond = pd.read_csv("sensibilidade_alpha2.csv")
pond = pond.rename(columns={
                            "viagens_totais": "viagens"})
pond["metodo"] = "soma ponderada (alpha_2 = " + pond["alpha_2"].astype(str) + ")"

saida = pd.concat([
    fronteira[["metodo", "epsilon", "custo_operacional_R$", "passageiros_represados",
               "espera_media_min", "viagens"]],
    pond[["metodo", "alpha_2", "custo_operacional_R$", "passageiros_represados",
          "espera_media_min", "viagens"]],
], ignore_index=True)
saida.to_csv("fronteira_pareto.csv", index=False)

# Custo marginal de reduzir não atendidos ao longo da fronteira
f = fronteira.sort_values("passageiros_represados")
dc = -np.diff(f["custo_operacional_R$"]) / np.diff(f["passageiros_represados"])
print("=== FRONTEIRA DE PARETO (ε-restrição) ===")
print(f"Extremo serviço: {w_min:,.0f} não atendidos, custo R$ {ext_servico['custo_operacional_R$']:,.2f}")
print(f"Extremo custo:   {w_max:,.0f} não atendidos, custo R$ {ext_custo['custo_operacional_R$']:,.2f}")
print(f.round(1).to_string(index=False))
print("\nCusto marginal (R$ por passageiro-hora evitado) entre pontos consecutivos:")
print(np.round(dc, 2))
print("\nArquivo 'fronteira_pareto.csv' gerado.")
