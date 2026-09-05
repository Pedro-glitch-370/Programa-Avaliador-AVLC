import importlib.util
import json
import multiprocessing
import os
import shutil
import sys
import time
import numpy as np

#função pra importar dinamicamente o arquivo .py enviado pela equipe
def carregar_modulo_aluno(caminho_arquivo_py):
    try:
        caminho_absoluto = os.path.abspath(caminho_arquivo_py)
        nome_modulo = "codigo_aluno_temp"

        spec = importlib.util.spec_from_file_location(
            nome_modulo, caminho_absoluto
        )
        if spec is None or spec.loader is None:
            return None

        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome_modulo] = modulo
        spec.loader.exec_module(modulo)
        return modulo
    except Exception as e:
        print(f"Erro na importação: {e}")
        return None

#função pra isolar e rodar o código em processo separado
def _tarefa_processo_aluno(
    caminho_arquivo_py, matriz_observada, mascara, fila_comunicacao
):
    try:
        modulo_aluno = carregar_modulo_aluno(caminho_arquivo_py)
        if not modulo_aluno or not hasattr(modulo_aluno, "principal"):
            fila_comunicacao.put({
                "status": "Erro de Estrutura",
                "mensagem_erro": (
                    "O arquivo não pôde ser importado ou não contém a função"
                    " 'principal(observada, mascara)'."
                ),
            })
            return

        inicio = time.perf_counter()
        matriz_saida = modulo_aluno.principal(matriz_observada, mascara)
        fim = time.perf_counter()

        fila_comunicacao.put({
            "status": "Executado",
            "tempo_execucao": round(fim - inicio, 6),
            "matriz_retornada": matriz_saida,
        })
    except Exception as e:
        fila_comunicacao.put(
            {"status": "Erro de Execução", "mensagem_erro": str(e)}
        )

#função pra executar o código do aluno e retornar um dict estruturado
def avaliar_submissao(
    caminho_arquivo_py, matriz_observada, mascara, gabarito_oficial, timeout_seg=3
):
    #padrão do dicionário de resultados
    resultado = {
        "status": "Erro Desconhecido",
        "tempo_execucao": 0.0,
        "erro_rmse": None,
        "mensagem_erro": None,
        "matriz_retornada": None,
    }

    #fila pra receber os dados de dentro do processo isolado
    fila_comunicacao = multiprocessing.Queue()

    #configur o processo isolado
    p = multiprocessing.Process(
        target=_tarefa_processo_aluno,
        args=(
            caminho_arquivo_py,
            matriz_observada,
            mascara,
            fila_comunicacao,
        ),
    )

    p.start()
    p.join(timeout=timeout_seg)

    #verificar se o processo estourou o timeout
    if p.is_alive():
        p.terminate()
        p.join()
        resultado["status"] = "Reprovado (Timeout excedido)"
        resultado["mensagem_erro"] = (
            f"A execução ultrapassou o limite máximo de {timeout_seg} segundos."
        )
        return resultado

    #se terminou mas a fila tá vazia, houve algum erro crítico no processo
    if fila_comunicacao.empty():
        resultado["status"] = "Erro de Execução"
        resultado["mensagem_erro"] = "O processo encerrou inesperadamente."
        return resultado

    #recuperar o que o processo isolado devolveu
    dados_execucao = fila_comunicacao.get()

    if dados_execucao["status"] != "Executado":
        resultado["status"] = dados_execucao["status"]
        resultado["mensagem_erro"] = dados_execucao.get("mensagem_erro")
        return resultado

    resultado["tempo_execucao"] = dados_execucao["tempo_execucao"]
    matriz_saida = dados_execucao["matriz_retornada"]
    resultado["matriz_retornada"] = matriz_saida

    #validar a matriz retornada pela equipe
    if not isinstance(matriz_saida, np.ndarray):
        matriz_saida = np.array(matriz_saida)

    if matriz_saida.shape != gabarito_oficial.shape:
        resultado["status"] = "Reprovado (Dimensões Incorretas)"
        return resultado

    if np.isnan(matriz_saida).any():
        resultado["status"] = "Reprovado (Contém valores NaNs)"
        return resultado

    #calcular erro agregado
    posicoes_ocultas = ~mascara
    if not posicoes_ocultas.any():
        resultado["status"] = "Aviso: Nenhuma posição oculta encontrada."
        resultado["erro_rmse"] = 0.0
    else:
        valores_aluno = matriz_saida[posicoes_ocultas]
        valores_gabarito = gabarito_oficial[posicoes_ocultas]

        #RMSE (Raiz do Erro Quadrático Médio)
        mse = np.mean((valores_aluno - valores_gabarito) ** 2)
        rmse = np.sqrt(mse)

        resultado["status"] = "Sucesso"
        resultado["erro_rmse"] = round(float(rmse), 4)

    return resultado

