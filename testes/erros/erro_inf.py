import numpy as np

def principal(observada, mascara):
    # Cria uma cópia da matriz observada e injeta um valor infinito (Inf) ou NaN
    resultado = observada.copy()
    
    # Força um erro matemático gerando um infinito (ex: divisão por zero)
    # ou insira diretamente um valor inválido:
    resultado[0, 0] = np.inf 
    
    return resultado