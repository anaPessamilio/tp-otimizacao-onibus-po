"""
Gera as tabelas (.tex) e os números citados no texto (macros LaTeX) a partir
dos CSVs de resultado, para que artigo e slides fiquem sincronizados com o
código. Saída: latex/tabelas/*.tex

Rodar depois de otimizacao.py, gera_instancias.py,
analise_sensibilidade_alpha.py e analise_dual.py.
"""

from pathlib import Path

import gurobipy as gp
import pandas as pd

from config import (
    ALPHA_1,
    ALPHA_2,
    CUSTO_KM_MEDIO,
    FROTA_MAX,
    LINHAS_CORREDOR,
    MARGEM_TERMINAL,
)
from modelo import construir_modelo, resolver_modelo

SAIDA = Path("latex/tabelas")
SAIDA.mkdir(parents=True, exist_ok=True)


def br(v, casas=2):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", "{,}").replace("X", ".")


def escrever(nome, conteudo):
    (SAIDA / nome).write_text(conteudo, encoding="utf-8")
    print(f"  {nome}")


def tabular(colunas, linhas, total=None):
    """Corpo de tabela booktabs (sem ambiente table)."""
    out = [r"\begin{tabular}{" + colunas + "}", r"\toprule"]
    out.append(" & ".join(linhas[0]) + r" \\")
    out.append(r"\midrule")
    for l in linhas[1:]:
        out.append(" & ".join(l) + r" \\")
    if total:
        out.append(r"\midrule")
        out.append(" & ".join(total) + r" \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out) + "\n"


inst = pd.read_csv("instancia_modelo_bhtrans.csv")
inst["route_short_name"] = inst["route_short_name"].astype(str)
res = pd.read_csv("resultados_otimizacao_bhtrans.csv")
res["linha"] = res["linha"].astype(str)
cen = pd.read_csv("comparativo_resumo_cenarios.csv")
sens = pd.read_csv("sensibilidade_alpha2.csv")
dual = pd.read_csv("analise_dual_frota.csv")
dual_r2 = pd.read_csv("analise_dual_atendimento.csv")
dem_pbh = pd.read_csv("dados_pbh/demanda_diaria_linhas.csv", dtype={"linha": str})
print("Tabelas geradas:")

# ------------------------------------------------------------------ parâmetros por linha
p = inst.groupby("route_short_name").agg(
    km_min=("extensao_km", "min"), km_max=("extensao_km", "max"),
    n_min=("tempo_ciclo_horas", "min"), n_max=("tempo_ciclo_horas", "max"),
    c_min=("c_lt", "min"), c_max=("c_lt", "max"),
    dia=("d_lt", "sum"), pico=("d_lt", "max"),
)


def intervalo(a, b, casas):
    return br(a, casas) if abs(a - b) < 1e-9 else f"{br(a, casas)}--{br(b, casas)}"


linhas = [["Linha", r"$D_{lt}$ (km)", r"$n_{lt}$ (h)", r"$c_{lt}$ (R\$)",
           "Demanda (pas/dia)", "Pico (pas/h)"]]
for l in LINHAS_CORREDOR:
    r = p.loc[l]
    linhas.append([l, intervalo(r.km_min, r.km_max, 1), intervalo(r.n_min, r.n_max, 2),
                   intervalo(r.c_min, r.c_max, 0), br(r.dia, 0), br(r.pico, 0)])
escrever("parametros_linhas.tex", tabular("lrrrrr", linhas))

# ------------------------------------------------------------------ demanda BHTRANS
linhas = [["Linha", "Registro no ônibus", "Viagens/dia (GTFS)",
           "Demanda (lim. sup.)", "Demanda (lim. inf.)"]]
for _, r in dem_pbh.iterrows():
    linhas.append([r.linha, br(r.registro_no_onibus, 0), br(r.viagens_gtfs_dia_util, 0),
                   br(r.demanda_dia_util_superior, 0), br(r.demanda_dia_util_inferior, 0)])
total = ["Total", br(dem_pbh.registro_no_onibus.sum(), 0), br(dem_pbh.viagens_gtfs_dia_util.sum(), 0),
         br(dem_pbh.demanda_dia_util_superior.sum(), 0), br(dem_pbh.demanda_dia_util_inferior.sum(), 0)]
escrever("demanda_bhtrans.tex", tabular("lrrrr", linhas, total))

# ------------------------------------------------------------------ resultados por linha
g = res.groupby("linha").agg(v=("frequencia_otima", "sum"), d=("demanda", "sum"),
                             w=("passageiros_represados", "sum"),
                             c=("custo_operacional_R$", "sum"))
linhas = [["Linha", "Viagens/dia", "Demanda", "Não atendidos", r"\% não atend.", r"Custo (R\$)"]]
for l, r in g.iterrows():
    linhas.append([l, br(r.v, 0), br(r.d, 0), br(r.w, 0), br(100 * r.w / r.d, 1), br(r.c, 0)])
tot = g.sum()
total = [r"\textbf{Total}", br(tot.v, 0), br(tot.d, 0), br(tot.w, 0),
         br(100 * tot.w / tot.d, 1), br(tot.c, 0)]
escrever("resultados_linhas.tex", tabular("lrrrrr", linhas, total))

# ------------------------------------------------------------------ cenários
nomes = {
    "Cenario_R_Relatorio": "R -- 100\\% articulado (custo médio)",
    "Cenario_0_Baseline": "0 -- Baseline (articulado só na 51)",
    "Cenario_1_Frota_Mista_MOVE": "1 -- Frota mista (51, 52, 63)",
    "Cenario_2_100pct_Articulados": "2 -- 100\\% articulado",
    "Cenario_3_Expansao_Frota_110": "3 -- Baseline com frota 110",
}
linhas = [["Cenário", "$F$", r"Custo (R\$)", "Não atendidos", r"$Z$ (R\$)"]]
for _, r in cen.iterrows():
    linhas.append([nomes.get(r.cenario, r.cenario), str(int(r.frota_max)),
                   br(r["custo_operacional_R$"], 0),
                   f"{br(r.passageiros_represados, 0)} ({br(r.pct_nao_atendida, 1)}\\%)",
                   br(r.valor_obj_Z, 0)])
escrever("cenarios.tex", tabular("lrrrr", linhas))

# ------------------------------------------------------------------ sensibilidade
linhas = [[r"$\alpha_2$", "Viagens", r"Custo (R\$)", "Não atendidos", r"\%", "Faixas no limite"]]
for _, r in sens.iterrows():
    linhas.append([br(r.alpha_2, 1), br(r.viagens_totais, 0), br(r["custo_operacional_R$"], 0),
                   br(r.passageiros_represados, 0), br(r.pct_demanda_nao_atendida, 1),
                   str(int(r.faixas_frota_saturada))])
escrever("sensibilidade.tex", tabular("rrrrrr", linhas))

# ------------------------------------------------------------------ duais da frota
sel = dual[(dual["preco_sombra_R$_por_veiculo"] > 1e-6) | (dual["reducao_Z_PLIM_+1_veiculo"] > 1e-6)]
linhas = [["Faixa", "Frota (PL)", r"Preço-sombra (R\$)", "Validade do RHS",
           r"$\Delta Z$ PLIM, +1 veíc. (R\$)"]]
for _, r in sel.iterrows():
    ate = r"$\infty$" if pd.isna(r.rhs_valido_ate) else br(r.rhs_valido_ate, 1)
    linhas.append([f"{int(r.faixa_horaria)}h", br(r.frota_em_operacao_PL, 1),
                   br(r["preco_sombra_R$_por_veiculo"]), f"{br(r.rhs_valido_de, 1)} a {ate}",
                   br(r["reducao_Z_PLIM_+1_veiculo"])])
escrever("duais_frota.tex", tabular("lrrcr", linhas))

# ------------------------------------------------------------------ números citados no texto
dados = inst
m = construir_modelo(dados, FROTA_MAX, ALPHA_1, ALPHA_2, nome="PL")
m["model"].update()
lp = m["model"].relax()
lp.Params.OutputFlag = 0
lp.optimize()
mip = resolver_modelo(dados, FROTA_MAX, ALPHA_1, ALPHA_2, nome="PLIM")
z_mip, z_lp = mip["valor_obj_Z"], lp.ObjVal

razao = dem_pbh.set_index("linha").eval("demanda_dia_util_inferior / demanda_dia_util_superior")
inf = dados.copy()
inf["d_lt"] = (inf["d_lt"] * inf["route_short_name"].map(razao)).round().astype(int)
res_inf = resolver_modelo(inf, FROTA_MAX, ALPHA_1, ALPHA_2, nome="Inferior")

frota_h = res.groupby("faixa_horaria")["veiculos_em_operacao"].sum()
horas_lim = ", ".join(f"{h}h" for h in frota_h[frota_h >= FROTA_MAX - 1].index)
top = dual.sort_values("preco_sombra_R$_por_veiculo", ascending=False).iloc[0]
reg = dual_r2["regime"].value_counts()
gv = gp.gurobi.version()

numeros = {
    "Zotimo": br(z_mip),
    "Zrelax": br(z_lp),
    "gapInt": br(100 * (z_mip - z_lp) / z_mip, 2),
    "custoTotal": br(mip["custo_operacional"]),
    "naoAtendidos": br(mip["passageiros_represados"], 0),
    "demandaTotal": br(mip["demanda_total"], 0),
    "pctNaoAtendidos": br(100 * mip["passageiros_represados"] / mip["demanda_total"], 1),
    "viagensTotal": br(res["frequencia_otima"].sum(), 0),
    "horasFrotaLimite": horas_lim,
    "demandaInf": br(res_inf["demanda_total"], 0),
    "naoAtendidosInf": br(res_inf["passageiros_represados"], 0),
    "pctNaoAtendidosInf": br(100 * res_inf["passageiros_represados"] / res_inf["demanda_total"], 1),
    "custoInf": br(res_inf["custo_operacional"]),
    "frotaMaxInf": br(res_inf["frota_por_faixa"].max(), 0),
    "embarquesEstacoes": br(pd.read_csv("dados_pbh/passageiros_corredor_antonio_carlos.csv", dtype={"codigo": str})
                            .query("codigo.str.startswith('AC') or codigo in ['2000','2001','6000','6001','7000','7001']", engine="python")
                            .groupby("codigo")["media_dia_util"].mean().sum(), 0),
    "demandaSup": br(dem_pbh.demanda_dia_util_superior.sum(), 0),
    "demandaInfDados": br(dem_pbh.demanda_dia_util_inferior.sum(), 0),
    "horaPrecoMax": f"{int(top.faixa_horaria)}h",
    "precoSombraMax": br(top["preco_sombra_R$_por_veiculo"]),
    "regimeFolga": str(reg.get("atendido; frota com folga (= c/C)", 0)),
    "regimeLimite": str(reg.get("atendido; frota no limite (> c/C)", 0)),
    "regimeAlfa": str(reg.get("passageiro excedente não atendido (= α2)", 0)),
    "frotaMax": str(FROTA_MAX),
    "alfaUm": br(ALPHA_1, 0),
    "alfaDois": br(ALPHA_2, 0),
    "custoKm": br(CUSTO_KM_MEDIO),
    "margemTerminal": br(100 * (MARGEM_TERMINAL - 1), 0),
    "nVarInt": str(len(dados)),
    "nRestr": str(24 + len(dados)),
    "versaoGurobi": ".".join(str(x) for x in gv),
}
linhas_tex = ["% Gerado por gera_tabelas_latex.py -- não editar à mão"]
for nome, valor in numeros.items():
    linhas_tex.append(rf"\newcommand{{\{nome}}}{{{valor}}}")
escrever("numeros.tex", "\n".join(linhas_tex) + "\n")
