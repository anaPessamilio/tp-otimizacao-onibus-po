"""
Gera as figuras (PDF vetorial + PNG de pré-visualização) do artigo e dos
slides, a partir dos CSVs de resultado. Saída: latex/figuras/

Rodar depois de otimizacao.py, validacao_grade.py, gera_instancias.py,
analise_sensibilidade_alpha.py, analise_pareto.py, analise_demanda.py.
"""

from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from cria_instancia_teste import lambda_efetivo  # noqa: E402
from modelo import frota_grade_atual  # noqa: E402

LAMBDA_C = lambda_efetivo()

SAIDA = Path("latex/figuras")
SAIDA.mkdir(parents=True, exist_ok=True)
for antigo in ["sensibilidade_alpha2", "precos_sombra_frota"]:  # substituídas
    for ext in ("pdf", "png"):
        (SAIDA / f"{antigo}.{ext}").unlink(missing_ok=True)

# Paleta categórica de referência (slots 1-3, validados em conjunto)
AZUL, LARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
TEXTO, TEXTO_2, GRADE, REF = "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": GRADE, "axes.labelcolor": TEXTO_2,
    "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": TEXTO,
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRADE, "grid.linewidth": 0.6,
    "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "legend.frameon": False, "legend.fontsize": 8.5,
    "savefig.bbox": "tight", "pdf.fonttype": 42,
})
HORAS = list(range(24))


def milhar(v, _=None):
    return f"{v:,.0f}".replace(",", ".")


def eixo_horas(ax):
    ax.set_xticks(HORAS[::2])
    ax.set_xticklabels([f"{h}h" for h in HORAS[::2]])
    ax.set_xlabel("Faixa horária")


def virgula(v, _=None):
    """Rótulo numérico com vírgula decimal (padrão brasileiro)."""
    if abs(v - round(v)) < 1e-9 and abs(v) >= 1:
        return milhar(v)
    return f"{v:g}".replace(".", ",")


def salvar(fig, nome):
    for ax in fig.get_axes():
        for eixo in (ax.xaxis, ax.yaxis):
            if eixo.get_scale() == "linear" and not isinstance(
                    eixo.get_major_formatter(), matplotlib.ticker.FuncFormatter) \
                    and not isinstance(eixo.get_major_formatter(), matplotlib.ticker.FixedFormatter):
                eixo.set_major_formatter(matplotlib.ticker.FuncFormatter(virgula))
    fig.savefig(SAIDA / f"{nome}.pdf")
    fig.savefig(SAIDA / f"{nome}.png", dpi=180)
    plt.close(fig)
    print(f"  {nome}.pdf / .png")


inst = pd.read_csv("instancia_modelo_bhtrans.csv", dtype={"route_short_name": str})
res = pd.read_csv("resultados_otimizacao_bhtrans.csv", dtype={"linha": str})
val_h = pd.read_csv("validacao_grade_horas.csv")
F = frota_grade_atual(inst)
CAP = config.TIPOS_VEICULO["articulado"]["capacidade"]
print("Figuras geradas:")

# ------------------------------------------------------------------ 1. frota e espera por hora
fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.3, 4.6), sharex=True,
                             gridspec_kw={"height_ratios": [1.2, 1], "hspace": 0.35})
a1.bar(HORAS, val_h["frota_otimo"], width=0.78, color=AZUL, edgecolor="white", label="Solução ótima")
a1.plot(HORAS, val_h["frota_gtfs"], color=LARANJA, linewidth=2, marker="o", markersize=3.2,
        label="Grade atual (GTFS)")
a1.axhline(F, color=REF, linestyle=(0, (4, 3)), linewidth=1.2)
a1.text(23.6, F + 2, f"Frota disponível F = {F}", ha="right", va="bottom", color=TEXTO_2, fontsize=8)
a1.set_ylim(0, F * 1.2)
a1.set_ylabel("Veículos")
a1.set_title("Ônibus em operação por faixa horária (frota acumulada)")
a1.legend(loc="upper left")
espera = res.groupby("faixa_horaria")["passageiros_represados"].sum().reindex(HORAS, fill_value=0)
a2.bar(HORAS, espera.values, width=0.78, color=AZUL, edgecolor="white")
a2.set_ylabel("Passageiros")
a2.set_title("Passageiros esperando ao fim da faixa (solução ótima)")
a2.yaxis.set_major_formatter(milhar)
eixo_horas(a2)
salvar(fig, "frota_deficit_por_hora")

# ------------------------------------------------------------------ 2. demanda x capacidade por linha
fig, eixos = plt.subplots(len(config.LINHAS_CORREDOR), 1, figsize=(6.3, 7.4), sharex=True,
                          gridspec_kw={"hspace": 0.55})
