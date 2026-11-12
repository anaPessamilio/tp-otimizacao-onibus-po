"""
Gera as tabelas (.tex) e os números citados no texto (macros LaTeX) a partir
dos CSVs de resultado e do log do Gurobi, para que artigo e slides fiquem
sincronizados com o código. Saída: latex/tabelas/*.tex

Rodar depois de todo o pipeline (executar_tudo.py faz isso na ordem).
"""

import math
import re
from pathlib import Path

import gurobipy as gp
import pandas as pd

import config
from cria_instancia_teste import calibracao_lambda, lambda_efetivo
from modelo import capacidade_corredor, frota_grade_atual

SAIDA = Path("latex/tabelas")
SAIDA.mkdir(parents=True, exist_ok=True)


def br(v, casas=2):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", "{,}").replace("X", ".")


def tex(texto):
    """Escapa texto livre (nomes de cenário etc.) para LaTeX."""
    return (str(texto).replace("\\", r"\textbackslash{}").replace("%", r"\%")
            .replace("$", r"\$").replace("_", r"\_").replace("&", r"\&")
            .replace("#", r"\#"))


def escrever(nome, conteudo):
    (SAIDA / nome).write_text(conteudo, encoding="utf-8")
    print(f"  {nome}")


def tabular(colunas, linhas, total=None, separadores=()):
    out = [r"\begin{tabular}{" + colunas + "}", r"\toprule",
           " & ".join(linhas[0]) + r" \\", r"\midrule"]
    for i, l in enumerate(linhas[1:], start=1):
        if i in separadores:
            out.append(r"\midrule")
        out.append(" & ".join(l) + r" \\")
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
frota_bh = pd.read_csv("dados_pbh/frota_bhtrans.csv").iloc[-1]
lam = pd.read_csv("analise_demanda_lambda.csv")
rob = pd.read_csv("analise_robustez.csv")
val = pd.read_csv("validacao_grade_linhas.csv", dtype={"linha": str})
comp = pd.read_csv("validacao_comparacao.csv")
par = pd.read_csv("fronteira_pareto.csv")
log = Path("log_gurobi.txt").read_text(encoding="utf-8", errors="ignore")

ART, PAD = config.TIPOS_VEICULO["articulado"], config.TIPOS_VEICULO["padron"]
F = frota_grade_atual(inst)
CAP = capacidade_corredor(inst)
LAM = lambda_efetivo()
LAM_CAL, LAM_LINHA = calibracao_lambda()
print("Tabelas geradas:")

# ------------------------------------------------------------------ parâmetros e origem
fmin = {p: math.ceil(60 / v) for p, v in config.INTERVALO_MAX_MIN.items()}
linhas = [["Parâmetro", "Valor", "Origem"],
          [r"Frota disponível $F$",
           f"{F} articulados em operação (exigidos pela grade atual); a frota cadastrada do "
           f"BRT MOVE é de {int(frota_bh.frota_brt_move)} veículos em todos os corredores, "
           f"incluindo reserva técnica", "GTFS; BHTRANS"],
          [r"Capacidade do corredor $\bar{P}$", f"{CAP} partidas/h (maior valor programado hoje)", "GTFS"],
          [r"Tempo de ciclo $n_{lt}$", f"duração da viagem circular $+{round(100 * (config.MARGEM_TERMINAL - 1))}\\%$",
           "GTFS + hipótese"],
          [r"Extensão $D_{lt}$", "geometria do itinerário (ida e volta)", "GTFS"],
          [r"Demanda $d_{lt}$", f"embarques/h atribuídos à linha; $\\lambda={br(LAM, 3)}$ (calibrado)",
           "BHTRANS + hipótese de rateio"],
          [r"Capacidade $C_k$", f"articulado {ART['capacidade']}; Padron {PAD['capacidade']} passageiros", "Hipótese"],
          [r"Custo por km", f"articulado R\\$ {br(ART['custo_km'])}; Padron R\\$ {br(PAD['custo_km'])}", "Hipótese"],
          [r"$f^{\min}_{lt}$", f"intervalo máximo de {config.INTERVALO_MAX_MIN['pico']} min no pico "
           f"($\\ge{fmin['pico']}$/h), {config.INTERVALO_MAX_MIN['dia']} min de dia ($\\ge{fmin['dia']}$/h) e "
           f"{config.INTERVALO_MAX_MIN['noite']} min à noite ($\\ge{fmin['noite']}$/h)", "Hipótese"],
          [r"$f^{\max}_{lt}$", f"{config.F_MAX} partidas/h por linha (intervalo de 2,5 min)", "Hipótese"],
          [r"$\alpha_1$, $\alpha_2$", f"{br(config.ALPHA_1, 0)}; R\\$ {br(config.ALPHA_2, 0)} por passageiro-hora",
           "Hipótese"]]
