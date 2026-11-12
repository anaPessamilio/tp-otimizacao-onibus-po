"""
Gera as tabelas (.tex) e os números citados no texto (macros LaTeX) a partir
dos CSVs de resultado e do log do Gurobi, para que artigo e slides fiquem
sincronizados com o código. Saída: latex/tabelas/*.tex

Rodar depois de todo o pipeline de análise (ver README/ordem no artigo).
"""

import math
import re
from pathlib import Path

import gurobipy as gp
import pandas as pd

import config
from modelo import capacidade_corredor, frota_grade_atual

SAIDA = Path("latex/tabelas")
SAIDA.mkdir(parents=True, exist_ok=True)


def br(v, casas=2):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", "{,}").replace("X", ".")


def escrever(nome, conteudo):
    (SAIDA / nome).write_text(conteudo, encoding="utf-8")
    print(f"  {nome}")


def tabular(colunas, linhas, total=None):
    out = [r"\begin{tabular}{" + colunas + "}", r"\toprule",
           " & ".join(linhas[0]) + r" \\", r"\midrule"]
    out += [" & ".join(l) + r" \\" for l in linhas[1:]]
    if total:
        out += [r"\midrule", " & ".join(total) + r" \\"]
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out) + "\n"


def intervalo(a, b, casas):
    return br(a, casas) if abs(a - b) < 1e-9 else f"{br(a, casas)}--{br(b, casas)}"


inst = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
res = pd.read_csv("resultados_otimizacao_bhtrans.csv", dtype={"linha": str})
cen = pd.read_csv("comparativo_resumo_cenarios.csv")
sens = pd.read_csv("sensibilidade_alpha2.csv")
dual = pd.read_csv("analise_dual_frota.csv")
dual_r2 = pd.read_csv("analise_dual_atendimento.csv")
dem_pbh = pd.read_csv("dados_pbh/demanda_diaria_linhas.csv", dtype={"linha": str})
lam = pd.read_csv("analise_demanda_lambda.csv")
rob = pd.read_csv("analise_robustez.csv")
val = pd.read_csv("validacao_grade_linhas.csv", dtype={"linha": str})
par = pd.read_csv("fronteira_pareto.csv")
log = Path("log_gurobi.txt").read_text(encoding="utf-8", errors="ignore")

ART = config.TIPOS_VEICULO["articulado"]
PAD = config.TIPOS_VEICULO["padron"]
F = frota_grade_atual(inst)
CAP = capacidade_corredor(inst)
print("Tabelas geradas:")

# ------------------------------------------------------------------ parâmetros e origem
fmin = {p: math.ceil(60 / v) for p, v in config.INTERVALO_MAX_MIN.items()}
linhas = [["Parâmetro", "Valor", "Origem"],
          [r"Frota disponível $F$", f"{F} articulados (frota em operação exigida pela grade atual)", "GTFS"],
          [r"Capacidade do corredor", f"{CAP} partidas/h (maior valor programado hoje)", "GTFS"],
          [r"Tempo de ciclo $n_{lt}$", f"duração da viagem circular $+{round(100 * (config.MARGEM_TERMINAL - 1))}\\%$", r"GTFS + hipótese"],
          [r"Extensão $D_{lt}$", "geometria do itinerário (ida e volta)", "GTFS"],
          [r"Demanda $d_{lt}$", f"embarques por dia útil, $\\lambda={br(config.LAMBDA_DEMANDA, 2)}$", "BHTRANS + hipótese de rateio"],
          [r"Capacidade $C_k$", f"articulado {ART['capacidade']}; Padron {PAD['capacidade']} passageiros", "Hipótese"],
          [r"Custo por km", f"articulado R\\$ {br(ART['custo_km'])}; Padron R\\$ {br(PAD['custo_km'])}", "Hipótese"],
          [r"$f^{\min}_{lt}$", f"intervalo máx. {config.INTERVALO_MAX_MIN['pico']} min no pico "
           f"($f\\ge{fmin['pico']}$), {config.INTERVALO_MAX_MIN['dia']} min de dia ($\\ge{fmin['dia']}$), "
           f"{config.INTERVALO_MAX_MIN['noite']} min à noite ($\\ge{fmin['noite']}$)", "Hipótese (padrão de serviço)"],
          [r"$f^{\max}_{lt}$", f"{config.F_MAX} partidas/h por linha (intervalo de 2,5 min)", "Hipótese"],
          [r"$\alpha_1$, $\alpha_2$", f"{br(config.ALPHA_1, 0)} e R\\$ {br(config.ALPHA_2, 0)} por passageiro-hora", "Hipótese (ver fronteira)"]]
