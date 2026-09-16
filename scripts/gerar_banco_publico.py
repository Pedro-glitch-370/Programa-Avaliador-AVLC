import os
import numpy as np

def criar_banco_mock():
    # Cria o diretório para salvar as matrizes públicas
    pasta_saida = "banco_publico"
    os.makedirs(pasta_saida, exist_ok=True)
    
    np.random.seed(42)  # Garante reprodutibilidade
    
    def salvar_amostra(idx, gabarito, mascara):
        # Cria a matriz observada injetando NaN nos locais onde a máscara é 0
        observada = gabarito.astype(float).copy()
        observada[mascara == 0] = np.nan
        
        np.save(os.path.join(pasta_saida, f"gabarito_{idx:02d}.npy"), gabarito)
        np.save(os.path.join(pasta_saida, f"mascara_{idx:02d}.npy"), mascara.astype(int))
        np.save(os.path.join(pasta_saida, f"observada_{idx:02d}.npy"), observada)

    print("Gerando o banco de 10 matrizes públicas...")

    # ==========================================
    # NÍVEL BÁSICO: Média Simples (Matrizes 1 a 3)
    # ==========================================
    
    # 1. Média Global (Valores em torno de uma constante com pequeno ruído)
    gab_1 = 50.0 + np.random.normal(0, 2, size=(10, 10))
    mask_1 = np.random.choice([0, 1], size=(10, 10), p=[0.2, 0.8])
    salvar_amostra(1, gab_1, mask_1)

    # 2. Média por Linha (Cada linha tem um comportamento base diferente)
    base_linhas = np.linspace(10, 100, 10)[:, np.newaxis]
    gab_2 = base_linhas + np.random.normal(0, 1, size=(10, 10))
    mask_2 = np.random.choice([0, 1], size=(10, 10), p=[0.25, 0.75])
    salvar_amostra(2, gab_2, mask_2)

    # 3. Média por Coluna (Cada coluna tem uma tendência média própria)
    base_colunas = np.linspace(5, 50, 10)[np.newaxis, :]
    gab_3 = base_colunas + np.random.normal(0, 1, size=(10, 10))
    mask_3 = np.random.choice([0, 1], size=(10, 10), p=[0.2, 0.8])
    salvar_amostra(3, gab_3, mask_3)

    # ==========================================
    # NÍVEL INTERMEDIÁRIO: Mínimos Quadrados & SVD (Matrizes 4 a 7)
    # ==========================================

    # 4 e 5. Mínimos Quadrados (Sistemas lineares e ajustes polinomiais em formato matricial)
    x = np.linspace(-3, 3, 12)
    # Matriz 4: Relação linear y = 2x + 3
    gab_4 = np.outer(x, [2.0]) + 3.0 + np.random.normal(0, 0.1, size=(12, 6))
    mask_4 = np.random.choice([0, 1], size=(12, 6), p=[0.15, 0.85])
    salvar_amostra(4, gab_4, mask_4)

    # Matriz 5: Relação quadrática y = x^2
    gab_5 = np.outer(x**2, [1.0]) + np.random.normal(0, 0.2, size=(12, 8))
    mask_5 = np.random.choice([0, 1], size=(12, 8), p=[0.2, 0.8])
    salvar_amostra(5, gab_5, mask_5)

    # 6 e 7. Aproximação de Baixo Posto (Low-Rank Matrices - ex: PCA / SVD Truncado)
    # Geradas pelo produto de matrizes de rank reduzido (ex: rank 2 e rank 3)
    U6 = np.random.randn(15, 2)
    V6 = np.random.randn(2, 15)
    gab_6 = np.dot(U6, V6) + np.random.normal(0, 0.05, size=(15, 15))
    mask_6 = np.random.choice([0, 1], size=(15, 15), p=[0.3, 0.7])
    salvar_amostra(6, gab_6, mask_6)

    U7 = np.random.randn(20, 3)
    V7 = np.random.randn(3, 20)
    gab_7 = np.dot(U7, V7) + np.random.normal(0, 0.1, size=(20, 20))
    mask_7 = np.random.choice([0, 1], size=(20, 20), p=[0.3, 0.7])
    salvar_amostra(7, gab_7, mask_7)

    # ==========================================
    # NÍVEL AVANÇADO: SVD Completo & Fatoração Matricial (Matrizes 8 a 10)
    # ==========================================

    # 8. SVD Espectral Avançado (Matriz com autovalores bem definidos)
    A_base = np.random.randn(15, 15)
    U_s, _, Vt_s = np.linalg.svd(A_base)
    # Força espectro decrescente
    s = np.linspace(50, 1, 15)
    gab_8 = np.dot(U_s * s, Vt_s)
    mask_8 = np.random.choice([0, 1], size=(15, 15), p=[0.25, 0.75])
    salvar_amostra(8, gab_8, mask_8)

    # 9 e 10. Fatoração Matricial (Estilo Sistemas de Recomendação / Fatores Latentes U * V)
    # Matriz 9: Fatoração de rank 4 (usuários x itens simulados)
    U9 = np.random.uniform(1, 3, size=(25, 4))
    V9 = np.random.uniform(1, 3, size=(4, 20))
    gab_9 = np.dot(U9, V9)
    mask_9 = np.random.choice([0, 1], size=(25, 20), p=[0.35, 0.65]) # Alta esparsidade
    salvar_amostra(9, gab_9, mask_9)

    # Matriz 10: Fatoração Matricial de maior complexidade (Rank 5 com esparsidade desafiadora)
    U10 = np.random.uniform(0.5, 2.5, size=(30, 5))
    V10 = np.random.uniform(0.5, 2.5, size=(5, 30))
    gab_10 = np.dot(U10, V10)
    mask_10 = np.random.choice([0, 1], size=(30, 30), p=[0.4, 0.6])
    salvar_amostra(10, gab_10, mask_10)

    print(f"Sucesso! 10 conjuntos de matrizes gerados na pasta '{pasta_saida}/'.")

if __name__ == "__main__":
    criar_banco_mock()