escrever("parametros_fontes.tex", tabular(r"p{3.4cm}p{8.0cm}p{2.6cm}", linhas))

# ------------------------------------------------------------------ parâmetros por linha
p = inst.groupby("route_short_name").agg(
    km_min=("extensao_km", "min"), km_max=("extensao_km", "max"),
    n_min=("tempo_ciclo_horas", "min"), n_max=("tempo_ciclo_horas", "max"),
    dia=("d_lt", "sum"), pico=("d_lt", "max"), viag=("viagens_gtfs", "sum"))
linhas = [["Linha", r"$D_{lt}$ (km)", r"$n_{lt}$ (h)", "Viagens/dia (GTFS)", "Embarques/dia", "Pico (emb./h)"]]
for l in config.LINHAS_CORREDOR:
    r = p.loc[l]
    linhas.append([l, intervalo(r.km_min, r.km_max, 1), intervalo(r.n_min, r.n_max, 2),
                   br(r.viag, 0), br(r.dia, 0), br(r.pico, 0)])
escrever("parametros_linhas.tex", tabular("lrrrrr", linhas))

# ------------------------------------------------------------------ demanda BHTRANS
linhas = [["Linha", "Registro no ônibus", "Viagens/dia", "Lim. inferior", "Lim. superior", r"$\lambda$ de saturação"]]
for _, r in dem_pbh.iterrows():
    linhas.append([r.linha, br(r.registro_no_onibus, 0), br(r.viagens_gtfs_dia_util, 0),
                   br(r.demanda_dia_util_inferior, 0), br(r.demanda_dia_util_superior, 0),
                   br(LAM_LINHA[r.linha], 2)])
total = ["Total", br(dem_pbh.registro_no_onibus.sum(), 0), br(dem_pbh.viagens_gtfs_dia_util.sum(), 0),
         br(dem_pbh.demanda_dia_util_inferior.sum(), 0), br(dem_pbh.demanda_dia_util_superior.sum(), 0),
         br(LAM_CAL, 2)]
escrever("demanda_bhtrans.tex", tabular("lrrrrr", linhas, total))

# ------------------------------------------------------------------ validação: comparação justa
linhas = [["Modo", "Solução", "Viagens", r"Custo (R\$)", "Não atendidos", "Indicador", r"$Z$ (R\$)"]]
for _, r in comp.iterrows():
    if r.modo == "espera":
        ind, nao = f"{br(r.espera_media_min, 2)} min/pas", f"{br(r.nao_atendidos, 0)} pas$\\cdot$h"
    else:
        ind, nao = f"{br(r.pct_perdidos, 2)}\\% perdidos", f"{br(r.nao_atendidos, 0)} pas"
    linhas.append(["fila" if r.modo == "espera" else "perda", r.solucao, br(r.viagens, 0),
                   br(r["custo_operacional_R$"], 0), nao, ind, br(r.valor_obj_Z, 0)])
escrever("validacao_comparacao.tex", tabular("llrrrrr", linhas, separadores=(3,)))

