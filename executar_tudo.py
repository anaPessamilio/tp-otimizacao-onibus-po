"""
Executa o pipeline completo, na ordem, e para no primeiro erro.

    python executar_tudo.py            # tudo (inclui baixar/ler o GTFS)
    python executar_tudo.py --sem-gtfs # pula a extração do GTFS (mais rápido)
"""

import subprocess
import sys
import time

ETAPAS = [
    ("extracao_dados_gtfs.py", "Oferta: GTFS da BHTRANS"),
    ("demanda_pbh.py", "Demanda: relatório mensal da BHTRANS"),
    ("cria_instancia_teste.py", "Montagem da instância"),
    ("otimizacao.py", "Solução da instância principal (Gurobi)"),
    ("validacao_grade.py", "Validação contra a grade atual"),
    ("gera_instancias.py", "Cenários de frota e infraestrutura"),
    ("analise_sensibilidade_alpha.py", "Sensibilidade de alfa_2"),
    ("analise_pareto.py", "Fronteira de Pareto (epsilon-restrição)"),
    ("analise_demanda.py", "Resultados por nível de demanda e robustez"),
    ("analise_dual.py", "Dualidade e pós-otimização"),
    ("gera_figuras.py", "Figuras do artigo e slides"),
    ("gera_tabelas_latex.py", "Tabelas e números do artigo e slides"),
]

if "--sem-gtfs" in sys.argv:
    ETAPAS = ETAPAS[1:]

for script, descricao in ETAPAS:
    inicio = time.time()
    print(f"\n>>> {script}: {descricao}")
    r = subprocess.run([sys.executable, script], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        sys.exit(f"ERRO em {script}")
    print(f"    ok ({time.time() - inicio:.1f} s)")

print("\nPipeline concluído. Artigo e slides: pasta latex/ (compilar no Overleaf).")