for ax, l in zip(eixos, config.LINHAS_CORREDOR):
    d = res[res["linha"] == l].set_index("faixa_horaria").reindex(HORAS, fill_value=0)
    ax.step(HORAS, d["capacidade_ofertada"], where="mid", color=AZUL, linewidth=2,
            label="Capacidade ótima")
    ax.step(HORAS, d["viagens_gtfs"] * CAP, where="mid", color=VERDE_AGUA, linewidth=1.6,
            linestyle=(0, (3, 2)), label="Capacidade da grade atual")
    ax.plot(HORAS, d["demanda"], color=LARANJA, linewidth=2, marker="o", markersize=3,
            label="Demanda")
    ax.set_title(f"Linha {l}", pad=3)
    ax.yaxis.set_major_formatter(milhar)
    ax.set_ylim(0, max(d["capacidade_ofertada"].max(), d["demanda"].max(),
                       (d["viagens_gtfs"] * CAP).max()) * 1.2)
eixos[0].legend(loc="upper right", ncol=3, bbox_to_anchor=(1.0, 1.6))
eixo_horas(eixos[-1])
fig.text(0.02, 0.5, "Passageiros por hora", rotation=90, va="center", color=TEXTO_2)
salvar(fig, "demanda_capacidade_linhas")

# ------------------------------------------------------------------ 3. validação: partidas por hora
fig, ax = plt.subplots(figsize=(6.3, 2.8))
larg = 0.38
ax.bar([h - larg / 2 - 0.02 for h in HORAS], val_h["partidas_gtfs"], width=larg,
       color=LARANJA, edgecolor="white", label="Grade atual (GTFS)")
ax.bar([h + larg / 2 + 0.02 for h in HORAS], val_h["partidas_otimo"], width=larg,
       color=AZUL, edgecolor="white", label="Solução ótima")
cap = int(val_h["partidas_gtfs"].max()) if config.CAP_CORREDOR == "grade_atual" else config.CAP_CORREDOR
ax.axhline(cap, color=REF, linestyle=(0, (4, 3)), linewidth=1.2)
ax.text(23.6, cap + 1.5, f"Capacidade do corredor = {cap} partidas/h", ha="right",
        va="bottom", color=TEXTO_2, fontsize=8)
ax.set_ylim(0, cap * 1.25)
ax.set_ylabel("Partidas por hora")
ax.set_title("Partidas por hora no corredor: grade atual x solução ótima")
ax.legend(loc="upper left")
eixo_horas(ax)
salvar(fig, "validacao_partidas")

# ------------------------------------------------------------------ 4. fronteira de Pareto
par = pd.read_csv("fronteira_pareto.csv")
eps = par[par["metodo"] == "epsilon-restricao"].sort_values("espera_media_min")
pond = par[par["metodo"] != "epsilon-restricao"]
pond = pond[pond["espera_media_min"] <= eps["espera_media_min"].max() * 1.05]
fig, ax = plt.subplots(figsize=(6.3, 3.2))
ax.plot(eps["espera_media_min"], eps["custo_operacional_R$"] / 1000, color=AZUL, linewidth=2,
        marker="o", markersize=4, label="Fronteira (ε-restrição)")
ax.scatter(pond["espera_media_min"], pond["custo_operacional_R$"] / 1000, s=42,
           facecolor="white", edgecolor=LARANJA, linewidth=1.8, zorder=3,
           label="Soma ponderada (α₂ variando)")
esc = pond[pond["alpha_2"] == config.ALPHA_2]
if not esc.empty:
    x, y = esc["espera_media_min"].iloc[0], esc["custo_operacional_R$"].iloc[0] / 1000
    ax.annotate(f"α₂ = {config.ALPHA_2:g} (adotado)", (x, y), xytext=(25, -18),
                textcoords="offset points", fontsize=8, color=TEXTO_2,
                arrowprops={"arrowstyle": "-", "color": REF, "lw": 0.8})
ax.set_xlabel("Espera excedente média (min por passageiro)")
ax.set_ylabel("Custo operacional (R$ mil/dia)")
ax.set_title("Fronteira de Pareto: custo x nível de serviço")
ax.legend(loc="upper right")
salvar(fig, "fronteira_pareto")

