"""
Gera o relatório técnico revisado (PDF) a partir dos resultados do pipeline.
Rodar depois de otimizacao.py, gera_instancias.py e analise_sensibilidade_alpha.py.
"""

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import (
    ALPHA_1,
    ALPHA_2,
    CAP_ARTICULADO,
    CUSTO_KM_ARTICULADO,
    CUSTO_KM_MEDIO,
    CUSTO_KM_PADRON,
    DEMANDA_PBH_LIMITE,
    F_MAX,
    F_MIN,
    FATOR_TRECHO_CRITICO,
    FROTA_MAX,
    LINHAS_CORREDOR,
    MARGEM_TERMINAL,
)
from modelo import construir_modelo, resolver_modelo

ARQUIVO_SAIDA = "Relatorio Otimizacao Frequencia BHTRANS v2.pdf"

# ---------------------------------------------------------------- fontes
FONTES = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Arial", FONTES + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTES + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONTES + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Consolas", FONTES + "consola.ttf"))
pdfmetrics.registerFontFamily(
    "Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic"
)

# ---------------------------------------------------------------- cores
NAVY = colors.HexColor("#0F172A")
AZUL = colors.HexColor("#2563EB")
AZUL_ESCURO = colors.HexColor("#1E3A8A")
CINZA_TXT = colors.HexColor("#334155")
CINZA_CLARO = colors.HexColor("#64748B")
BORDA = colors.HexColor("#CBD5E1")
FUNDO_TAB = colors.HexColor("#F1F5F9")
FUNDO_FO = colors.HexColor("#EFF6FF")
AMBAR_FUNDO = colors.HexColor("#FEF9C3")
AMBAR_BORDA = colors.HexColor("#F59E0B")
AMBAR_TXT = colors.HexColor("#78350F")

# ---------------------------------------------------------------- estilos
base = ParagraphStyle("base", fontName="Arial", fontSize=9.5, leading=13.5,
                      textColor=CINZA_TXT, alignment=TA_JUSTIFY)
s_h1 = ParagraphStyle("h1", parent=base, fontName="Arial-Bold", fontSize=12.5,
                      leading=16, textColor=NAVY, spaceBefore=10, spaceAfter=2,
                      alignment=0)
s_h2 = ParagraphStyle("h2", parent=base, fontName="Arial-Bold", fontSize=10,
                      leading=13, textColor=AZUL_ESCURO, spaceBefore=6,
                      spaceAfter=3, alignment=0)
s_cel = ParagraphStyle("cel", parent=base, fontSize=8.3, leading=10.8, alignment=0)
s_cel_b = ParagraphStyle("celb", parent=s_cel, fontName="Arial-Bold", textColor=NAVY)
s_cel_c = ParagraphStyle("celc", parent=s_cel, alignment=TA_CENTER)
s_eq = ParagraphStyle("eq", parent=base, fontSize=10, leading=17,
                      alignment=TA_CENTER, textColor=NAVY)
s_eq_tit = ParagraphStyle("eqt", parent=s_eq, fontName="Arial-Bold",
                          textColor=AZUL_ESCURO, fontSize=10)
s_nota = ParagraphStyle("nota", parent=base, fontSize=8.5, leading=11.5,
                        textColor=AMBAR_TXT)
s_ref = ParagraphStyle("ref", parent=base, fontSize=8.6, leading=11.8,
                       leftIndent=10, firstLineIndent=-10, spaceAfter=3,
                       alignment=0)
s_cod = ParagraphStyle("cod", fontName="Consolas", fontSize=7.6, leading=9.8,
                       textColor=colors.HexColor("#E2E8F0"))
s_legenda = ParagraphStyle("leg", parent=base, fontSize=7.8, leading=10,
                           textColor=CINZA_CLARO, alignment=0)


def P(txt, st=base):
    return Paragraph(txt, st)


