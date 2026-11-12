"""
Parâmetros centrais do modelo de otimização de frequências (Corredor
Antônio Carlos). Todos os scripts importam daqui, para que uma mudança
valha para o pipeline inteiro.

Cada parâmetro indica sua ORIGEM:
  [GTFS]     extraído do GTFS da BHTRANS (oferta programada atual);
  [BHTRANS]  extraído dos relatórios mensais de passageiros da BHTRANS;
  [HIPÓTESE] valor adotado pelo grupo, sem fonte oficial -- declarado como tal
             no artigo e testado em análise de sensibilidade.
"""

# ---------- Linhas do corredor ----------
# [GTFS] Linhas troncais do MOVE Antônio Carlos. As demais linhas que a
# BHTRANS lista no corredor (5250, 5550, 6031, 6350) compartilham só 22-53%
# das paradas com as troncais (passam majoritariamente fora do corredor).
LINHAS_CORREDOR = ["51", "52", "63", "64", "67"]

# ---------- Extração GTFS ----------
# Cada viagem do GTFS da BHTRANS é circular (começa e termina na mesma
# estação), então a duração da viagem JÁ é o ciclo completo ida + volta.
MARGEM_TERMINAL = 1.15  # [HIPÓTESE] +15% de regulação no terminal

# Variantes de itinerário a excluir (trechos do trip_headsign). Lista vazia =
# todas as variantes regulares de dia útil, ponderadas pelo nº de viagens.
VARIANTES_EXCLUIDAS = []

# Extensão usada no custo por viagem c = D x custo/km.
# True: extensão real medida no GTFS (ida + volta) [GTFS].
# False: valor único D_L_RELATORIO para todas as linhas (proposta inicial).
USAR_EXTENSAO_GTFS = True
D_L_RELATORIO = 34.0  # km

# ---------- Tipos de veículo (decisão do modelo) ----------
# O modelo escolhe quantas viagens de cada tipo cada linha faz em cada faixa.
# "frota": veículos disponíveis do tipo; "grade_atual" = frota máxima em
# operação exigida pela grade atual do GTFS (calculada com a mesma regra de
# frota acumulada do modelo) [GTFS]. Capacidades e custos: [HIPÓTESE].
TIPOS_VEICULO = {
    "articulado": {"capacidade": 130, "custo_km": 12.50, "frota": "grade_atual"},
    "padron": {"capacidade": 85, "custo_km": 9.50, "frota": 0},
}

# ---------- Limites de frequência ----------
# f_max por linha: intervalo mínimo de 2,5 min entre partidas [HIPÓTESE].
F_MAX = 24

# f_min: padrão de serviço = intervalo máximo entre ônibus [HIPÓTESE], aplicado
# nas faixas em que a linha opera hoje (GTFS). f_min = ceil(60 / intervalo).
HORAS_PICO = [6, 7, 8, 16, 17, 18]
INTERVALO_MAX_MIN = {"pico": 10, "dia": 20, "noite": 60}  # minutos
HORAS_DIA = range(5, 23)  # 5h-22h (fora do pico) = "dia"; demais = "noite"

# Faixas sem viagem no GTFS (madrugada etc.):
# True: o modelo pode criar serviço (f_min = 0, f_max = F_MAX);
# False: mantém a grade atual (f = 0).
OPERAR_FORA_DO_HORARIO_GTFS = True

# Capacidade física do corredor: máximo de partidas por hora somando as
# linhas. "grade_atual" = maior número de partidas/h programado hoje no GTFS
# (capacidade demonstrada pela operação) [GTFS]; ou um número [HIPÓTESE].
CAP_CORREDOR = "grade_atual"

# ---------- Passageiros não atendidos ----------
# "espera": quem não embarca na faixa t continua esperando e entra na demanda
#           de t+1 (w_lt = passageiros esperando ao fim da faixa; soma de w =
#           passageiro-hora de espera excedente);
# "perda":  quem não embarca desiste (w_lt = passageiros perdidos).
NAO_ATENDIDOS = "espera"

# ---------- Demanda ----------
# "pbh": passageiros registrados por dia útil (BHTRANS, via demanda_pbh.py);
# "hipotese": DEMANDA_PICO_LINHA x FATORES_DEMANDA (proposta inicial).
FONTE_DEMANDA = "pbh"

# Os embarques nas estações do MOVE são registrados na catraca da estação, não
# na linha; demanda_pbh.py os rateia entre as linhas e gera dois limites
# [BHTRANS + HIPÓTESE de rateio]: inferior (rateio com todas as linhas do
# corredor) e superior (só linhas do modelo).
# LAMBDA_DEMANDA posiciona a instância: demanda = inf + λ (sup - inf).
# 0 = limite inferior, 1 = limite superior, 0,5 = cenário central.
LAMBDA_DEMANDA = 0.5

# Distribuição da demanda diária pelas 24 horas:
# "gtfs": proporcional às viagens programadas em cada hora (dia útil);
# "tipico": proporcional a FATORES_DEMANDA (perfil típico, independente da
#           grade atual -- usado como teste de robustez).
PERFIL_HORARIO = "gtfs"

# Fração dos embarques que passa pelo trecho crítico (carga máxima). 1,0 é
# conservador: todo passageiro ocupa o veículo no trecho crítico [HIPÓTESE].
FATOR_TRECHO_CRITICO = 1.0

# ---------- Demanda hipotética / perfil típico ----------
DEMANDA_PICO_LINHA = {"51": 3200, "52": 1800, "63": 1400, "64": 1200, "67": 1100}
FATORES_DEMANDA = {
    0: 0.05, 1: 0.02, 2: 0.01, 3: 0.02, 4: 0.15, 5: 0.50,
    6: 1.00, 7: 0.95, 8: 0.70, 9: 0.45, 10: 0.40, 11: 0.45, 12: 0.50,
    13: 0.45, 14: 0.45, 15: 0.55, 16: 0.75, 17: 0.95, 18: 0.90,
    19: 0.60, 20: 0.40, 21: 0.30, 22: 0.20, 23: 0.10,
}

# ---------- Pesos da função objetivo ----------
ALPHA_1 = 1.0  # peso do custo operacional (R$)
# [HIPÓTESE] penalidade por passageiro-hora de espera (R$). Calibrada pela
# fronteira de Pareto (analise_pareto.py) e pela sensibilidade.
ALPHA_2 = 25.0