escrever("parametros_fontes.tex", tabular("p{3.2cm}p{7.6cm}p{3.2cm}", linhas))

# ------------------------------------------------------------------ parâmetros por linha
p = inst.groupby("route_short_name").agg(
    km_min=("extensao_km", "min"), km_max=("extensao_km", "max"),
    n_min=("tempo_ciclo_horas", "min"), n_max=("tempo_ciclo_horas", "max"),
    dia=("d_lt", "sum"), pico=("d_lt", "max"), viag=("viagens_gtfs", "sum"))
linhas = [["Linha", r"$D_{lt}$ (km)", r"$n_{lt}$ (h)", r"Viagens/dia (GTFS)", "Demanda (pas/dia)", "Pico (pas/h)"]]
for l in config.LINHAS_CORREDOR:
    r = p.loc[l]
    linhas.append([l, intervalo(r.km_min, r.km_max, 1), intervalo(r.n_min, r.n_max, 2),
                   br(r.viag, 0), br(r.dia, 0), br(r.pico, 0)])
escrever("parametros_linhas.tex", tabular("lrrrrr", linhas))

# ------------------------------------------------------------------ demanda BHTRANS
linhas = [["Linha", "Registro no ônibus", "Viagens/dia (GTFS)", "Lim. inferior", "Lim. superior"]]
for _, r in dem_pbh.iterrows():
    linhas.append([r.linha, br(r.registro_no_onibus, 0), br(r.viagens_gtfs_dia_util, 0),
                   br(r.demanda_dia_util_inferior, 0), br(r.demanda_dia_util_superior, 0)])
total = ["Total", br(dem_pbh.registro_no_onibus.sum(), 0), br(dem_pbh.viagens_gtfs_dia_util.sum(), 0),
         br(dem_pbh.demanda_dia_util_inferior.sum(), 0), br(dem_pbh.demanda_dia_util_superior.sum(), 0)]
escrever("demanda_bhtrans.tex", tabular("lrrrr", linhas, total))

# ------------------------------------------------------------------ validação por linha
linhas = [["Linha", "Viagens GTFS", "Viagens ótimo", r"Variação", r"Não atend. GTFS$^\ast$", "Não atend. ótimo"]]
for _, r in val.iterrows():
    linhas.append([r.linha, br(r.viagens_gtfs, 0), br(r.viagens_otimo, 0),
                   f"{'+' if r.variacao_viagens_pct >= 0 else ''}{br(r.variacao_viagens_pct, 1)}\\%",
                   br(r.nao_atendidos_gtfs_perda, 0), br(r.nao_atendidos_otimo, 0)])
t = val.sum(numeric_only=True)
total = ["Total", br(t.viagens_gtfs, 0), br(t.viagens_otimo, 0),
         f"+{br(100 * (t.viagens_otimo / t.viagens_gtfs - 1), 1)}\\%",
         br(t.nao_atendidos_gtfs_perda, 0), br(t.nao_atendidos_otimo, 0)]
escrever("validacao_linhas.tex", tabular("lrrrrr", linhas, total))

# ------------------------------------------------------------------ resultados por linha
g = res.groupby("linha").agg(v=("frequencia_otima", "sum"), d=("demanda", "sum"),
                             w=("passageiros_represados", "sum"), c=("custo_operacional_R$", "sum"))
linhas = [["Linha", "Viagens/dia", "Demanda", "Não atendidos", r"\%", r"Custo (R\$)"]]
for l, r in g.iterrows():
    linhas.append([l, br(r.v, 0), br(r.d, 0), br(r.w, 0), br(100 * r.w / r.d, 1), br(r.c, 0)])
tot = g.sum()
escrever("resultados_linhas.tex", tabular("lrrrrr", linhas, [
    r"\textbf{Total}", br(tot.v, 0), br(tot.d, 0), br(tot.w, 0), br(100 * tot.w / tot.d, 1), br(tot.c, 0)]))

# ------------------------------------------------------------------ cenários
linhas = [["Cenário", "Viagens", "Padron", r"Custo (R\$)", "Não atend.", r"\%"]]
for _, r in cen.iterrows():
    linhas.append([r.cenario.replace("%", r"\%"), br(r.viagens, 0), br(r.viagens_padron, 0),
                   br(r["custo_operacional_R$"], 0), br(r.passageiros_represados, 0),
                   br(r.pct_nao_atendida, 2)])
