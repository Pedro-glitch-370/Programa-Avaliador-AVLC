import numpy as np

def principal(observada, mascara):
    """
    Abordagem Básica: Preenche os valores ausentes com a média global
    dos dados disponíveis.
    """
    resultado = observada.copy()
    
    # Calcula a média apenas dos valores não nulos
    media_global = np.nanmean(resultado)
    
    # Se toda a matriz for NaN por algum motivo extremo, usa 0.0 como fallback
    if np.isnan(media_global):
        media_global = 0.0
        
    # Substitui os NaNs pela média
    resultado[np.isnan(resultado)] = media_global
    
    return resultado