import numpy as np

def principal(observada, mascara):
    # Copia a matriz, mas deixa os buracos intactos (com NaN)
    saida = observada.copy()
    return saida