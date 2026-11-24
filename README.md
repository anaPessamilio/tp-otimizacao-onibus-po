# Otimização de frequências e tipos de veículo — MOVE, Corredor Antônio Carlos

Trabalho computacional de Pesquisa Operacional (UFMG).
Autores: Pedro Henrique Araujo, Marcus Vinicius Bittencourt e Ana Carolina Pessamilio.

Modelo de Programação Linear Inteira Mista (PLIM) que define, para as cinco
linhas troncais do MOVE no Corredor Antônio Carlos (51, 52, 63, 64 e 67),
quantas viagens de cada tipo de veículo partem em cada hora de um dia útil,
minimizando custo operacional + espera excedente dos passageiros, sujeito à
frota acumulada, à capacidade do corredor e ao padrão mínimo de serviço.
Resolvido com o Gurobi.

## Como rodar

1. Python 3.13 e as dependências:

   ```
   pip install -r requirements.txt
   ```

2. Licença do Gurobi. O modelo tem 360 variáveis e 393 restrições; a licença
   acadêmica gratuita do Gurobi serve (a licença restrita que acompanha o
   `gurobipy` também comporta esse tamanho).

3. Pipeline completo (na pasta do projeto):

   ```
   python executar_tudo.py --sem-gtfs
   ```

   Leva cerca de 15 minutos. Usa os parâmetros já extraídos do GTFS
   (`parametros_gtfs_extraidos.csv`) e os arquivos `routes.txt`, `trips.txt`
   e `calendar.txt` em `gtfs_bhtrans/`. Para refazer também a extração do GTFS,
   rode `python executar_tudo.py`: o script baixa o GTFS completo da BHTRANS
   (cerca de 500 MB).

   Só a instância principal: `python otimizacao.py` (menos de 1 s).

Todos os parâmetros ficam em `config.py`, com a origem de cada um
([GTFS], [BHTRANS], [IBGE] ou [HIPÓTESE]).

## Etapas do pipeline (`executar_tudo.py`)

| Script | O que faz | Saídas |
|---|---|---|
| `extracao_dados_gtfs.py` | Extensões, ciclos e viagens por linha e hora (GTFS) | `parametros_gtfs_extraidos.csv` |
| `demanda_pbh.py` | Embarques por dia útil do relatório da BHTRANS e rateio das estações | `dados_pbh/*.csv` |
| `cria_instancia_teste.py` | Monta a instância (5 linhas × 24 h) e calibra λ | `instancia_modelo_bhtrans.csv` |
| `otimizacao.py` | Resolve a instância principal | `resultados_otimizacao_bhtrans.csv`, `log_gurobi.txt` |
| `validacao_grade.py` | Grade atual (GTFS) × ótimo, modos fila e perda | `validacao_*.csv` |
| `analise_mesmo_orcamento.py` | Grade atual × ótimo a orçamento igual | `comparacao_mesmo_orcamento*.csv` |
| `gera_instancias.py` | Cenários de frota e corredor | `comparativo_*.csv` |
| `analise_sensibilidade_alpha.py` | Sensibilidade de α₂ | `sensibilidade_alpha2.csv` |
| `analise_pareto.py` | Fronteira de Pareto (ε-restrição) | `fronteira_pareto.csv` |
| `analise_demanda.py` | Resultados por nível de demanda (λ) e robustez | `analise_demanda_lambda.csv`, `analise_robustez.csv` |
| `analise_dual.py` | Preços-sombra e pós-otimização | `analise_dual_*.csv` |
| `gera_figuras.py` | Figuras | `latex/figuras/` |
| `gera_tabelas_latex.py` | Tabelas e números citados no texto | `latex/tabelas/` |

O modelo está em `modelo.py` (implementação única usada por todos os scripts).

## Artigo e slides

`latex/artigo.tex` e `latex/slides.tex` (pdfLaTeX + BibTeX). Tabelas e números
vêm de `latex/tabelas/`, gerados pelo código; não devem ser editados à mão.

## Fontes de dados

- GTFS da BHTRANS: <https://s3.amazonaws.com/mobilibus-uploads/gtfs/GTFSBHTRANS.zip>
- Relatório mensal da BHTRANS (agosto de 2026), em `dados_pbh/`
- IBGE, PNAD Contínua, 3º trimestre de 2025 (renda média de Minas Gerais, usada em α₂)
