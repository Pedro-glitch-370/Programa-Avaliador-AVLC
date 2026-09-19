import json
import os
import shutil
import time
import numpy as np
import multiprocessing
import sys
from funcoes_suporte import validar_seguranca_codigo
from sandbox_restrito import compilar_e_extrair_principal, ViolacaoSandbox
from banco import salvar_tentativa, inicializar_banco

if sys.platform != "win32":
    import resource
else:
    resource = None

inicializar_banco()

#função pra executar o código da equipe contra todas as matrizes
def _tarefa_lote_processo(equipe_id, caminho_arquivo_py, banco_10_matrizes, fila_comunicacao, timestamp_str):
    #definindo o limite de memória RAM
    if resource is not None:
        try:
            limite_bytes = 512 * 1024 * 1024 #512 MB
            resource.setrlimit(resource.RLIMIT_AS, (limite_bytes, limite_bytes))

        except (ValueError, OSError) as e:
            print(f"Não foi possível definir o limite de memória: {e}")
            
    try:
        #localizar o arquivo .py enviado pelo aluno pelo caminho absoluto
        caminho_absoluto = os.path.abspath(caminho_arquivo_py)

        #validar a segurança
        valido, mensagem_seguranca = validar_seguranca_codigo(caminho_absoluto)
        if not valido:
            fila_comunicacao.put({
                "status_geral": "Reprovado por Violação de Segurança",
                "mensagem_erro": f"O código contém elementos proibidos: {mensagem_seguranca}",
            })
            return

        #ler o código-fonte como texto, compilar e executar em um namespace restrito
        with open(caminho_absoluto, "r", encoding="utf-8") as arquivo_codigo:
            codigo_fonte = arquivo_codigo.read()

        try:
            principal = compilar_e_extrair_principal(codigo_fonte)
        except SyntaxError as e:
            fila_comunicacao.put({
                "status_geral": "Erro de Estrutura",
                "mensagem_erro": f"Erro de sintaxe: {e}",
            })
            return
        except ViolacaoSandbox as e:
            fila_comunicacao.put({
                "status_geral": "Reprovado por Violação de Segurança",
                "mensagem_erro": str(e),
            })
            return
        except AttributeError as e:
            fila_comunicacao.put({
                "status_geral": "Erro de Estrutura",
                "mensagem_erro": str(e),
            })
            return

        #listas de controle
        detalhes_por_matriz = []
        nrmses_validos = []
        tempo_total = 0.0

        #diretório para salvar as saídas da equipe
        pasta_saidas = os.path.join("historico_local_tentativas", f"equipe_{equipe_id}", f"tentativa_{timestamp_str}", "saidas")
        os.makedirs(pasta_saidas, exist_ok=True)

        #iterar pelas 10 matrizes no mesmo processo
        for idx, dados_matriz in enumerate(banco_10_matrizes):
            obs = dados_matriz["observada"]
            mascara = dados_matriz["mascara"]
            gabarito = dados_matriz["gabarito"]

            #cronômetro e output
            inicio = time.perf_counter()
            try:
                matriz_saida = principal(obs, mascara)
            except ViolacaoSandbox as e:
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Violação de Segurança",
                    "mensagem_erro": str(e),
                })
                return
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

            #procurar por 'Not a Number's
            if np.isnan(matriz_saida).any():
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Contém Valores NaNs",
                    "mensagem_erro": "A matriz retornada possui valores NaN não preenchidos.",
                })
                return

            #procurar por valores infinitos
            if not np.isfinite(matriz_saida).all():
                fila_comunicacao.put({
                    "status_geral": f"Reprovado na Matriz #{idx + 1}: Contém Valores Inválidos (Inf)",
                    "mensagem_erro": "A matriz retornada possui valores infinitos (Inf).",
                })
                return

            #salvar a matriz para visualização
            np.save(os.path.join(pasta_saidas, f"saida_{idx + 1}.npy"), matriz_saida)

            #calcular o NRMSE nas posições ocultas
            posicoes_ocultas = ~mascara
            if not posicoes_ocultas.any():
                nrmse = 0.0
                rmse = 0.0
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
def avaliar_todas_as_matrizes(equipe_id, caminho_arquivo_py, banco_10_matrizes, timestamp_str, timeout_total_seg=30):
    
    #cria um contexto de multiprocessamento configurado por spawn
    ctx = multiprocessing.get_context("spawn")
    #criar fila segura entre processos do contexto
    fila_comunicacao = ctx.Queue()

    #instanciar o objeto do processo
    p = ctx.Process(
        target=_tarefa_lote_processo,
        args=(equipe_id, caminho_arquivo_py, banco_10_matrizes, fila_comunicacao, timestamp_str),
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
    p.close()

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

#função pra salvar o código enviado e registrar o histórico
def salvar_historico_local(caminho_codigo_enviado, relatorio, equipe_id, timestamp_str):
    
    #criar o armazenamento persistente das submissões
    diretorio_base = os.path.join("historico_local_tentativas", f"equipe_{equipe_id}", f"tentativa_{timestamp_str}")
    os.makedirs(diretorio_base, exist_ok=True)

    #copiar o arquivo .py para a pasta de histórico
    nome_codigo_salvo = f"codigo_{timestamp_str}.py"
    caminho_destino_codigo = os.path.join(diretorio_base, nome_codigo_salvo)
    shutil.copy(caminho_codigo_enviado, caminho_destino_codigo)

    #extrair os dados do relatório retornado
    status_geral = relatorio.get("status_geral", "mensagem_erro")
    nrmse = relatorio.get("nrmse_medio_agregado", 0.0)
    if nrmse is None:
        nrmse = 0.0
    
    tempo_total = relatorio.get("tempo_total_acumulado", 0.0)
    detalhes = relatorio.get("detalhes_por_matriz")

    #empacotar os metadados da tentativa e adicionar ao histórico geral
    salvar_tentativa(
        equipe_id=str(equipe_id),
        timestamp=timestamp_str,
        arquivo_codigo=caminho_destino_codigo,
        status_geral=status_geral,
        nrmse=float(nrmse),
        tempo_total=float(tempo_total),
        detalhes=detalhes
    )