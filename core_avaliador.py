import importlib.util
import json
import os
import shutil
import sys
import time
import numpy as np
import multiprocessing

#função pra executar o código da equipe contra todas as matrizes
def _tarefa_lote_processo(caminho_arquivo_py, banco_10_matrizes, fila_comunicacao):
    try:
        #localizar o arquivo .py enviado pelo aluno pelo caminho absoluto
        caminho_absoluto = os.path.abspath(caminho_arquivo_py)
        nome_modulo = "codigo_aluno_temp"

        spec = importlib.util.spec_from_file_location(nome_modulo, caminho_absoluto)

        #capturar erro de sintaxe
        if spec is None or spec.loader is None:
            fila_comunicacao.put({
                "status_geral": "Erro de Estrutura",
                "mensagem_erro": "O arquivo não pôde ser importado.",
            })
            return

        #carregar dinamicamente em memória como se fosse um módulo comum
        modulo_aluno = importlib.util.module_from_spec(spec)
        sys.modules[nome_modulo] = modulo_aluno
        spec.loader.exec_module(modulo_aluno)

        #validar se o script tem a função chamada principal
        if not hasattr(modulo_aluno, "principal"):
            fila_comunicacao.put({
                "status_geral": "Erro de Estrutura",
                "mensagem_erro": "O arquivo não contém a função 'principal(observada, mascara)'.",
            })
            return

        #listas de controle
        detalhes_por_matriz = []
        nrmses_validos = []
        tempo_total = 0.0

        #iterar pelas 10 matrizes no mesmo processo
        for idx, dados_matriz in enumerate(banco_10_matrizes):
            obs = dados_matriz["observada"]
            mascara = dados_matriz["mascara"]
            gabarito = dados_matriz["gabarito"]

            #cronômetro e output
            inicio = time.perf_counter()
            try:
                matriz_saida = modulo_aluno.principal(obs, mascara)
            except Exception as e:
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Erro de Execução",
                    "mensagem_erro": str(e),
                })
                return
            fim = time.perf_counter()

            tempo_exec = fim - inicio
            tempo_total += tempo_exec

            #converter o output em array do NumPy
            if not isinstance(matriz_saida, np.ndarray):
                matriz_saida = np.array(matriz_saida)

            #comparar dimensões com as do gabarito
            if matriz_saida.shape != gabarito.shape:
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Dimensões Incorretas",
                    "mensagem_erro": f"Esperado {gabarito.shape}. Retornado {matriz_saida.shape}.",
                })
                return

            #procurar por valores infinitos
            if not np.isfinite(matriz_saida).all():
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Contém Valores Inválidos (Inf)",
                    "mensagem_erro": "A matriz retornada possui valores infinitos (Inf).",
                })
                return

            #procurar por 'Not a Number's
            if np.isnan(matriz_saida).any():
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Contém Valores NaNs",
                    "mensagem_erro": "A matriz retornada possui valores NaN não preenchidos.",
                })
                return

            #calcular o NRMSE nas posições ocultas
            posicoes_ocultas = ~mascara
            if not posicoes_ocultas.any():
                nrmse = 0.0
                rmse_bruto = 0.0
            else:
                valores_aluno = matriz_saida[posicoes_ocultas]
                valores_gabarito = gabarito[posicoes_ocultas]

                rmse = np.sqrt(np.mean((valores_aluno - valores_gabarito) ** 2))
                amplitude = np.max(gabarito) - np.min(gabarito)
                nrmse = rmse / amplitude if amplitude > 0 else rmse

            nrmses_validos.append(nrmse)
            detalhes_por_matriz.append({
                "matriz_id": idx + 1,
                "status": "Sucesso",
                "tempo": round(tempo_exec, 6),
                "rmse_bruto": round(float(rmse), 6),
                "nrmse": round(float(nrmse), 6),
            })

        nrmse_medio = np.mean(nrmses_validos) if nrmses_validos else 0.0

        #retornar pra aplicação um relatório completo de sucesso
        fila_comunicacao.put({
            "status_geral": "Sucesso",
            "nrmse_medio_agregado": round(float(nrmse_medio), 6),
            "tempo_total_acumulado": round(tempo_total, 6),
            "detalhes_por_matriz": detalhes_por_matriz,
            "mensagem_erro": None,
        })

    except Exception as e:
        fila_comunicacao.put({
            "status_geral": "Erro Crítico de Processamento",
            "mensagem_erro": str(e),
        })

#função que orquestra um único processo isolado para a avaliação das matrizes
def avaliar_todas_as_matrizes(caminho_arquivo_py, banco_10_matrizes, timeout_total_seg=3):
    
    #cria um contexto de multiprocessamento configurado por spawn
    ctx = multiprocessing.get_context("spawn")
    #criar fila segura entre processos do contexto
    fila_comunicacao = ctx.Queue()

    #instanciar o objeto do processo
    p = ctx.Process(
        target=_tarefa_lote_processo,
        args=(caminho_arquivo_py, banco_10_matrizes, fila_comunicacao),
    )

    #iniciar a execução do processo e travar a thread principal até acabar
    p.start()
    p.join(timeout=timeout_total_seg)

    #matar o processo à força se o cronômetro estourar
    if p.is_alive():
        p.terminate()
        p.join()
        return {
            "status_geral": "Timeout Excedido",
            "nrmse_medio_agregado": None,
            "tempo_total_acumulado": timeout_total_seg,
            "detalhes_por_matriz": [],
            "mensagem_erro": f"A execução total ultrapassou o limite de {timeout_total_seg} segundos para o lote.",
        }

    #capturar falha abrupta
    if fila_comunicacao.empty():
        return {
            "status_geral": "Erro de Execução",
            "nrmse_medio_agregado": None,
            "tempo_total_acumulado": 0.0,
            "detalhes_por_matriz": [],
            "mensagem_erro": "O processo encerrou inesperadamente.",
        }

    #retornar relatório de sucesso
    return fila_comunicacao.get()

#função pra salvar o código enviado e registrar o histórico localmente
def salvar_historico_local(caminho_codigo_enviado, relatorio, equipe_id):
    
    #criar o armazenamento persistente das submissões
    diretorio_base = "historico_local_tentativas"
    diretorio_base = os.path.join(diretorio_base, f"equipe_{equipe_id}")
    os.makedirs(diretorio_base, exist_ok=True)

    #carregar a lista de tentativas anteriores de historico.json para a memória
    caminho_historico = os.path.join(diretorio_base, "historico.json")
    historico_geral = []

    if os.path.exists(caminho_historico):
        try:
            with open(caminho_historico, "r", encoding="utf-8") as f:
                historico_geral = json.load(f)
        except Exception:
            historico_geral = []

    #copiar o arquivo .py para a pasta de histórico
    timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S")
    nome_codigo_salvo = f"codigo_{timestamp_str}.py"
    shutil.copy(caminho_codigo_enviado, os.path.join(diretorio_base, nome_codigo_salvo))

    #empacotar os metadados da tentativa e adicionar ao histórico geral
    nova_entrada = {
        "equipe_id": equipe_id,
        "timestamp": timestamp_str,
        "arquivo_codigo": nome_codigo_salvo,
        "resultado": relatorio,
    }
    historico_geral.append(nova_entrada)

    #sobrescrever o historico.json
    with open(caminho_historico, "w", encoding="utf-8") as f:
        json.dump(historico_geral, f, indent=4, ensure_ascii=False)