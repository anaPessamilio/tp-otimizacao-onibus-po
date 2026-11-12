"""
Gera as figuras (PDF vetorial + PNG de pré-visualização) usadas no artigo e
nos slides LaTeX, a partir dos CSVs de resultado do pipeline.

Saída: latex/figuras/*.pdf e *.png
Rodar depois de otimizacao.py, gera_instancias.py,
analise_sensibilidade_alpha.py e analise_dual.py.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from config import FROTA_MAX, LINHAS_CORREDOR  # noqa: E402

SAIDA = Path("latex/figuras")
SAIDA.mkdir(parents=True, exist_ok=True)

# Paleta (slots 1 e 2 da paleta categórica de referência, modo claro)
AZUL = "#2a78d6"
LARANJA = "#eb6834"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"
REFERENCIA = "#8a8984"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": GRADE,
    "axes.labelcolor": TEXTO_2,
    "axes.titlesize": 9.5,
    "axes.titleweight": "bold",
    "axes.titlecolor": TEXTO,
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRADE,
    "grid.linewidth": 0.6,
    "xtick.color": TEXTO_2,
    "ytick.color": TEXTO_2,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})


def milhar(v, _=None):
    return f"{v:,.0f}".replace(",", ".")


def salvar(fig, nome):
    fig.savefig(SAIDA / f"{nome}.pdf")
    fig.savefig(SAIDA / f"{nome}.png", dpi=180)
    plt.close(fig)
    print(f"  {nome}.pdf / .png")


def barras(ax, x, y, cor, largura=0.78, **kw):
    """Barras finas com cantos levemente arredondados no topo (via capstyle)."""
    return ax.bar(x, y, width=largura, color=cor, edgecolor="white",
                  linewidth=1.0, **kw)


res = pd.read_csv("resultados_otimizacao_bhtrans.csv")
res["linha"] = res["linha"].astype(str)
horas = range(24)
print("Figuras geradas:")

# ------------------------------------------------------------------ 1. frota e déficit por hora
frota = res.groupby("faixa_horaria")["veiculos_em_operacao"].sum().reindex(horas, fill_value=0)
deficit = res.groupby("faixa_horaria")["passageiros_represados"].sum().reindex(horas, fill_value=0)

fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.3, 4.4), sharex=True,
                             gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.35})
barras(a1, list(horas), frota.values, AZUL)
a1.axhline(FROTA_MAX, color=REFERENCIA, linestyle=(0, (4, 3)), linewidth=1.2)
a1.text(23.6, FROTA_MAX + 2, f"Frota máxima F = {FROTA_MAX}", ha="right",
        va="bottom", color=TEXTO_2, fontsize=8)
a1.set_ylim(0, FROTA_MAX * 1.18)
a1.set_ylabel("Veículos")
a1.set_title("Ônibus em operação por faixa horária (frota acumulada)")

barras(a2, list(horas), deficit.values, LARANJA)
a2.set_ylabel("Passageiros")
a2.set_title("Passageiros não atendidos por faixa horária")
a2.yaxis.set_major_formatter(milhar)
for h in deficit.sort_values(ascending=False).head(2).index:
    a2.annotate(milhar(deficit[h]), (h, deficit[h]), xytext=(0, 3),
                textcoords="offset points", ha="center", fontsize=7.5, color=TEXTO_2)
a2.set_xticks(list(horas)[::2])
a2.set_xticklabels([f"{h}h" for h in list(horas)[::2]])
a2.set_xlabel("Faixa horária")
salvar(fig, "frota_deficit_por_hora")

# ------------------------------------------------------------------ 2. demanda x capacidade por linha
fig, eixos = plt.subplots(len(LINHAS_CORREDOR), 1, figsize=(6.3, 7.2), sharex=True,
                          gridspec_kw={"hspace": 0.55})
for ax, l in zip(eixos, LINHAS_CORREDOR):
    d = res[res["linha"] == l].set_index("faixa_horaria").reindex(horas, fill_value=0)
    ax.step(list(horas), d["capacidade_ofertada"], where="mid", color=AZUL,
            linewidth=2, label="Capacidade ofertada (C·f)")
    ax.plot(list(horas), d["demanda"], color=LARANJA, linewidth=2,
            marker="o", markersize=3.2, label="Demanda d")
    ax.set_title(f"Linha {l}", pad=3)
    ax.yaxis.set_major_formatter(milhar)
    ax.set_ylim(0, max(d["capacidade_ofertada"].max(), d["demanda"].max()) * 1.2)
eixos[0].legend(loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.55))
eixos[-1].set_xticks(list(horas)[::2])
eixos[-1].set_xticklabels([f"{h}h" for h in list(horas)[::2]])
eixos[-1].set_xlabel("Faixa horária")
fig.text(0.02, 0.5, "Passageiros por hora", rotation=90, va="center", color=TEXTO_2)
salvar(fig, "demanda_capacidade_linhas")

# ------------------------------------------------------------------ 3. sensibilidade de alpha_2
sens = pd.read_csv("sensibilidade_alpha2.csv")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.7), gridspec_kw={"wspace": 0.38})
a1.plot(sens["alpha_2"], sens["pct_demanda_nao_atendida"], color=AZUL, linewidth=2,
        marker="o", markersize=4)
a1.set_xscale("log")
a1.set_title("Demanda não atendida")
a1.set_ylabel("% da demanda")
a1.set_xlabel("α₂ (R$ por passageiro, escala log)")
a2.plot(sens["alpha_2"], sens["custo_operacional_R$"] / 1000, color=AZUL, linewidth=2,
        marker="o", markersize=4)
a2.set_xscale("log")
a2.set_title("Custo operacional")
a2.set_ylabel("R$ mil por dia")
a2.set_xlabel("α₂ (R$ por passageiro, escala log)")
for ax in (a1, a2):
    ax.axvline(25, color=REFERENCIA, linestyle=(0, (4, 3)), linewidth=1)
    ax.set_xticks([0.5, 1, 2, 5, 10, 25, 50])
    ax.set_xticklabels(["0,5", "1", "2", "5", "10", "25", "50"])
a1.text(25, a1.get_ylim()[1] * 0.92, " adotado", color=TEXTO_2, fontsize=7.5)
salvar(fig, "sensibilidade_alpha2")

# ------------------------------------------------------------------ 4. preços-sombra da frota
dual = pd.read_csv("analise_dual_frota.csv")
dual = dual[(dual["faixa_horaria"] >= 5) & (dual["faixa_horaria"] <= 20)]
x = dual["faixa_horaria"].values
fig, ax = plt.subplots(figsize=(6.3, 2.8))
larg = 0.38
barras(ax, x - larg / 2 - 0.02, dual["preco_sombra_R$_por_veiculo"], AZUL, largura=larg,
       label="Preço-sombra na relaxação linear (dual de R1)")
barras(ax, x + larg / 2 + 0.02, dual["reducao_Z_PLIM_+1_veiculo"], LARANJA, largura=larg,
       label="Redução real de Z no PLIM com +1 veículo")
ax.set_xticks(x)
ax.set_xticklabels([f"{h}h" for h in x])
ax.yaxis.set_major_formatter(milhar)
ax.set_ylabel("R$ por veículo")
ax.set_xlabel("Faixa horária")
ax.set_title("Valor marginal de um veículo adicional em cada faixa")
ax.legend(loc="upper left")
ax.set_ylim(0, dual[["preco_sombra_R$_por_veiculo", "reducao_Z_PLIM_+1_veiculo"]].max().max() * 1.3)
salvar(fig, "precos_sombra_frota")

# ------------------------------------------------------------------ 5. cenários
cen = pd.read_csv("comparativo_resumo_cenarios.csv")
nomes = {
    "Cenario_R_Relatorio": "R: 100% articulado\n(custo médio)",
    "Cenario_0_Baseline": "0: Baseline\n(articulado só na 51)",
    "Cenario_1_Frota_Mista_MOVE": "1: Frota mista\n(51, 52, 63 articulados)",
    "Cenario_2_100pct_Articulados": "2: 100% articulado",
    "Cenario_3_Expansao_Frota_110": "3: Baseline com\nfrota 110",
}
cen["rotulo"] = cen["cenario"].map(nomes)
cen = cen.iloc[::-1]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 3.0), sharey=True, gridspec_kw={"wspace": 0.12})
a1.barh(cen["rotulo"], cen["pct_nao_atendida"], height=0.6, color=AZUL, edgecolor="white")
a1.set_title("Demanda não atendida (%)")
for y, v in enumerate(cen["pct_nao_atendida"]):
    a1.text(v + 0.3, y, f"{v:.1f}%".replace(".", ","), va="center", fontsize=7.5, color=TEXTO_2)
a1.set_xlim(0, cen["pct_nao_atendida"].max() * 1.25)
a2.barh(cen["rotulo"], cen["custo_operacional_R$"] / 1000, height=0.6, color=AZUL, edgecolor="white")
a2.set_title("Custo operacional (R$ mil/dia)")
for y, v in enumerate(cen["custo_operacional_R$"] / 1000):
    a2.text(v + 4, y, f"{v:.0f}", va="center", fontsize=7.5, color=TEXTO_2)
a2.set_xlim(0, (cen["custo_operacional_R$"] / 1000).max() * 1.2)
for ax in (a1, a2):
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
salvar(fig, "cenarios")
