import numpy as np

def principal(observada, mascara):
  """Função principal obrigatória para o Torneio de Álgebra Linear.

  Parâmetros:
      observada (np.ndarray): Matriz com valores conhecidos e NaNs nos buracos.
      mascara (np.ndarray): Matriz booleana (True = conhecido, False = buraco).

  Retorna:
      np.ndarray: A matriz preenchida (sem nenhum valor NaN).
  """
  # Cria uma cópia de trabalho para evitar mutações diretas
  X = observada.copy()

  # Imputação inicial: substitui os NaNs (False na máscara) pela média dos valores válidos
  media_valida = np.nanmean(X)
  X[~mascara] = media_valida

  # Parâmetros da otimização iterativa
  max_iter = 30
  posto_alvo = 2  # Posto estimado para o truncamento da SVD

  for _ in range(max_iter):
    # Aplica a Decomposição em Valores Singulares (SVD)
    U, s, Vt = np.linalg.svd(X, full_matrices=False)

    # Truncamento de posto (mantém apenas as maiores componentes singulares)
    S = np.diag(s)
    if len(s) > posto_alvo:
      S[posto_alvo:, posto_alvo:] = 0

    # Reconstrói a matriz aproximada de baixo posto
    X_reconstruida = U @ S @ Vt

    # Restringe a atualização: preserva os dados originais conhecidos e preenche apenas os buracos
    X[~mascara] = X_reconstruida[~mascara]

  # Retorna a matriz completamente preenchida e limpa de NaNs
  return X