#função pra salvar o código da equipe e seu resultado na devida pasta
def salvar_submissao_equipe(
    numero_equipe, caminho_codigo_enviado, resultado_avaliacao
):
    diretorio_base = "submissoes_armazenadas"
    nome_pasta_equipe = f"equipe_{numero_equipe}"
    diretorio_equipe = os.path.join(diretorio_base, nome_pasta_equipe)
    os.makedirs(diretorio_equipe, exist_ok=True)

    #copiar o código .py enviado
    destino_codigo = os.path.join(diretorio_equipe, "codigo_submetido.py")
    shutil.copy(caminho_codigo_enviado, destino_codigo)

    #converte numpy array para lista pra poder salvamento em JSON
    resultado_para_json = resultado_avaliacao.copy()
    if (
        "matriz_retornada" in resultado_para_json
        and resultado_para_json["matriz_retornada"] is not None
    ):
        if isinstance(resultado_para_json["matriz_retornada"], np.ndarray):
            resultado_para_json["matriz_retornada"] = resultado_para_json["matriz_retornada"].tolist()

    #salvar o JSON estruturado
    caminho_json = os.path.join(diretorio_equipe, "resultado.json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(resultado_para_json, f, indent=4, ensure_ascii=False)

#bloco de teste mockado
if __name__ == "__main__":

    #criar dados mockados oficiais
    gabarito_mock = np.array([[2.0, 5.0, 1.0], [4.0, 8.0, 6.0], [7.0, 3.0, 9.0]])
    mascara_mock = np.array([[True, False, True], [False, True, False], [True, False, True]])
    observada_mock = np.where(mascara_mock, gabarito_mock, np.nan)

    #teste do timeout de 3 segundos
    codigo_exemplo_aluno = """
import numpy as np
def principal(observada, mascara):
    # Simulando um código normal que roda rápido
    gabarito_perfeito = np.array([[2.0, 5.0, 1.0], [4.0, 8.0, 6.0], [7.0, 3.0, 9.0]])
    return gabarito_perfeito
"""
    with open("solucao_aluno_mock.py", "w") as f:
        f.write(codigo_exemplo_aluno)

    #simulando com equipe 1
    id_equipe = 1
    res = avaliar_submissao(
        "solucao_aluno_mock.py", observada_mock, mascara_mock, gabarito_mock, timeout_seg=3
    )
    salvar_submissao_equipe(id_equipe, "solucao_aluno_mock.py", res)

    print("\nResultado do Avaliador:")
    for chave, valor in res.items():
        if chave == "tempo_execucao" and valor is not None:
            print(f"  {chave}: {valor:.6f}")
        else:
            print(f"  {chave}: {valor}")

    #teste com loop infinito
    codigo_loop_infinito = """
import time
def principal(observada, mascara):
    while True:
        time.sleep(1)
"""
    with open("solucao_aluno_timeout.py", "w") as f:
        f.write(codigo_loop_infinito)

    #simulando com equipe 2
    id_equipe = 2
    res_timeout = avaliar_submissao(
        "solucao_aluno_timeout.py",
        observada_mock,
        mascara_mock,
        gabarito_mock,
        timeout_seg=2,
    )
    salvar_submissao_equipe(id_equipe, "solucao_aluno_timeout.py", res)

    print("\nResultado do Avaliador:")
    for chave, valor in res_timeout.items():
        print(f"  {chave}: {valor}")