escrever("cenarios.tex", tabular("lrrrrr", linhas))

# ------------------------------------------------------------------ demanda (λ)
linhas = [[r"$\lambda$", "Demanda/dia", "Emb./viagem GTFS", "Viagens ótimo", r"\% não atend.",
           "Frota necessária", r"Preço-sombra máx. (R\$)"]]
for _, r in lam.iterrows():
    linhas.append([br(r["lambda"], 2), br(r.demanda_dia, 0), br(r.embarques_por_viagem_gtfs, 1),
                   br(r.viagens_otimo, 0), br(r.pct_otimo, 1), br(r.frota_necessaria, 1),
                   br(r.maior_preco_sombra_frota, 0)])
escrever("demanda_lambda.tex", tabular("rrrrrrr", linhas))

# ------------------------------------------------------------------ robustez
linhas = [["Caso", "Viagens", r"Custo (R\$)", "Não atend.", r"\%"]]
for _, r in rob.iterrows():
    linhas.append([r.caso, br(r.viagens_otimo, 0), br(r.custo_otimo, 0),
                   br(r.nao_atendidos_otimo, 0), br(r.pct_otimo, 2)])
escrever("robustez.tex", tabular("lrrrr", linhas))

# ------------------------------------------------------------------ sensibilidade
linhas = [[r"$\alpha_2$", "Viagens", r"Custo (R\$)", "Não atendidos", r"\%"]]
for _, r in sens.iterrows():
    linhas.append([br(r.alpha_2, 1), br(r.viagens_totais, 0), br(r["custo_operacional_R$"], 0),
                   br(r.passageiros_represados, 0), br(r.pct_demanda_nao_atendida, 2)])
escrever("sensibilidade.tex", tabular("rrrrr", linhas))

# ------------------------------------------------------------------ duais
sel = dual[(dual.preco_sombra > 1e-6) | (dual["reducao_Z_PLIM_+1"] > 1e-6)]
linhas = [["Restrição", "Faixa", "Uso (PL)", r"Preço-sombra (R\$)", "Validade do RHS",
           r"$\Delta Z$ PLIM, +1 (R\$)"]]
for _, r in sel.iterrows():
    ate = r"$\infty$" if pd.isna(r.rhs_valido_ate) else br(r.rhs_valido_ate, 1)
    linhas.append([r.restricao, f"{int(r.faixa_horaria)}h", br(r.uso_PL, 1), br(r.preco_sombra),
                   f"{br(r.rhs_valido_de, 1)} a {ate}", br(r["reducao_Z_PLIM_+1"])])
escrever("duais_frota.tex", tabular("llrrcr", linhas))

# ------------------------------------------------------------------ números
def do_log(padrao, tipo=float, padrao_falta=0):
    m = re.search(padrao, log)
    return tipo(m.group(1)) if m else padrao_falta


tot_val = val.sum(numeric_only=True)
base = cen.iloc[0]
lam_c = lam[lam["lambda"] == config.LAMBDA_DEMANDA].iloc[0]
lam_0, lam_1 = lam[lam["lambda"] == 0].iloc[0], lam[lam["lambda"] == 1].iloc[0]
pad15 = cen[cen.cenario.str.startswith("+15 Padron")].iloc[0]
f90 = cen[cen.cenario.str.startswith("Frota de 90")].iloc[0]
top = dual.sort_values("preco_sombra", ascending=False).iloc[0]
reg = dual_r2["regime"].value_counts()
eps = par[par.metodo == "epsilon-restricao"].sort_values("passageiros_represados")
cm = (eps["custo_operacional_R$"].iloc[0] - eps["custo_operacional_R$"].iloc[1]) / \
     (eps["passageiros_represados"].iloc[1] - eps["passageiros_represados"].iloc[0])

