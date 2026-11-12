import pandas as pd

from config import ALPHA_1, ALPHA_2, FROTA_MAX
from modelo import resolver_modelo

# ==========================================
# 1. CARREGAMENTO DA INSTÂNCIA
# ==========================================
# Parâmetros por (linha, faixa): c_lt (R$/viagem), tempo_ciclo_horas (n_lt),
# capacidade_C (C_l), d_lt (pas/hora), f_min e f_max (viagens/hora).
df_instancia = pd.read_csv("instancia_modelo_bhtrans.csv")

# ==========================================
# 2. RESOLUÇÃO DO MODELO (implementação em modelo.py)
# ==========================================
res = resolver_modelo(
    df_instancia,
    frota_max=FROTA_MAX,
    alpha_1=ALPHA_1,
    alpha_2=ALPHA_2,
    nome="Otimizacao_Frequencia_BHTRANS",
    log=True,
)

# ==========================================
# 3. EXTRAÇÃO E EXPORTAÇÃO DOS RESULTADOS
# ==========================================
if "detalhe" not in res:
    print("\nO modelo não encontrou solução ótima. Status:", res["status"])
else:
    print("\n" + "=" * 50)
    print("SOLUÇÃO ÓTIMA ENCONTRADA COM SUCESSO!")
    print("=" * 50)
    print(f"Valor da Função Objetivo (Z): R$ {res['valor_obj_Z']:,.2f}")
    print(f"  - Custo Operacional Total:  R$ {res['custo_operacional']:,.2f}")
    print(
        f"  - Passageiros Não Atendidos: {res['passageiros_represados']:,.0f} "
        f"de {res['demanda_total']:,} "
        f"({100 * res['passageiros_represados'] / res['demanda_total']:.1f}%)"
    )

    df_resultados = res["detalhe"]
    df_resultados.to_csv("resultados_otimizacao_bhtrans.csv", index=False)

    print("\n--- RESUMO OPERACIONAL POR LINHA (VALORES TOTAIS DIÁRIOS) ---")
    resumo = (
        df_resultados.groupby("linha")
        .agg(
            viagens_totais=("frequencia_otima", "sum"),
            demanda_total=("demanda", "sum"),
            capacidade_ofertada_total=("capacidade_ofertada", "sum"),
            passageiros_represados_totais=("passageiros_represados", "sum"),
            custo_operacional_total=("custo_operacional_R$", "sum"),
        )
        .reset_index()
    )
    print(resumo.to_string(index=False))
    print("\nArquivo detalhado 'resultados_otimizacao_bhtrans.csv' gerado com sucesso!")