linhas = [["Linha", "Viagens GTFS", "Viagens ótimo", r"$\sum_t\lceil d_{lt}/C\rceil$", "Emb./viagem GTFS",
           "Perdidos GTFS", "Perdidos ótimo"]]
for _, r in val.iterrows():
    linhas.append([r.linha, br(r.viagens_gtfs, 0), br(r.viagens_otimo, 0), br(r.soma_ceil_d_C, 0),
                   br(r.embarques_por_viagem_gtfs, 1), br(r.perdidos_gtfs, 0), br(r.perdidos_otimo, 0)])
t = val.sum(numeric_only=True)
total = ["Total", br(t.viagens_gtfs, 0), br(t.viagens_otimo, 0), br(t.soma_ceil_d_C, 0), "",
         br(t.perdidos_gtfs, 0), br(t.perdidos_otimo, 0)]
escrever("validacao_linhas.tex", tabular("lrrrrrr", linhas, total))

# ------------------------------------------------------------------ resultados por linha
g = res.groupby("linha").agg(v=("frequencia_otima", "sum"), vg=("viagens_gtfs", "sum"),
                             d=("demanda", "sum"), w=("passageiros_represados", "sum"),
                             c=("custo_operacional_R$", "sum"))
linhas = [["Linha", "Viagens", "Viagens GTFS", "Embarques", r"Espera (pas$\cdot$h)", "Espera (min/pas)", r"Custo (R\$)"]]
for l, r in g.iterrows():
    linhas.append([l, br(r.v, 0), br(r.vg, 0), br(r.d, 0), br(r.w, 0), br(60 * r.w / r.d, 2), br(r.c, 0)])
tot = g.sum()
escrever("resultados_linhas.tex", tabular("lrrrrrr", linhas, [
    r"\textbf{Total}", br(tot.v, 0), br(tot.vg, 0), br(tot.d, 0), br(tot.w, 0),
    br(60 * tot.w / tot.d, 2), br(tot.c, 0)]))

# ------------------------------------------------------------------ cenários (λ calibrado e λ = 1)
linhas = [[r"$\lambda$", "Cenário", "Viagens", "Padron", r"Custo (R\$)", "Espera (min/pas)",
           r"Equilíbrio (R\$/veíc.$\cdot$dia)"]]
seps, anterior = [], None
for i, (_, r) in enumerate(cen.iterrows(), start=1):
    if anterior is not None and r["lambda"] != anterior:
        seps.append(i)
    anterior = r["lambda"]
    eq = "" if pd.isna(r["equilibrio_R$_por_veiculo_dia"]) else br(r["equilibrio_R$_por_veiculo_dia"], 0)
    nome = tex(r.cenario).replace(".", "{,}") if "R$" in r.cenario else tex(r.cenario)
    flag = "" if r.otimo_provado else r"$^\dagger$"
    linhas.append([br(r["lambda"], 3), nome + flag, br(r.viagens, 0), br(r.viagens_padron, 0),
                   br(r["custo_operacional_R$"], 0), br(r.espera_media_min, 2), eq])
escrever("cenarios.tex", tabular("rlrrrrr", linhas, separadores=tuple(seps)))

# ------------------------------------------------------------------ demanda (λ)
linhas = [[r"$\lambda$", "Embarques/dia", "Emb./viagem GTFS", "Viagens", "Espera (min/pas)",
           "Frota necessária", "Faixas c/ corredor no limite", r"Preço-sombra máx. (R\$)"]]
for _, r in lam.iterrows():
    linhas.append([br(r["lambda"], 3), br(r.demanda_dia, 0), br(r.embarques_por_viagem_gtfs, 1),
                   br(r.viagens_otimo, 0), br(r.espera_min_otimo, 2), br(r.frota_necessaria, 1),
                   str(int(r.faixas_corredor_no_limite)), br(r.maior_preco_sombra_frota, 0)])
escrever("demanda_lambda.tex", tabular("rrrrrrrr", linhas))

