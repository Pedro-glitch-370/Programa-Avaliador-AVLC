import os
import numpy as np

def criar_banco_publico():
  pasta_banco = "banco_publico"
  os.makedirs(pasta_banco, exist_ok=True)

  print(
      f"Gerando o lote público de 10 matrizes de exemplo na pasta"
      f" '{pasta_banco}/'..."
  )

  # Semente diferente do banco oficial, garantindo que sejam matrizes inéditas,
  # mas com a mesma estrutura e nível de complexidade.
  np.random.seed(2026)

  total_matrizes = 10

  for i in range(1, total_matrizes + 1):
    # Variação de dimensões compatível com o banco oficial (entre 6x6 e 12x12)
    m = np.random.randint(6, 13)
    n = np.random.randint(6, 13)

    # Fatores lineares para manter a propriedade de posto baixo
    fator1 = np.random.randn(m, 2)
    fator2 = np.random.randn(2, n)
    gabarito_publico = (fator1 @ fator2) * np.random.uniform(1.0, 10.0)

    # Máscara booleana com taxa de visibilidade semelhante (60% a 85%)
    taxa_visivel = np.random.uniform(0.6, 0.85)
    mascara = np.random.rand(m, n) < taxa_visivel

    # Matriz observada com NaNs nos buracos
    observada = gabarito_publico.copy()
    observada[~mascara] = np.nan

    # Salvando os arquivos públicos para os alunos
    prefixo = f"exemplo_{i:02d}"
    np.save(os.path.join(pasta_banco, f"{prefixo}_observada.npy"), observada)
    np.save(os.path.join(pasta_banco, f"{prefixo}_mascara.npy"), mascara)
    np.save(os.path.join(pasta_banco, f"{prefixo}_gabarito.npy"), gabarito_publico)

  print(
      f"Sucesso! {total_matrizes} matrizes públicas de exemplo criadas em"
      f" '{pasta_banco}/'."
  )

if __name__ == "__main__":
  criar_banco_publico()