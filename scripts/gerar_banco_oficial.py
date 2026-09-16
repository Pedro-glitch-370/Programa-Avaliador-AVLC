import os
import numpy as np

def criar_banco_oficial():
    # Cria um diretório separado e sigiloso para a avaliação final
    pasta_saida = "banco_oficial"
    os.makedirs(pasta_saida, exist_ok=True)
    
    # Semente diferente da pública (ex: 12345) para garantir valores inéditos
    np.random.seed(12345)  
    
    def salvar_amostra(idx, gabarito, mascara):
        # Injeta NaN nos locais ausentes com base na máscara
        observada = gabarito.astype(float).copy()
        observada[mascara == 0] = np.nan
        
        np.save(os.path.join(pasta_saida, f"gabarito_{idx:02d}.npy"), gabarito)
        np.save(os.path.join(pasta_saida, f"mascara_{idx:02d}.npy"), mascara.astype(int))
        np.save(os.path.join(pasta_saida, f"observada_{idx:02d}.npy"), observada)

    print("Gerando o lote de 10 matrizes oficiais (sigilosas)...")

    # ==========================================
    # NÍVEL BÁSICO: Média Simples (Matrizes 1 a 3)
    # ==========================================
    
    # 1. Média Global (Nova média base e desvio)
    gab_1 = 75.0 + np.random.normal(0, 3, size=(12, 12))
    mask_1 = np.random.choice([0, 1], size=(12, 12), p=[0.25, 0.75])
    salvar_amostra(1, gab_1, mask_1)

    # 2. Média por Linha
    base_linhas = np.linspace(20, 120, 12)[:, np.newaxis]
    gab_2 = base_linhas + np.random.normal(0, 1.5, size=(12, 12))
    mask_2 = np.random.choice([0, 1], size=(12, 12), p=[0.2, 0.8])
    salvar_amostra(2, gab_2, mask_2)

    # 3. Média por Coluna
    base_colunas = np.linspace(10, 80, 12)[np.newaxis, :]
    gab_3 = base_colunas + np.random.normal(0, 1.2, size=(12, 12))
    mask_3 = np.random.choice([0, 1], size=(12, 12), p=[0.3, 0.7])
    salvar_amostra(3, gab_3, mask_3)

    # ==========================================
    # NÍVEL INTERMEDIÁRIO: Mínimos Quadrados & SVD (Matrizes 4 a 7)
    # ==========================================

    # 4 e 5. Mínimos Quadrados (Novas funções e dimensões)
    x = np.linspace(-4, 4, 14)
    # Matriz 4: Relação linear y = -1.5x + 5
    gab_4 = np.outer(x, [-1.5]) + 5.0 + np.random.normal(0, 0.15, size=(14, 7))
    mask_4 = np.random.choice([0, 1], size=(14, 7), p=[0.2, 0.8])
    salvar_amostra(4, gab_4, mask_4)

    # Matriz 5: Relação cúbica y = 0.5*x^3 - 2x
    gab_5 = np.outer(0.5*(x**3) - 2*x, [1.0]) + np.random.normal(0, 0.25, size=(14, 9))
    mask_5 = np.random.choice([0, 1], size=(14, 9), p=[0.25, 0.75])
    salvar_amostra(5, gab_5, mask_5)

    # 6 e 7. Aproximação de Baixo Posto (Low-Rank Matrices)
    U6 = np.random.randn(16, 3)
    V6 = np.random.randn(3, 16)
    gab_6 = np.dot(U6, V6) + np.random.normal(0, 0.08, size=(16, 16))
    mask_6 = np.random.choice([0, 1], size=(16, 16), p=[0.35, 0.65])
    salvar_amostra(6, gab_6, mask_6)

    U7 = np.random.randn(18, 4)
    V7 = np.random.randn(4, 18)
    gab_7 = np.dot(U7, V7) + np.random.normal(0, 0.12, size=(18, 18))
    mask_7 = np.random.choice([0, 1], size=(18, 18), p=[0.3, 0.7])
    salvar_amostra(7, gab_7, mask_7)

    # ==========================================
    # NÍVEL AVANÇADO: SVD Completo & Fatoração Matricial (Matrizes 8 a 10)
    # ==========================================

    # 8. SVD Espectral Avançado
    A_base = np.random.randn(18, 18)
    U_s, _, Vt_s = np.linalg.svd(A_base)
    s = np.linspace(80, 2, 18)
    gab_8 = np.dot(U_s * s, Vt_s)
    mask_8 = np.random.choice([0, 1], size=(18, 18), p=[0.3, 0.7])
    salvar_amostra(8, gab_8, mask_8)

    # 9 e 10. Fatoração Matricial (Fatores Latentes)
    U9 = np.random.uniform(0.8, 3.5, size=(28, 5))
    V9 = np.random.uniform(0.8, 3.5, size=(5, 22))
    gab_9 = np.dot(U9, V9)
    mask_9 = np.random.choice([0, 1], size=(28, 22), p=[0.4, 0.6])
    salvar_amostra(9, gab_9, mask_9)

    U10 = np.random.uniform(1.0, 4.0, size=(32, 6))
    V10 = np.random.uniform(1.0, 4.0, size=(6, 32))
    gab_10 = np.dot(U10, V10)
    mask_10 = np.random.choice([0, 1], size=(32, 32), p=[0.45, 0.55])
    salvar_amostra(10, gab_10, mask_10)

    print(f"Sucesso! 10 matrizes oficiais geradas na pasta sigilosa '{pasta_saida}/'.")

if __name__ == "__main__":
    criar_banco_oficial()