# ------------------------------------------------------------------ robustez
linhas = [["Caso", "Viagens", r"Custo (R\$)", "Não atendidos", "Indicador"]]
for _, r in rob.iterrows():
    unid = "min/pas" if r.unidade.startswith("min") else r"\% perdidos"
    linhas.append([r.caso, br(r.viagens_otimo, 0), br(r.custo_otimo, 0),
                   br(r.nao_atendidos_otimo, 0), f"{br(r.indicador_otimo, 2)} {unid}"])
escrever("robustez.tex", tabular("lrrrr", linhas))

# ------------------------------------------------------------------ sensibilidade
linhas = [[r"$\alpha_2$ (R\$/pas$\cdot$h)", "Viagens", r"Custo (R\$)", r"Espera (pas$\cdot$h)", "Espera (min/pas)"]]
for _, r in sens.iterrows():
    linhas.append([br(r.alpha_2, 1), br(r.viagens_totais, 0), br(r["custo_operacional_R$"], 0),
                   br(r.passageiros_represados, 0), br(r.espera_media_min, 2)])
escrever("sensibilidade.tex", tabular("rrrrr", linhas))

# ------------------------------------------------------------------ duais
sel = dual[(dual.preco_sombra > 1e-6) | (dual["reducao_Z_PLIM_+1"] > 1e-6)]
linhas = [["Restrição", "Faixa", "Uso (PL)", r"Preço-sombra (R\$)", "Validade do RHS", r"$\Delta Z$ PLIM, +1 (R\$)"]]
for _, r in sel.iterrows():
    ate = r"$\infty$" if pd.isna(r.rhs_valido_ate) else br(r.rhs_valido_ate, 1)
    linhas.append([r.restricao, f"{int(r.faixa_horaria)}h", br(r.uso_PL, 1), br(r.preco_sombra),
                   f"{br(r.rhs_valido_de, 1)} a {ate}", br(r["reducao_Z_PLIM_+1"])])
escrever("duais_frota.tex", tabular("llrrcr", linhas))


# ------------------------------------------------------------------ números
def do_log(padrao, tipo=float, padrao_falta=0):
    m = re.search(padrao, log)
    return tipo(m.group(1)) if m else padrao_falta


def linha_lam(valor):
    return lam.iloc[(lam["lambda"] - valor).abs().argmin()]


c_esp_g = comp[(comp.modo == "espera") & comp.solucao.str.startswith("Grade")].iloc[0]
c_esp_o = comp[(comp.modo == "espera") & comp.solucao.str.startswith("Solução")].iloc[0]
c_per_g = comp[(comp.modo == "perda") & comp.solucao.str.startswith("Grade")].iloc[0]
c_per_o = comp[(comp.modo == "perda") & comp.solucao.str.startswith("Solução")].iloc[0]
lc, l0, l1 = linha_lam(LAM), linha_lam(0.0), linha_lam(1.0)
cen_c = cen[cen["lambda"] == cen["lambda"].min()]
cen_1 = cen[cen["lambda"] == cen["lambda"].max()]


def cen_val(df, inicio, col):
    return df[df.cenario.str.startswith(inicio)].iloc[0][col]


top = dual.sort_values("preco_sombra", ascending=False).iloc[0]
reg = dual_r2["regime"].value_counts()
eps = par[par.metodo == "epsilon-restricao"].sort_values("passageiros_represados")
cm = (eps["custo_operacional_R$"].iloc[0] - eps["custo_operacional_R$"].iloc[1]) / \
     (eps["passageiros_represados"].iloc[1] - eps["passageiros_represados"].iloc[0])
lam_gargalo = lam[lam.maior_preco_sombra_frota > 1e-6]["lambda"].min()

