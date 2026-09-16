import numpy as np

def principal(observada, mascara):
    """
    Abordagem Avançada: Preenchimento iterativo de matrizes (Matrix Completion)
    utilizando SVD truncado em múltiplos ciclos.
    """
    X = observada.copy()
    
    # Inicializa NaNs com a média global
    val_media = np.nanmean(X)
    if np.isnan(val_media):
        val_media = 0.0
    X[np.isnan(X)] = val_media
    
    # Configurações do algoritmo iterativo
    max_iteracoes = 15
    posto_alvo = min(X.shape[0], X.shape[1], 4)
    
    for _ in range(max_iteracoes):
        # Decomposição SVD
        U, s, Vt = np.linalg.svd(X, full_matrices=False)
        
        # Trunca o espectro mantendo os maiores valores singulares
        s_trunc = s.copy()
        if len(s_trunc) > posto_alvo:
            s_trunc[posto_alvo:] = 0.0
            
        # Reconstrói a matriz intermediária
        X_reconstruido = np.dot(U[:, :len(s_trunc)] * s_trunc, Vt[:len(s_trunc), :])
        
        # Mistura: Mantém os dados reais onde a máscara é 1, atualiza com a predição onde é 0
        X = np.where(mascara == 1, observada, X_reconstruido)
        
    # Garante ausência total de NaNs no retorno final
    X[np.isnan(X)] = val_media
    
    return X