def br(v, casas=2):
    """Formata número no padrão brasileiro."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def secao(titulo):
    linha = Table([[""]], colWidths=[174 * mm], rowHeights=[1.2])
    linha.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 1.2, BORDA)]))
    return [P(titulo, s_h1), linha, Spacer(1, 5)]


def tabela(dados, larguras, cabecalho=True, alinhar_dir=None, negrito_ultima=False):
    linhas = []
    for i, linha in enumerate(dados):
        st = s_cel_b if (cabecalho and i == 0) else s_cel
        linhas.append([c if not isinstance(c, str) else P(c, st) for c in linha])
    t = Table(linhas, colWidths=[w * mm for w in larguras], repeatRows=1 if cabecalho else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.5, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if cabecalho:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), FUNDO_TAB))
    if negrito_ultima:
        estilo.append(("BACKGROUND", (0, -1), (-1, -1), FUNDO_FO))
    t.setStyle(TableStyle(estilo))
    return t


def caixa(conteudo, fundo, borda, largura=174):
    t = Table([[conteudo]], colWidths=[largura * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo),
        ("LINEBEFORE", (0, 0), (0, -1), 3, borda),
        ("BOX", (0, 0), (-1, -1), 0.5, borda),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


# ---------------------------------------------------------------- rodapé com "Página X de Y"
class CanvasNumerado(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setStrokeColor(BORDA)
            self.setLineWidth(0.5)
            self.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
            self.setFont("Arial", 7.8)
            self.setFillColor(CINZA_CLARO)
            self.drawString(18 * mm, 10.5 * mm,
                            "Otimização de Frequência de Linhas de Ônibus - BHTRANS / UFMG")
            self.drawRightString(192 * mm, 10.5 * mm,
                                 f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


# ---------------------------------------------------------------- dados
inst = pd.read_csv("instancia_modelo_bhtrans.csv")
res = pd.read_csv("resultados_otimizacao_bhtrans.csv")
cen = pd.read_csv("comparativo_resumo_cenarios.csv")
sens = pd.read_csv("sensibilidade_alpha2.csv")

n_pares = len(inst)
n_restr = 24 + n_pares
custo_total = res["custo_operacional_R$"].sum()
rep_total = res["passageiros_represados"].sum()
dem_total = res["demanda"].sum()
viagens_total = res["frequencia_otima"].sum()
z_total = ALPHA_1 * custo_total + ALPHA_2 * rep_total
frota_hora = res.groupby("faixa_horaria")["veiculos_em_operacao"].sum()
horas_pico_frota = frota_hora[frota_hora >= FROTA_MAX - 1].index.tolist()
equilibrio = inst["c_lt"] / inst["capacidade_C"]
eq_min, eq_max = equilibrio.min(), equilibrio.max()

# Demanda real (BHTRANS)
dem_pbh = pd.read_csv("dados_pbh/demanda_diaria_linhas.csv", dtype={"linha": str})
dem_sup_total = dem_pbh["demanda_dia_util_superior"].sum()
dem_inf_total = dem_pbh["demanda_dia_util_inferior"].sum()
tab_pbh = pd.read_csv("dados_pbh/passageiros_corredor_antonio_carlos.csv", dtype={"codigo": str})
estacoes = [f"AC{i:02d}" for i in range(1, 26)] + ["2000", "2001", "6000", "6001", "7000", "7001"]
embarques_estacoes = (
    tab_pbh[tab_pbh["codigo"].isin(estacoes)]
    .groupby("codigo")["media_dia_util"].mean().sum()
)
inst["route_short_name"] = inst["route_short_name"].astype(str)
dem_linha = inst.groupby("route_short_name").agg(dia=("d_lt", "sum"), pico=("d_lt", "max"))

# Limite inferior: mesma distribuição horária, escalada pela razão inferior/superior
razao = dem_pbh.set_index("linha").eval("demanda_dia_util_inferior / demanda_dia_util_superior")
inst_inf = inst.copy()
inst_inf["d_lt"] = (inst_inf["d_lt"] * inst_inf["route_short_name"].map(razao)).round().astype(int)
res_inf = resolver_modelo(inst_inf, FROTA_MAX, ALPHA_1, ALPHA_2, nome="Limite_inferior")

# Dualidade (gerada por analise_dual.py)
duais_r1 = pd.read_csv("analise_dual_frota.csv")
duais_r2 = pd.read_csv("analise_dual_atendimento.csv")
m_lp = construir_modelo(inst, FROTA_MAX, ALPHA_1, ALPHA_2, nome="PL")
m_lp["model"].update()
lp = m_lp["model"].relax()
lp.Params.OutputFlag = 0
lp.optimize()
z_lp, z_mip = lp.ObjVal, z_total
gap_int = 100 * (z_mip - z_lp) / z_mip

par_linha = inst.groupby("route_short_name").agg(
    km_min=("extensao_km", "min"), km_max=("extensao_km", "max"),
    n_min=("tempo_ciclo_horas", "min"), n_max=("tempo_ciclo_horas", "max"),
    c_min=("c_lt", "min"), c_max=("c_lt", "max"),
)


def faixa(a, b, casas=2, pref=""):
    return f"{pref}{br(a, casas)}" if abs(a - b) < 1e-9 else f"{pref}{br(a, casas)} – {br(b, casas)}"


# ---------------------------------------------------------------- conteúdo
story = []

# Cabeçalho
cab = Table(
    [[P("Otimização de Frequência de Linhas do MOVE (Corredor Antônio Carlos)",
        ParagraphStyle("t", fontName="Arial-Bold", fontSize=16, leading=20,
                       textColor=colors.white))],
     [P("Formulação revisada, instância baseada no GTFS e resultados | Pesquisa Operacional (UFMG)",
        ParagraphStyle("st", fontName="Arial", fontSize=9.5, leading=13,
                       textColor=colors.HexColor("#CBD5E1")))]],
    colWidths=[174 * mm],
)
cab.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), NAVY),
    ("LINEBEFORE", (0, 0), (0, -1), 4, AZUL),
    ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ("TOPPADDING", (0, 0), (-1, 0), 12),
    ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
]))
story += [cab, Spacer(1, 7)]

rot = ParagraphStyle("rot", fontName="Arial-Bold", fontSize=7, leading=9, textColor=CINZA_CLARO)
val = ParagraphStyle("val", fontName="Arial", fontSize=8.8, leading=11, textColor=NAVY)
info = Table(
    [[P("INSTITUIÇÃO:", rot), P("DATA:", rot), P("MODELO:", rot), P("SOLVER:", rot)],
     [P("UFMG - Eng. Sistemas", val), P("Novembro / 2026 (rev. 2)", val),
      P("PLIM Bi-Objetivo", val),P("Gurobi Optimizer", val)]],
    colWidths=[43.5 * mm] * 4,
)
info.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
    ("BOX", (0, 0), (-1, -1), 0.5, BORDA),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, 0), 6),
    ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
]))
story += [info, Spacer(1, 4)]

# 1. Contextualização
story += secao("1. CONTEXTUALIZAÇÃO E DIAGNÓSTICO DO MODELO")
story.append(P(
    "O problema consiste em definir quantas viagens por hora (frequência) cada linha troncal do "
    "MOVE no Corredor Av. Antônio Carlos / Pedro I deve realizar ao longo de um dia útil. "
    "A formulação inicial minimizava apenas a demanda não atendida; sem um termo de custo, o "
    "modelo tenderia a alocar o máximo de viagens permitido pelas restrições, gerando uma "
    "operação cara e irrealista. Por isso, a função objetivo foi reformulada como "
    "<b>otimização bi-objetivo ponderada</b> (Ceder, 2016; Arbex &amp; da Cunha, 2015), "
    "equilibrando o custo operacional da concessionária e o nível de serviço ao passageiro."
))
story.append(Spacer(1, 4))
story.append(P(
    "Na implementação computacional sobre os dados reais do GTFS da BHTRANS, a proposta "
    "apresentada no Seminário 1 passou por revisões, resumidas abaixo. As principais corrigem a "
    "estimativa da frota necessária, que estava superdimensionada."
))
story.append(Spacer(1, 5))
story.append(tabela([
    ["Aspecto", "Proposta (Seminário 1)", "Versão atual", "Motivo"],
    ["Tempo de ciclo n<sub>lt</sub>", "Duração da viagem × 2 (ida + volta) × 1,15",
     f"Duração da viagem × {br(MARGEM_TERMINAL)}",
     "As viagens do GTFS da BHTRANS são circulares: a duração já inclui ida e volta."],
    ["Extensão D<sub>l</sub> e custo c<sub>l</sub>", "34,0 km fixos; c<sub>l</sub> = R$ 374,00 para todas as linhas",
     "Extensão medida no GTFS por linha e faixa; c<sub>lt</sub> = D<sub>lt</sub> × R$ 11,00",
     "As linhas têm extensões diferentes (18 a 43 km); custo fixo distorcia a alocação."],
    ["Restrição de frota", "Σ<sub>l</sub> n<sub>lt</sub> f<sub>lt</sub> ≤ F em cada faixa isolada",
     "Frota acumulada: ônibus que saíram em faixas anteriores e ainda não voltaram também contam",
     "Ciclos de 1 a 2,4 h: um ônibus ocupa mais de uma faixa horária."],
    ["Dados do GTFS", "Todas as viagens e dias", "Somente dias úteis; todas as variantes regulares ponderadas pelo nº de viagens",
     "Excluir fins de semana e Carnaval; incluir variantes Direta e Madrugão."],
    ["Horizonte", "Faixas com viagem no GTFS", "24 faixas (0h–23h) para todas as linhas",
     "A demanda das horas sem viagem programada deixava de ser contabilizada."],
    ["Demanda d<sub>lt</sub>", "Hipótese: pico por linha × perfil horário típico",
     "Passageiros registrados por dia útil (BHTRANS, mar–ago/2026), distribuídos pelas viagens programadas de cada hora",
     "Substituir a hipótese por dados observados."],
], [30, 42, 52, 50]))

# 2. Formulação
story += secao("2. FORMULAÇÃO MATEMÁTICA (PLIM)")
story.append(P(
    f"<b>Conjuntos.</b> L = {{{', '.join(LINHAS_CORREDOR)}}} (linhas troncais do corredor); "
    "T = {0, 1, ..., 23} (faixas horárias de um dia útil). As faixas são tratadas de forma "
    "cíclica (a faixa anterior a 0h é 23h)."
))
story.append(Spacer(1, 5))

eq = [
    [P("Modelo Bi-Objetivo Ponderado", s_eq_tit)],
    [P("min Z = α<sub>1</sub> Σ<sub>l,t</sub> c<sub>lt</sub> f<sub>lt</sub> "
       "+ α<sub>2</sub> Σ<sub>l,t</sub> w<sub>lt</sub>", s_eq)],
    [P("sujeito a:", ParagraphStyle("sa", parent=s_eq, fontSize=9, textColor=CINZA_CLARO))],
    [P("(R1) &nbsp; Σ<sub>l</sub> Σ<sub>k≥0</sub> ω(k, n<sub>l,t−k</sub>) · f<sub>l,t−k</sub> "
       "≤ F &nbsp;&nbsp;&nbsp; para toda faixa t &nbsp;&nbsp;(frota em operação)", s_eq)],
    [P("(R2) &nbsp; C<sub>l</sub> f<sub>lt</sub> + w<sub>lt</sub> ≥ d<sub>lt</sub> "
       "&nbsp;&nbsp;&nbsp; para todo (l, t) &nbsp;&nbsp;(atendimento da demanda)", s_eq)],
    [P("(R3) &nbsp; f<sub>min</sub> ≤ f<sub>lt</sub> ≤ f<sub>max</sub>, "
       "f<sub>lt</sub> inteiro; &nbsp; w<sub>lt</sub> ≥ 0", s_eq)],
]
# Célula única: o bloco inteiro muda de página se não couber (não é partido).
t_eq = Table([[[linha[0] for linha in eq]]], colWidths=[174 * mm])
t_eq.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), FUNDO_FO),
    ("LINEBEFORE", (0, 0), (0, -1), 3, AZUL),
    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
    ("TOPPADDING", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
]))
story += [t_eq, Spacer(1, 6)]

story.append(tabela([
    ["Elemento", "Símbolo", "Domínio", "Descrição / Unidade"],
    ["Variável de decisão", "f<sub>lt</sub>", "Inteiro ≥ 0",
     "Número de viagens (partidas) da linha l na faixa t (viagens/hora)."],
    ["Variável de folga", "w<sub>lt</sub>", "Contínuo ≥ 0",
     "Passageiros não atendidos (deixados no ponto) na faixa t."],
    ["Custo por viagem", "c<sub>lt</sub>", "Parâmetro",
     "c<sub>lt</sub> = D<sub>lt</sub> × custo/km (R$/viagem), D<sub>lt</sub> = extensão ida + volta."],
    ["Tempo de ciclo", "n<sub>lt</sub>", "Parâmetro",
     "Duração da viagem circular + margem de terminal (horas)."],
    ["Capacidade", "C<sub>l</sub>", "Parâmetro", "Passageiros por veículo."],
    ["Demanda", "d<sub>lt</sub>", "Parâmetro",
     "Carga no trecho crítico: passageiros/hora no ponto de maior lotação da linha."],
    ["Frota máxima", "F", "Parâmetro", "Veículos simultaneamente em operação no corredor."],
    ["Pesos", "α<sub>1</sub>, α<sub>2</sub>", "Parâmetro",
     "Harmonizam R$ e passageiros não atendidos (α<sub>2</sub> em R$/passageiro)."],
    ["Fração de ocupação", "ω(k, n)", "[0, 1]",
     "Fração média da faixa s + k em que um ônibus que partiu na faixa s, com ciclo n, está em operação."],
], [32, 22, 24, 96]))
story.append(Spacer(1, 6))

story.append(P("<b>Restrição de frota acumulada (R1).</b>", s_h2))
story.append(P(
    "Um ônibus que parte num instante u da faixa s (u uniforme em [0, 1)) fica em operação no "
    "intervalo [u, u + n]. A fração média da faixa s + k ocupada por ele é "
    "ω(k, n) = ∫<sub>0</sub><super>1</super> |[u, u + n] ∩ [k, k + 1]| du. "
    "Assim, a frota em operação na faixa t soma as partidas de t e as partidas anteriores que "
    "ainda não retornaram. Como Σ<sub>k</sub> ω(k, n) = n, para frequência constante R1 se reduz à "
    "relação clássica frota = frequência × tempo de ciclo (Ceder, 2016); a diferença aparece "
    "justamente nas transições de demanda, como o início dos picos. A restrição continua linear "
    "em f, mantendo o modelo como PLIM."
))
story.append(Spacer(1, 4))
story.append(P(
    f"<b>Porte da instância:</b> {n_pares} variáveis inteiras, {n_pares} contínuas e "
    f"{n_restr} restrições ({len(LINHAS_CORREDOR)} linhas × 24 faixas)."
))

# 3. Parametrização
story += secao("3. PARAMETRIZAÇÃO E INSTÂNCIA DE TESTE")
story.append(P(
    "Os tempos de viagem e as extensões foram extraídos do feed GTFS da BHTRANS "
    "(routes, trips, shapes, stop_times e calendar). As extensões foram calculadas a partir das "
    "geometrias dos itinerários projetadas em SIRGAS 2000 / UTM 23S (EPSG:31983). Para cada linha "
    "e faixa, ciclo e extensão são médias ponderadas pelas viagens de dia útil de cada variante."
))
story.append(Spacer(1, 5))

linhas_par = [["Linha", "Extensão D<sub>lt</sub> (km)", "Ciclo n<sub>lt</sub> (h)",
               "Custo c<sub>lt</sub> (R$/viagem)", "Demanda (pas/dia útil)",
               "Pico (pas/h)"]]
for l in LINHAS_CORREDOR:
    p = par_linha.loc[int(l)] if int(l) in par_linha.index else par_linha.loc[l]
    linhas_par.append([
        l, faixa(p.km_min, p.km_max, 1), faixa(p.n_min, p.n_max),
        faixa(p.c_min, p.c_max, 2, ""), br(dem_linha.loc[l, "dia"], 0),
        br(dem_linha.loc[l, "pico"], 0),
    ])
story.append(tabela(linhas_par, [16, 32, 26, 38, 34, 28]))
story.append(Spacer(1, 6))

story.append(tabela([
    ["Parâmetro", "Valor adotado", "Fonte"],
    ["Custo/km", f"R$ {br(CUSTO_KM_MEDIO)} (média Padron/Articulado); cenários: R$ {br(CUSTO_KM_ARTICULADO)} articulado, R$ {br(CUSTO_KM_PADRON)} padron", "SUMOB / PBH"],
    ["C<sub>l</sub>", f"{CAP_ARTICULADO} passageiros (articulado padronizado); cenários: 85 (padron)", "Especificação MOVE"],
    ["F", f"{FROTA_MAX} veículos (cenário de expansão: 110)", "Hipótese de planejamento"],
    ["f<sub>min</sub>, f<sub>max</sub>",f"{F_MIN} a {F_MAX} viagens/h; 0 a {F_MAX} nas faixas sem viagem programada", "Hipótese contratual / física"],
    ["Margem de terminal", f"+{round((MARGEM_TERMINAL - 1) * 100)}% sobre a duração da viagem", "Hipótese de regulação"],
    ["α<sub>1</sub>, α<sub>2</sub>", f"α<sub>1</sub> = {br(ALPHA_1, 1)} | α<sub>2</sub> = {br(ALPHA_2, 1)} R$/passageiro", "Calibração (ver análise de sensibilidade)"],
    ["d<sub>lt</sub>", f"Média de dias úteis mar–ago/2026, limite {DEMANDA_PBH_LIMITE}: "
     f"{br(dem_total, 0)} pas/dia; distribuída pelas viagens programadas de cada hora (GTFS)",
     "BHTRANS (relatório mensal ago/2026)"],
], [32, 98, 44]))
story.append(Spacer(1, 6))
story.append(P("<b>Demanda a partir dos dados da BHTRANS.</b>", s_h2))
story.append(P(
    "O relatório mensal da BHTRANS publica, para o Corredor Antônio Carlos, os passageiros "
    "registrados por linha troncal e por estação (total do mês e média de dias úteis). No MOVE, "
    "quem embarca numa estação passa pela catraca da estação: o passageiro é registrado na "
    f"estação (AC01–AC25) ou nas linhas de bloqueio/acesso das estações de integração "
    f"(em média {br(embarques_estacoes, 0)} embarques por dia útil), e não na linha troncal. "
    "Por isso, a demanda diária de cada linha é o registro no próprio ônibus mais uma parcela "
    "dos embarques nas estações, rateada pelas viagens programadas em dia útil. Como outras "
    "linhas (5250, 5550, 6031, 6350) também usam o corredor, há dois limites: o "
    "<b>superior</b> rateia as estações só entre as cinco linhas do modelo "
    f"({br(dem_sup_total, 0)} pas/dia); o <b>inferior</b> inclui as demais linhas no rateio "
    f"({br(dem_inf_total, 0)} pas/dia). A instância principal usa o limite superior, "
    "que é conservador para o dimensionamento da frota."
))
story.append(Spacer(1, 6))
story.append(caixa(P(
    "<b>Limitações da demanda:</b> (i) são passageiros registrados (embarques), não a carga "
    "medida no trecho crítico; adota-se fator de trecho crítico igual a "
    f"{br(FATOR_TRECHO_CRITICO, 1)}, que é conservador; (ii) quem chega por linha alimentadora "
    "e se transfere na estação de integração é registrado na alimentadora, e não aparece na "
    "troncal; (iii) o perfil horário segue a oferta programada (GTFS), que reflete o "
    "planejamento da BHTRANS, e não contagens horárias. Tempos, extensões e custos vêm de "
    "dados oficiais.", s_nota),
    AMBAR_FUNDO, AMBAR_BORDA))

# 4. Resultados
story += secao("4. RESULTADOS")
story.append(P(
    f"O modelo foi resolvido pelo Gurobi (branch-and-cut) em menos de 1 segundo, com gap de "
    f"otimalidade abaixo da tolerância padrão de 0,01%. A solução ótima tem Z = R$ {br(z_total)}, com custo operacional de "
    f"R$ {br(custo_total)}, {br(viagens_total, 0)} viagens no dia e "
    f"<b>{br(rep_total, 0)} passageiros não atendidos ({br(100 * rep_total / dem_total, 1)}% da demanda)</b>."
))
story.append(Spacer(1, 5))

por_linha = res.groupby("linha").agg(
    v=("frequencia_otima", "sum"), d=("demanda", "sum"),
    w=("passageiros_represados", "sum"), c=("custo_operacional_R$", "sum"),
)
tab_res = [["Linha", "Viagens/dia", "Demanda (pas)", "Não atendidos", "% não atend.", "Custo (R$)"]]
for l, r in por_linha.iterrows():
    tab_res.append([str(l), br(r.v, 0), br(r.d, 0), br(r.w, 0), br(100 * r.w / r.d, 1) + "%", br(r.c)])
tab_res.append(["<b>Total</b>", f"<b>{br(viagens_total, 0)}</b>", f"<b>{br(dem_total, 0)}</b>",
                f"<b>{br(rep_total, 0)}</b>", f"<b>{br(100 * rep_total / dem_total, 1)}%</b>",
                f"<b>{br(custo_total)}</b>"])
story.append(tabela(tab_res, [20, 26, 30, 30, 28, 40], negrito_ultima=True))
story.append(Spacer(1, 6))

horas_txt = ", ".join(f"{h}h" for h in horas_pico_frota)
deficit_hora = res.groupby("faixa_horaria")["passageiros_represados"].sum()
piores = deficit_hora.sort_values(ascending=False).head(2).index.tolist()
piores_txt = " e ".join(f"{h}h" for h in sorted(piores))
pct_piores = 100 * deficit_hora[piores].sum() / max(rep_total, 1)
story.append(P(
    f"<b>Uso da frota.</b> A frota em operação atinge o limite de {FROTA_MAX} veículos às "
    f"{horas_txt}. Os maiores déficits ocorrem às {piores_txt} "
    f"({br(pct_piores, 0)}% dos passageiros não atendidos), no início dos picos: os ônibus que "
    "partem nessas horas continuam em circulação na faixa seguinte, quando a frota já está no "
    "limite. Esse é o efeito capturado pela restrição de frota acumulada."
))
story.append(Spacer(1, 4))

frota_tab = [["Hora"] + [f"{h}h" for h in range(4, 24, 2)],
             ["Frota"] + [br(frota_hora.get(h, 0), 0) for h in range(4, 24, 2)]]
story.append(tabela(frota_tab, [16.4] + [15.76] * 10))
story.append(Spacer(1, 5))
story.append(P(
    f"<b>Limite inferior de demanda.</b> Com o rateio que inclui as demais linhas do corredor "
    f"(≈ {br(res_inf['demanda_total'], 0)} pas/dia), o modelo deixa "
    f"{br(res_inf['passageiros_represados'], 0)} passageiros sem atendimento "
    f"({br(100 * res_inf['passageiros_represados'] / res_inf['demanda_total'], 1)}%), com custo "
    f"de R$ {br(res_inf['custo_operacional'])} e frota máxima de "
    f"{br(res_inf['frota_por_faixa'].max(), 0)} veículos. A frota de {FROTA_MAX} veículos é, "
    "portanto, suficiente no limite inferior e insuficiente nos picos do limite superior."
))
story.append(Spacer(1, 8))

story.append(KeepTogether([
    P("<b>Cenários de frota.</b>", s_h2),
    P("O Cenário R reproduz a instância principal (100% articulado a R$ 11,00/km). Os demais usam "
      f"custo por tipologia (articulado R$ {br(CUSTO_KM_ARTICULADO)}/km, 130 lugares; padron "
      f"R$ {br(CUSTO_KM_PADRON)}/km, 85 lugares)."),
    Spacer(1, 4),
]))
nomes_cen = {
    "Cenario_R_Relatorio": "R – Instância principal (100% articulado, custo médio)",
    "Cenario_0_Baseline": "0 – Baseline (articulado só na linha 51)",
    "Cenario_1_Frota_Mista_MOVE": "1 – Frota mista (articulado em 51, 52 e 63)",
    "Cenario_2_100pct_Articulados": "2 – 100% articulados",
    "Cenario_3_Expansao_Frota_110": "3 – Baseline com frota de 110 veículos",
}
tab_cen = [["Cenário", "Frota", "Custo (R$)", "Não atendidos", "Z (R$)"]]
for _, c in cen.iterrows():
    tab_cen.append([nomes_cen.get(c.cenario, c.cenario), str(int(c.frota_max)),
                    br(c["custo_operacional_R$"]),
                    f"{br(c.passageiros_represados, 0)} ({br(c.pct_nao_atendida, 1)}%)",
                    br(c.valor_obj_Z)])
story.append(tabela(tab_cen, [70, 16, 30, 30, 28]))
story.append(Spacer(1, 5))
story.append(P(
    "Converter a frota para articulados reduz os passageiros não atendidos de forma mais eficaz "
    "que ampliar a frota de padrons: o Cenário 2 deixa menos passageiros no ponto que o Cenário 3, "
    "com custo operacional menor, porque o gargalo é a capacidade ofertada por veículo-hora."
))

story.append(KeepTogether([
    P("<b>Análise de sensibilidade do peso α<sub>2</sub>.</b>", s_h2),
    P("Mantidos α<sub>1</sub> = 1 e F = 90, variou-se a penalidade por passageiro não atendido. "
      f"Abaixo do ponto de equilíbrio c<sub>lt</sub> / C<sub>l</sub> "
      f"(R$ {br(eq_min)} a R$ {br(eq_max)} por passageiro, conforme a linha e a faixa), "
      "é mais barato deixar o passageiro no ponto do que realizar a "
      "viagem."),
    Spacer(1, 4),
]))
sel = sens[sens.alpha_2.isin([1.5, 2.0, 2.5, 3.0, 3.5, 5.0, 10.0, 25.0, 50.0])]
tab_s = [["α<sub>2</sub> (R$/pas)", "Viagens", "Custo (R$)", "Não atendidos", "% não atend.", "Faixas c/ frota no limite"]]
for _, s in sel.iterrows():
    tab_s.append([br(s.alpha_2, 1), br(s.viagens_totais, 0), br(s["custo_operacional_R$"]),
                  br(s.passageiros_represados, 0), br(s.pct_demanda_nao_atendida, 1) + "%",
                  str(int(s.faixas_frota_saturada))])
story.append(tabela(tab_s, [26, 22, 32, 30, 28, 36]))
story.append(Spacer(1, 5))
story.append(P(
    "A curva mostra o trade-off esperado: entre R$ 2 e R$ 3,50 por passageiro o nível de serviço "
    "sobe rapidamente; a partir de R$ 10, o ganho é marginal, pois o limite passa a ser a frota "
    "disponível nos picos e não o custo. O valor adotado (α<sub>2</sub> = 25) está nessa região "
    "estável, e o resultado é pouco sensível a ele."
))

# 5. Dualidade e pós-otimização
story += secao("5. DUALIDADE E PÓS-OTIMIZAÇÃO")
story.append(P(
    "Como o PLIM não fornece variáveis duais diretamente, resolveu-se a <b>relaxação linear</b> "
    "(f<sub>lt</sub> contínuo) pelo simplex e extraíram-se os duais das restrições. "
    f"O valor ótimo da relaxação é R$ {br(z_lp)}, contra R$ {br(z_mip)} do problema inteiro: "
    f"gap de integralidade de {br(gap_int, 2)}%, o que indica que a relaxação é uma boa "
    "aproximação e que seus duais podem ser interpretados economicamente."
))
story.append(Spacer(1, 4))
story.append(P(
    "<b>Preço-sombra da frota (R1).</b> O dual de R1 na faixa t é a redução de Z obtida com um "
    "veículo a mais em operação naquela hora. Ele só é positivo nas faixas em que a frota está "
    "no limite; nas demais, há folga e o preço-sombra é zero (folgas complementares). A coluna "
    "\"faixa de validade\" é o intervalo do lado direito em que o preço-sombra permanece "
    "constante (análise de sensibilidade do RHS). A última coluna valida o resultado no problema "
    "inteiro, re-otimizando o PLIM com o limite daquela faixa aumentado em 1 veículo."
))
story.append(Spacer(1, 5))
tab_d = [["Faixa", "Frota (PL)", "Preço-sombra (R$/veículo)", "Faixa de validade do RHS",
          "Redução de Z no PLIM (+1 veículo)"]]
for _, r in duais_r1[(duais_r1["preco_sombra_R$_por_veiculo"] > 1e-6)
                     | (duais_r1["reducao_Z_PLIM_+1_veiculo"] > 1e-6)].iterrows():
    ate = "∞" if pd.isna(r.rhs_valido_ate) else br(r.rhs_valido_ate, 1)
    tab_d.append([f"{int(r.faixa_horaria)}h", br(r.frota_em_operacao_PL, 1),
                  br(r["preco_sombra_R$_por_veiculo"]),
                  f"{br(r.rhs_valido_de, 1)} a {ate}",
                  br(r["reducao_Z_PLIM_+1_veiculo"])])
story.append(tabela(tab_d, [18, 24, 42, 44, 46]))
story.append(Spacer(1, 5))
top = duais_r1.sort_values("preco_sombra_R$_por_veiculo", ascending=False).iloc[0]
story.append(P(
    f"O veículo mais valioso é o das {int(top.faixa_horaria)}h: R$ {br(top['preco_sombra_R$_por_veiculo'])} "
    "de redução em Z por veículo, o equivalente à penalidade de cerca de "
    f"{br(top['preco_sombra_R$_por_veiculo'] / ALPHA_2, 0)} passageiros não atendidos "
    f"(α<sub>2</sub> = {br(ALPHA_2, 0)}). Como uma restrição de frota afeta as horas vizinhas "
    "(R1 é acumulada), reforçar a frota no início do pico da manhã tem o maior retorno. No "
    "problema inteiro, os ganhos são menores que os do PL, porque as frequências são inteiras; "
    "em faixas em que o PL tem folga, o PLIM ainda pode ganhar com +1 veículo, ao permitir "
    "arredondar uma frequência para cima."
))
story.append(Spacer(1, 4))
reg = duais_r2["regime"].value_counts()
story.append(P(
    "<b>Duais da restrição de atendimento (R2).</b> O dual de R2 é o custo marginal de atender "
    "um passageiro a mais em (l, t) e se divide em três regimes, coerentes com a teoria: "
    f"(a) igual a c<sub>lt</sub>/C<sub>l</sub> quando a frota tem folga "
    f"({reg.get('atendido; frota com folga (= c/C)', 0)} pares): basta aumentar a frequência; "
    f"(b) acima de c<sub>lt</sub>/C<sub>l</sub> quando a frota está no limite "
    f"({reg.get('atendido; frota no limite (> c/C)', 0)} pares): o passageiro extra disputa "
    "veículos com outras linhas e o dual incorpora o preço-sombra da frota; (c) igual a "
    f"α<sub>2</sub> quando já há passageiros não atendidos "
    f"({reg.get('passageiro excedente não atendido (= α2)', 0)} pares): o passageiro extra "
    "também ficaria no ponto."
))

# 6. Implementação
story += secao("6. IMPLEMENTAÇÃO (PYTHON + GUROBI)")
story.append(tabela([
    ["Arquivo", "Função"],
    ["config.py", "Todos os parâmetros do modelo e hipóteses (fonte única)."],
    ["extracao_dados_gtfs.py", "Baixa o GTFS, filtra dias úteis e linhas, calcula extensões (GeoPandas) e ciclos."],
    ["demanda_pbh.py", "Extrai do relatório mensal da BHTRANS os passageiros do corredor e monta a demanda diária por linha."],
    ["cria_instancia_teste.py", "Monta a instância (24 faixas × linhas): custos, capacidade, demanda e limites."],
    ["modelo.py", "Implementação única do PLIM em gurobipy, incluindo os pesos ω da frota acumulada."],
    ["otimizacao.py", "Resolve a instância principal e exporta os resultados."],
    ["gera_instancias.py", "Resolve os cenários de tipologia e tamanho de frota."],
    ["analise_sensibilidade_alpha.py", "Varia α<sub>2</sub> e mede o trade-off custo × atendimento."],
    ["analise_dual.py", "Relaxação linear, preços-sombra, faixas de validade do RHS e validação no PLIM."],
], [52, 122]))


# 7. Referências
story += secao("7. REFERÊNCIAS BIBLIOGRÁFICAS")
refs = [
    "ARBEX, R. O.; DA CUNHA, C. B. Efficient transit network design and frequencies setting "
    "multi-objective optimization by alternating objective genetic algorithm. <i>Transportation "
    "Research Part B: Methodological</i>, v. 81, p. 355-376, 2015.",
    "ARENALES, M.; ARMENTANO, V.; MORABITO, R.; YANASSE, H. <i>Pesquisa Operacional para Cursos "
    "de Engenharia</i>. Rio de Janeiro: Campus/Elsevier, 2007.",
    "BHTRANS. <i>Sistema de Transporte por Ônibus Convencional e MOVE de BH: relatório de "
    "agosto de 2026</i>. Belo Horizonte: Prefeitura de Belo Horizonte, 2026. Disponível em: "
    "&lt;https://prefeitura.pbh.gov.br/sites/default/files/estrutura-de-governo/bhtrans/2026/"
    "relatorio-de-agosto-2026-para_publicacao.pdf&gt;. Acesso em: nov. 2026.",
    "CEDER, A. <i>Public Transit Planning and Operation: Modeling, Hierarchy and Integration</i>. "
    "2nd ed. CRC Press, 2016.",
    "GUROBI OPTIMIZATION. <i>Gurobi Optimizer Reference Manual</i>. Disponível em: "
    "&lt;https://www.gurobi.com/documentation/&gt;. Acesso em: nov. 2026.",
    "PREFEITURA MUNICIPAL DE BELO HORIZONTE. <i>Portal de Dados Abertos da PBH / BHTRANS</i>. "
    "Disponível em: &lt;https://dados.pbh.gov.br/&gt;. Acesso em: nov. 2026.",
    "SCHMIDT, M.; SCHÖBEL, A. Planning and Optimizing Transit Lines. arXiv:2405.10074, 2024.",
]
for r in refs:
    story.append(P(r, s_ref))

# ---------------------------------------------------------------- gera
doc = SimpleDocTemplate(
    ARQUIVO_SAIDA, pagesize=A4,
    leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
    title="Otimização de Frequência de Linhas do MOVE (Corredor Antônio Carlos)",
    author="UFMG - Pesquisa Operacional",
)
doc.build(story, canvasmaker=CanvasNumerado)
print(f"PDF gerado: {ARQUIVO_SAIDA}")
