import numpy as np

def principal(observada, mascara):
    saida = observada.copy()
    
    # Extrai apenas os valores válidos indicados pela máscara
    valores_validos = observada[mascara]
    
    # Verifica se existem valores válidos para evitar erro de computação
    if valores_validos.size > 0:
        media = np.nanmean(valores_validos)
    else:
        media = 0.0  # Fallback seguro caso a máscara venha vazia
    
    # Se a média calculada for NaN ou infinita, define um valor neutro seguro
    if not np.isfinite(media):
        media = 0.0
        
    # Preenche os espaços vazios (~mascara) com a média segura
    saida[~mascara] = media
    
    # Garantia final: substitui qualquer infinito restante na matriz por 0.0 ou outro valor seguro
    saida[~np.isfinite(saida)] = 0.0
    
    return saida