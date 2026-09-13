import os
import numpy as np


def criar_banco_oficial():
  # Nome da pasta solicitada
  pasta_banco = "banco_oficial"
  os.makedirs(pasta_banco, exist_ok=True)

  print(
      f"Gerando o lote oficial de matrizes na pasta '{pasta_banco}/'..."
  )

  # Semente fixa para garantir que o banco oficial gerado seja determinístico e igual sempre
  np.random.seed(101)

  total_matrizes = 10

  for i in range(1, total_matrizes + 1):
    # Variação de dimensões entre 6x6 e 12x12
    m = np.random.randint(6, 13)
    n = np.random.randint(6, 13)

    # Criação de fatores lineares para garantir matrizes de posto baixo (ideal para SVD/Álgebra Linear)
    fator1 = np.random.randn(m, 2)
    fator2 = np.random.randn(2, n)
    gabarito_real = (fator1 @ fator2) * np.random.uniform(1.0, 10.0)

    # Define a máscara booleana (True = dado visível, False = buraco/ausente)
    # Varia a taxa de dados visíveis entre 60% e 85%
    taxa_visivel = np.random.uniform(0.6, 0.85)
    mascara = np.random.rand(m, n) < taxa_visivel

    # Cria a matriz observada substituindo as posições ocultas por NaN
    observada = gabarito_real.copy()
    observada[~mascara] = np.nan

    # Nomes padronizados dos arquivos para cada matriz do lote
    prefixo = f"matriz_{i:02d}"
    np.save(os.path.join(pasta_banco, f"{prefixo}_observada.npy"), observada)
    np.save(os.path.join(pasta_banco, f"{prefixo}_mascara.npy"), mascara)
    np.save(os.path.join(pasta_banco, f"{prefixo}_gabarito.npy"), gabarito_real)

  print(
      f"Sucesso! {total_matrizes} conjuntos de matrizes criados e salvos em"
      f" '{pasta_banco}/'."
  )


if __name__ == "__main__":
  criar_banco_oficial()