numeros = {
    "Zotimo": br(lam_c.Z_otimo),
    "custoTotal": br(lam_c.custo_otimo),
    "naoAtendidos": br(lam_c.nao_atendidos_otimo, 0),
    "pctNaoAtendidos": br(lam_c.pct_otimo, 1),
    "demandaTotal": br(lam_c.demanda_dia, 0),
    "viagensTotal": br(lam_c.viagens_otimo, 0),
    "viagensGTFS": br(lam_c.viagens_gtfs, 0),
    "variacaoViagens": br(100 * (lam_c.viagens_otimo / lam_c.viagens_gtfs - 1), 1),
    "custoGTFS": br(lam_c.custo_gtfs),
    "naoAtendidosGTFSperda": br(tot_val.nao_atendidos_gtfs_perda, 0),
    "pctGTFSperda": br(100 * tot_val.nao_atendidos_gtfs_perda / tot_val.demanda, 1),
    "lambdaCentral": br(config.LAMBDA_DEMANDA, 1),
    "pctLambdaZero": br(lam_0.pct_otimo, 1),
    "pctLambdaUm": br(lam_1.pct_otimo, 1),
    "frotaNecZero": br(lam_0.frota_necessaria, 0),
    "frotaNecUm": br(lam_1.frota_necessaria, 0),
    "frotaNecCentral": br(lam_c.frota_necessaria, 0),
    "precoLambdaUm": br(lam_1.maior_preco_sombra_frota, 0),
    "embViagemCentral": br(lam_c.embarques_por_viagem_gtfs, 1),
    "embViagemUm": br(lam_1.embarques_por_viagem_gtfs, 1),
    "frotaMax": str(F),
    "capCorredor": str(CAP),
    "pctFnoventa": br(f90.pct_nao_atendida, 2),
    "pctPadron": br(pad15.pct_nao_atendida, 2),
    "custoPadron": br(pad15["custo_operacional_R$"], 0),
    "viagensPadron": br(pad15.viagens_padron, 0),
    "pctBase": br(base.pct_nao_atendida, 2),
    "custoBase": br(base["custo_operacional_R$"], 0),
    "Zrelax": br(do_log(r"Root relaxation: objective ([\d.e+]+)")),
    "gapInt": br(lam_c.gap_integralidade_pct, 2),
    "gapFinal": br(100 * do_log(r"gap ([\d.]+)%") / 100, 4),
    "cortesGomory": str(do_log(r"Gomory: (\d+)", int)),
    "cortesMIR": str(do_log(r"MIR: (\d+)", int)),
    "nosExplorados": str(do_log(r"Explored (\d+) nodes", int)),
    "iteracoesSimplex": str(do_log(r"\((\d+) simplex iterations\)", int)),
    "tempoSolucao": br(do_log(r"in ([\d.]+) seconds"), 2),
    "horaPrecoMax": f"{int(top.faixa_horaria)}h",
    "precoSombraMax": br(top.preco_sombra),
    "deltaPLIMMax": br(top["reducao_Z_PLIM_+1"]),
    "regimeFolga": str(reg.get("= c/C: frota com folga", 0)),
    "regimeLimite": str(reg.get("> c/C: frota ou corredor no limite", 0)),
    "regimeFila": str(reg.get("fila: passageiros esperando", 0)),
    "regimeSobra": str(reg.get("< c/C: capacidade sobra (padrão de serviço)", 0)),
    "custoMarginalPareto": br(cm),
    "alfaUm": br(config.ALPHA_1, 0),
    "alfaDois": br(config.ALPHA_2, 0),
    "margemTerminal": br(100 * (config.MARGEM_TERMINAL - 1), 0),
    "nVarInt": str(len(inst) * len(config.TIPOS_VEICULO)),
    "nVarCont": str(len(inst)),
    "versaoGurobi": ".".join(str(x) for x in gp.gurobi.version()),
    "embarquesEstacoes": br(pd.read_csv("dados_pbh/passageiros_corredor_antonio_carlos.csv",
                                        dtype={"codigo": str})
                            .query("codigo.str.startswith('AC') or codigo in "
                                   "['2000','2001','6000','6001','7000','7001']", engine="python")
                            .groupby("codigo")["media_dia_util"].mean().sum(), 0),
    "demandaSup": br(dem_pbh.demanda_dia_util_superior.sum(), 0),
    "demandaInf": br(dem_pbh.demanda_dia_util_inferior.sum(), 0),
}
nl = re.search(r"Optimize a model with (\d+) rows", log)
numeros["nRestr"] = nl.group(1) if nl else "?"
linhas_tex = ["% Gerado por gera_tabelas_latex.py -- não editar à mão"]
linhas_tex += [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in numeros.items()]
escrever("numeros.tex", "\n".join(linhas_tex) + "\n")

# trecho do log do Gurobi para o apêndice do artigo
trecho = [l for l in log.splitlines()
          if re.search(r"Gurobi Optimizer version|Optimize a model|Variable types|Presolved:|"
                       r"Root relaxation|Cutting planes|Gomory|MIR|Explored|Optimal solution|Best objective", l)]
(SAIDA / "log_gurobi_trecho.txt").write_text("\n".join(trecho) + "\n", encoding="utf-8")
print("  log_gurobi_trecho.txt")