# ------------------------------------------------------------------ 5. resultados por nível de demanda
lam = pd.read_csv("analise_demanda_lambda.csv")
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(6.6, 2.6), gridspec_kw={"wspace": 0.5})
a1.plot(lam["lambda"], lam["espera_min_otimo"], color=AZUL, linewidth=2, marker="o", markersize=4)
a1.set_title("Espera média (min/pas)")
a2.plot(lam["lambda"], lam["frota_necessaria"], color=AZUL, linewidth=2, marker="o", markersize=4)
a2.axhline(F, color=REF, linestyle=(0, (4, 3)), linewidth=1.1)
a2.text(0, F + 0.8, f"F = {F}", color=TEXTO_2, fontsize=7.5)
a2.set_title("Frota necessária")
a3.plot(lam["lambda"], lam["maior_preco_sombra_frota"] / 1000, color=AZUL, linewidth=2,
        marker="o", markersize=4)
a3.set_title("Preço-sombra máx. (R$ mil)")
for ax in (a1, a2, a3):
    ax.set_xlabel("λ (0 = inferior, 1 = superior)")
    ax.axvline(LAMBDA_C, color=REF, linestyle=":", linewidth=1)
salvar(fig, "demanda_lambda")

# ------------------------------------------------------------------ 6. ilustração de ω
from modelo import peso_ocupacao  # noqa: E402

n_ex, u_ex = 1.4, 0.6
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.4), gridspec_kw={"wspace": 0.35,
                                                                    "width_ratios": [1.4, 1]})
for h in range(4):
    a1.axvspan(h, h + 1, color=GRADE if h % 2 == 0 else "white", alpha=0.6, lw=0)
    a1.text(h + 0.5, 1.32, f"faixa s+{h}" if h else "faixa s", ha="center", fontsize=7.5, color=TEXTO_2)
a1.plot([u_ex, u_ex + n_ex], [0.6, 0.6], color=AZUL, linewidth=6, solid_capstyle="round")
a1.annotate("partida (u)", (u_ex, 0.6), xytext=(u_ex - 0.1, 0.2), fontsize=7.5, color=TEXTO_2,
            arrowprops={"arrowstyle": "-", "color": REF, "lw": 0.8})
a1.annotate("retorno (u + n)", (u_ex + n_ex, 0.6), xytext=(u_ex + n_ex - 0.2, 0.2), fontsize=7.5,
            color=TEXTO_2, arrowprops={"arrowstyle": "-", "color": REF, "lw": 0.8})
a1.set_xlim(0, 4)
a1.set_ylim(0, 1.5)
a1.set_yticks([])
a1.set_xticks([])
a1.grid(False)
a1.set_title(f"Um ônibus, ciclo n = {n_ex:g} h".replace(".", ","))
ks = [0, 1, 2, 3]
pesos_ex = [peso_ocupacao(k, n_ex) for k in ks]
a2.bar(ks, pesos_ex, width=0.6, color=AZUL, edgecolor="white")
for k, p in zip(ks, pesos_ex):
    a2.text(k, p + 0.02, f"{p:.2f}".replace(".", ","), ha="center", fontsize=7.5, color=TEXTO_2)
a2.set_xticks(ks)
a2.set_xticklabels(["s", "s+1", "s+2", "s+3"])
a2.set_ylim(0, 1.05)
a2.set_title(f"ω(k, n)   (soma = {sum(pesos_ex):.2f} = n)".replace(".", ","))
salvar(fig, "omega_ilustracao")

# ------------------------------------------------------------------ 7. cenários
cen = pd.read_csv("comparativo_resumo_cenarios.csv")
cen = cen[cen["lambda"] == cen["lambda"].min()].iloc[::-1]  # λ calibrado
rot = cen["cenario"].str.replace(" (", "\n(", regex=False)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 3.6), sharey=True, gridspec_kw={"wspace": 0.1})
a1.barh(rot, cen["espera_media_min"], height=0.6, color=AZUL, edgecolor="white")
a1.set_title("Espera média (min/passageiro)")
for y, v in enumerate(cen["espera_media_min"]):
    a1.text(v + 0.02, y, f"{v:.2f}".replace(".", ","), va="center", fontsize=7.5, color=TEXTO_2)
a1.set_xlim(0, cen["espera_media_min"].max() * 1.35)
a2.barh(rot, cen["custo_operacional_R$"] / 1000, height=0.6, color=AZUL, edgecolor="white")
a2.set_title("Custo operacional (R$ mil/dia)")
for y, v in enumerate(cen["custo_operacional_R$"] / 1000):
    a2.text(v + 3, y, f"{v:.0f}", va="center", fontsize=7.5, color=TEXTO_2)
a2.set_xlim(0, (cen["custo_operacional_R$"] / 1000).max() * 1.2)
for ax in (a1, a2):
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=7.5)
salvar(fig, "cenarios")
