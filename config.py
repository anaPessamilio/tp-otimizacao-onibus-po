"""
Parâmetros centrais do modelo de otimização de frequências (Corredor
Antônio Carlos). Todos os scripts importam daqui, para que uma mudança
valha para o pipeline inteiro.
"""

# ---------- Linhas do corredor ----------
LINHAS_CORREDOR = ["51", "52", "63", "64", "67"]

# ---------- Extração GTFS ----------
# Cada viagem do GTFS da BHTRANS é circular (começa e termina na mesma
# estação), então a duração da viagem JÁ é o ciclo completo ida + volta.
# Aplica-se apenas uma margem de regulação no terminal.
MARGEM_TERMINAL = 1.15  # +15% sobre a duração da viagem

# Variantes de itinerário a excluir (trechos do trip_headsign, sem
# diferenciar maiúsculas). Lista vazia = todas as variantes regulares de dia
# útil entram, ponderadas pelo número de viagens. Ex.: ["MADRUG"].
VARIANTES_EXCLUIDAS = []

# ---------- Custos (SUMOB) ----------
CUSTO_KM_MEDIO = 11.00  # R$/km, média Padron/Articulado (relatório)
CUSTO_KM_ARTICULADO = 12.50  # R$/km
CUSTO_KM_PADRON = 9.50  # R$/km

# Extensão usada no custo por viagem c_l = D_l x custo/km.
# True: usa a extensão real de cada linha medida no GTFS (ida + volta).
# False: usa o valor único do relatório (D_L_RELATORIO) para todas as linhas.
USAR_EXTENSAO_GTFS = True
D_L_RELATORIO = 34.0  # km

# ---------- Capacidades ----------
CAP_ARTICULADO = 130  # passageiros
CAP_PADRON = 85  # passageiros

# ---------- Restrições ----------
FROTA_MAX = 90  # veículos simultâneos no corredor
F_MIN = 1  # viagens/hora
F_MAX = 24  # viagens/hora (intervalo de 2,5 min)

# Horas em que a linha não tem viagem da variante principal no GTFS
# (madrugada, início/fim de operação). A demanda dessas horas entra no modelo
# em vez de ser descartada:
# True: o modelo pode decidir operar nessas horas (f_min = 0, f_max = F_MAX),
#       usando o tempo de ciclo médio da linha.
# False: mantém a grade atual da BHTRANS (f = 0); a demanda dessas horas
#        conta integralmente como passageiros não atendidos.
OPERAR_FORA_DO_HORARIO_GTFS = True

# Tempo de ciclo n_lt: o GTFS tem horário fixo por variante, então n_lt varia
# ao longo do dia apenas pela mistura de variantes em cada faixa (ex.: linha
# 51 no pico, com viagens Direta mais curtas). Congestionamento por horário
# não é capturado pela grade programada.

# ---------- Demanda ----------
# Fonte da demanda diária por linha:
# "pbh": passageiros registrados por dia útil (relatórios mensais da BHTRANS,
#        extraídos por demanda_pbh.py -> dados_pbh/demanda_diaria_linhas.csv);
# "hipotese": DEMANDA_PICO_LINHA x FATORES_DEMANDA abaixo (versão anterior).
FONTE_DEMANDA = "pbh"

# Os embarques nas estações do MOVE não são registrados na linha troncal, e
# sim na catraca da estação; demanda_pbh.py os rateia entre as linhas e gera
# dois limites: "superior" (só linhas do modelo) ou "inferior" (todas as
# linhas que a BHTRANS lista no corredor).
DEMANDA_PBH_LIMITE = "superior"

# Distribuição da demanda diária pelas 24 horas (só para FONTE_DEMANDA="pbh"):
# "gtfs": proporcional às viagens programadas em cada hora (dia útil);
# "tipico": proporcional a FATORES_DEMANDA (perfil típico de corredor).
PERFIL_HORARIO = "gtfs"

# Fração dos embarques que passa pelo trecho crítico (carga máxima). 1,0 é
# conservador: supõe que todo passageiro ocupa o veículo no trecho crítico.
FATOR_TRECHO_CRITICO = 1.0

# ---------- Demanda hipotética (FONTE_DEMANDA = "hipotese") ----------
# d_lt = carga no trecho crítico: passageiros/hora no ponto de maior
# lotação da linha (não é o total de embarques). É isso que precisa caber
# em C_l · f_lt na restrição R2 (Ceder, 2016).
# Demanda de pico por linha (passageiros/hora no trecho crítico).
DEMANDA_PICO_LINHA = {
    "51": 3200,  # linha de maior volume do corredor
    "52": 1800,
    "63": 1400,
    "64": 1200,
    "67": 1100,
}

# Perfil horário: fração da demanda de pico em cada hora (0h a 23h).
FATORES_DEMANDA = {
    0: 0.05, 1: 0.02, 2: 0.01, 3: 0.02, 4: 0.15, 5: 0.50,
    6: 1.00,  # pico manhã
    7: 0.95, 8: 0.70, 9: 0.45, 10: 0.40, 11: 0.45, 12: 0.50,
    13: 0.45, 14: 0.45, 15: 0.55, 16: 0.75,
    17: 0.95,  # pico tarde
    18: 0.90, 19: 0.60, 20: 0.40, 21: 0.30, 22: 0.20, 23: 0.10,
}

# ---------- Pesos da função objetivo ----------
ALPHA_1 = 1.0  # peso do custo operacional (R$)
ALPHA_2 = 25.0  # penalidade por passageiro deixado no ponto (R$/pas)