numeros = {
    "lambdaCentral": br(LAM, 3), "lambdaCalibrado": br(LAM_CAL, 3),
    "lambdaGargalo": br(lam_gargalo, 2) if pd.notna(lam_gargalo) else "--",
    "lambdaMinLinha": br(LAM_LINHA.min(), 2), "lambdaMaxLinha": br(LAM_LINHA.max(), 2),
    "Zotimo": br(c_esp_o.valor_obj_Z), "custoTotal": br(c_esp_o["custo_operacional_R$"]),
    "esperaPash": br(c_esp_o.nao_atendidos, 0), "esperaMin": br(c_esp_o.espera_media_min, 2),
    "demandaTotal": br(lc.demanda_dia, 0), "viagensTotal": br(c_esp_o.viagens, 0),
    "viagensGTFS": br(c_esp_g.viagens, 0),
    "variacaoViagens": br(100 * (c_esp_o.viagens / c_esp_g.viagens - 1), 1),
    "custoGTFS": br(c_esp_g["custo_operacional_R$"]),
    "variacaoCusto": br(100 * (c_esp_o["custo_operacional_R$"] / c_esp_g["custo_operacional_R$"] - 1), 1),
    "esperaMinGTFS": br(c_esp_g.espera_media_min, 1), "ZGTFS": br(c_esp_g.valor_obj_Z, 0),
    "perdidosGTFS": br(c_per_g.nao_atendidos, 0), "pctPerdidosGTFS": br(c_per_g.pct_perdidos, 2),
    "perdidosOtimo": br(c_per_o.nao_atendidos, 0), "pctPerdidosOtimo": br(c_per_o.pct_perdidos, 2),
    "custoPerdaGTFS": br(c_per_g["custo_operacional_R$"], 0), "custoPerdaOtimo": br(c_per_o["custo_operacional_R$"], 0),
    "embViagemCentral": br(lc.embarques_por_viagem_gtfs, 1), "embViagemUm": br(l1.embarques_por_viagem_gtfs, 1),
    "esperaLambdaZero": br(l0.espera_min_otimo, 2), "esperaLambdaUm": br(l1.espera_min_otimo, 2),
    "frotaNecZero": br(l0.frota_necessaria, 0), "frotaNecUm": br(l1.frota_necessaria, 0),
    "frotaNecCentral": br(lc.frota_necessaria, 0), "precoLambdaUm": br(l1.maior_preco_sombra_frota, 0),
    "frotaMax": str(F), "frotaMOVE": str(int(frota_bh.frota_brt_move)), "capCorredor": str(CAP),
    "esperaFnoventa": br(cen_val(cen_c, "90 articulados", "espera_media_min"), 2),
    "esperaMaisDezArt": br(cen_val(cen_c, "+10 articulados", "espera_media_min"), 2),
    "esperaPadron": br(cen_val(cen_c, "+15 Padron", "espera_media_min"), 2),
    "custoPadron": br(cen_val(cen_c, "+15 Padron", "custo_operacional_R$"), 0),
    "custoMaisDezArt": br(cen_val(cen_c, "+10 articulados", "custo_operacional_R$"), 0),
    "viagensPadron": br(cen_val(cen_c, "+15 Padron", "viagens_padron"), 0),
    "equilibrioPadron": br(cen_val(cen_c, "+15 Padron", "equilibrio_R$_por_veiculo_dia"), 0),
    "equilibrioMaisDezArt": br(cen_val(cen_c, "+10 articulados", "equilibrio_R$_por_veiculo_dia"), 0),
    "equilibrioPadronIgual": br(cen_val(cen_c, "+15 Padron (R$ 12,50", "equilibrio_R$_por_veiculo_dia"), 0),
    "viagensPadronIgual": br(cen_val(cen_c, "+15 Padron (R$ 12,50", "viagens_padron"), 0),
    "equilibrioMaisDezArtUm": br(cen_val(cen_1, "+10 articulados", "equilibrio_R$_por_veiculo_dia"), 0),
    "esperaBase": br(cen_val(cen_c, "Base", "espera_media_min"), 2),
    "custoBase": br(cen_val(cen_c, "Base", "custo_operacional_R$"), 0),
    "esperaBaseUm": br(cen_val(cen_1, "Base", "espera_media_min"), 2),
    "esperaCorredorUm": br(cen_val(cen_1, "Corredor", "espera_media_min"), 2),
    "esperaMaisDezArtUm": br(cen_val(cen_1, "+10 articulados", "espera_media_min"), 2),
    "Zrelax": br(do_log(r"Root relaxation: objective ([\d.e+]+)")),
    "gapInt": br(lc.gap_integralidade_pct, 2),
    "gapFinal": br(do_log(r"gap ([\d.]+)%"), 4),
    "cortesGomory": str(do_log(r"Gomory: (\d+)", int)), "cortesMIR": str(do_log(r"MIR: (\d+)", int)),
    "nosExplorados": str(do_log(r"Explored (\d+) nodes", int)),
    "iteracoesSimplex": str(do_log(r"\((\d+) simplex iterations\)", int)),
    "tempoSolucao": br(do_log(r"in ([\d.]+) seconds"), 2),
    "presolveLinhas": str(do_log(r"Presolved: (\d+) rows", int)),
    "presolveColunas": str(do_log(r"Presolved: \d+ rows, (\d+) columns", int)),
    "horaPrecoMax": f"{int(top.faixa_horaria)}h", "precoSombraMax": br(top.preco_sombra),
    "deltaPLIMMax": br(top["reducao_Z_PLIM_+1"]),
    "faixasReotimizadas": str(int((dual.restricao.str.startswith("Frota")).sum())),
    "faixasGanhoPLIM": str(int((dual["reducao_Z_PLIM_+1"] > 1e-6).sum())),
    "regimeFolga": str(reg.get("= c/C: frota com folga", 0)),
    "regimeLimite": str(reg.get("> c/C: frota ou corredor no limite", 0)),
    "regimeFila": str(reg.get("fila: passageiros esperando", 0)),
    "regimeSobra": str(reg.get("< c/C: capacidade sobra (padrão de serviço)", 0)),
    "regimeSemDemanda": str(reg.get("sem demanda", 0)),
    "nPares": str(len(dual_r2)),
    "custoMarginalPareto": br(cm),
    "alfaUm": br(config.ALPHA_1, 0), "alfaDois": br(config.ALPHA_2, 0),
    "margemTerminal": br(100 * (config.MARGEM_TERMINAL - 1), 0),
    "nVarInt": str(len(inst) * len(config.TIPOS_VEICULO)), "nVarCont": str(len(inst)),
    "versaoGurobi": ".".join(str(x) for x in gp.gurobi.version()),
    "embarquesEstacoes": br(pd.read_csv("dados_pbh/passageiros_corredor_antonio_carlos.csv", dtype={"codigo": str})
                            .query("codigo.str.startswith('AC') or codigo in "
                                   "['2000','2001','6000','6001','7000','7001']", engine="python")
                            .groupby("codigo")["media_dia_util"].mean().sum(), 0),
    "demandaSup": br(dem_pbh.demanda_dia_util_superior.sum(), 0),
    "demandaInf": br(dem_pbh.demanda_dia_util_inferior.sum(), 0),
    "tempoLimite": str(config.TEMPO_LIMITE_S),
}
nl = re.search(r"Optimize a model with (\d+) rows", log)
numeros["nRestr"] = nl.group(1) if nl else "?"
linhas_tex = ["% Gerado por gera_tabelas_latex.py -- não editar à mão"]
linhas_tex += [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in numeros.items()]
escrever("numeros.tex", "\n".join(linhas_tex) + "\n")

# trecho do log do Gurobi (uma única execução) para o apêndice
trecho = [l for l in log.splitlines()
          if re.search(r"Gurobi Optimizer version|Optimize a model|Variable types|Presolved:|"
                       r"Root relaxation|Cutting planes|Gomory|MIR|Explored|Optimal solution|Best objective", l)]
(SAIDA / "log_gurobi_trecho.txt").write_text("\n".join(trecho) + "\n", encoding="utf-8")
print("  log_gurobi_trecho.txt")
