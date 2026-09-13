import importlib.util
import json
import os
import shutil
import sys
import time
import numpy as np
import multiprocessing


def _tarefa_lote_processo(caminho_arquivo_py, banco_10_matrizes, fila_comunicacao):
  """Executa o código do aluno contra todas as matrizes em um único processo."""
  try:
    # Importação dinâmica do código do aluno (feita apenas 1 vez)
    caminho_absoluto = os.path.abspath(caminho_arquivo_py)
    nome_modulo = "codigo_aluno_temp"

    spec = importlib.util.spec_from_file_location(nome_modulo, caminho_absoluto)
    if spec is None or spec.loader is None:
      fila_comunicacao.put({
          "status_geral": "Erro de Estrutura",
          "mensagem_erro": "O arquivo não pôde ser importado.",
      })
      return

    modulo_aluno = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo_aluno
    spec.loader.exec_module(modulo_aluno)

    if not hasattr(modulo_aluno, "principal"):
      fila_comunicacao.put({
          "status_geral": "Erro de Estrutura",
          "mensagem_erro": "O arquivo não contém a função 'principal(observada, mascara)'.",
      })
      return

    detalhes_por_matriz = []
    nrmses_validos = []
    tempo_total = 0.0

    # Itera pelas 10 matrizes no mesmo processo
    for idx, dados_matriz in enumerate(banco_10_matrizes):
      obs = dados_matriz["observada"]
      mascara = dados_matriz["mascara"]
      gabarito = dados_matriz["gabarito"]

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

      # Validações de tipo e formato
      if not isinstance(matriz_saida, np.ndarray):
        matriz_saida = np.array(matriz_saida)

      if matriz_saida.shape != gabarito.shape:
        fila_comunicacao.put({
            "status_geral": f"Reprovado na Matriz #{idx + 1}: Reprovado (Dimensões Incorretas)",
            "mensagem_erro": f"Esperado {gabarito.shape}, retornado {matriz_saida.shape}",
        })
        return

      if np.isnan(matriz_saida).any():
        fila_comunicacao.put({
            "status_geral": f"Reprovado na Matriz #{idx + 1}: Reprovado (Contém valores NaNs)",
            "mensagem_erro": "A matriz retornada possui valores NaN não preenchidos.",
        })
        return

      # Cálculo do NRMSE estritamente nas posições ocultas
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

    # Retorna o relatório completo de sucesso
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


def avaliar_todas_as_matrizes(caminho_arquivo_py, banco_10_matrizes, timeout_total_seg=5):
  """Orquestra a avaliação completa em um único processo isolado com timeout global."""
  ctx = multiprocessing.get_context("spawn")
  fila_comunicacao = ctx.Queue()

  p = ctx.Process(
      target=_tarefa_lote_processo,
      args=(caminho_arquivo_py, banco_10_matrizes, fila_comunicacao),
  )

  p.start()
  p.join(timeout=timeout_total_seg)

  if p.is_alive():
    p.terminate()
    p.join()
    return {
        "status_geral": "Reprovado (Timeout excedido)",
        "nrmse_medio_agregado": None,
        "tempo_total_acumulado": timeout_total_seg,
        "detalhes_por_matriz": [],
        "mensagem_erro": f"A execução total ultrapassou o limite de {timeout_total_seg} segundos para o lote.",
    }

  if fila_comunicacao.empty():
    return {
        "status_geral": "Erro de Execução",
        "nrmse_medio_agregado": None,
        "tempo_total_acumulado": 0.0,
        "detalhes_por_matriz": [],
        "mensagem_erro": "O processo encerrou inesperadamente.",
    }

  return fila_comunicacao.get()


def salvar_historico_local(caminho_codigo_enviado, relatorio):
  """Salva uma cópia do código testado e registra o histórico localmente."""
  diretorio_base = "historico_local_tentativas"
  os.makedirs(diretorio_base, exist_ok=True)

  caminho_historico = os.path.join(diretorio_base, "historico.json")
  historico_geral = []

  if os.path.exists(caminho_historico):
    try:
      with open(caminho_historico, "r", encoding="utf-8") as f:
        historico_geral = json.load(f)
    except Exception:
      historico_geral = []

  timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S")
  nome_codigo_salvo = f"codigo_{timestamp_str}.py"
  shutil.copy(caminho_codigo_enviado, os.path.join(diretorio_base, nome_codigo_salvo))

  nova_entrada = {
      "timestamp": timestamp_str,
      "arquivo_codigo": nome_codigo_salvo,
      "resultado": relatorio,
  }
  historico_geral.append(nova_entrada)

  with open(caminho_historico, "w", encoding="utf-8") as f:
    json.dump(historico_geral, f, indent=4, ensure_ascii=False)