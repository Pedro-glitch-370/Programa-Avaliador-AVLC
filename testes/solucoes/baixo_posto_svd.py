import numpy as np

def principal(observada, mascara):
    """
    Abordagem Intermediária: Usa SVD Truncado para aproximação de baixo posto.
    """
    resultado = observada.copy()
    
    # Passo 1: Inicializa os NaNs com a média por coluna para evitar falhas no SVD
    medias_coluna = np.nanmean(resultado, axis=0)
    for j in range(resultado.shape[1]):
        val = medias_coluna[j]
        if np.isnan(val):
            val = 0.0
        resultado[np.isnan(resultado[:, j]), j] = val
        
    # Passo 2: Aplica SVD na matriz preenchida
    U, s, Vt = np.linalg.svd(resultado, full_matrices=False)
    
    # Mantém apenas os componentes principais mais relevantes (ex: posto k = 3)
    k = min(3, len(s))
    resultado_reconstruido = np.dot(U[:, :k] * s[:k], Vt[:k, :])
    
    # Passo 3: Preserva estritamente os dados originais onde a máscara é 1 (conhecidos)
    final = observada.copy()
    final[mascara == 0] = resultado_reconstruido[mascara == 0]
    
    # Tratamento de segurança final para qualquer NaN residual
    final[np.isnan(final)] = 0.0
    
    return final