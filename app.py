import time
import numpy as np
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Avaliador de Matrizes - Álgebra", layout="wide"
)

st.title("Avaliador Automático de Matrizes (MVP)")
st.write(
    "Ambiente de teste para submissão de códigos de resolução de matrizes com valores ocultos."
)

# 1. GABARITO E DADOS OFICIAIS (Ocultos dos alunos)
# Matriz original correta (Gabarito)
GABARITO_OFICIAL = np.array(
    [[2.0, 5.0, 1.0], [4.0, 8.0, 6.0], [7.0, 3.0, 9.0]]
)

# Máscara: True onde o valor é conhecido (observado), False onde está oculto
MASCARE_OFICIAL = np.array([[True, False, True], [False, True, False], [True, False, True]])

# Matriz Observada (o que é fornecido ao aluno: valores ocultos viram NaN)
MATRIZ_OBSERVADA = np.where(MASCARE_OFICIAL, GABARITO_OFICIAL, np.nan)

# 2. PAINEL LATERAL: ENVIO DE CÓDIGO
st.sidebar.header("📁 Submissão da Equipe")
nome_equipe = st.sidebar.text_input(
    "Nome da Equipe", value="Equipe Alpha"
)
arquivo_enviado = st.sidebar.file_uploader(
    "Envie o script de resolução (.py)", type=["py"]
)

btn_executar = st.sidebar.button("Executar Avaliação")

# 3. CORPO PRINCIPAL: EXIBIÇÃO DE ENTRADAS
col1, col2 = st.columns(2)

with col1:
  st.subheader("🔍 Matriz Observada (Entrada)")
  st.write("Valores conhecidos fornecidos para o cálculo:")
  st.dataframe(MATRIZ_OBSERVADA, use_container_width=True)

with col2:
  st.subheader("🧩 Máscara")
  st.write("True = Dado Revelado | False = Posição a Calcular:")
  st.dataframe(MASCARE_OFICIAL, use_container_width=True)

st.markdown("---")

# 4. LÓGICA DE AVALIAÇÃO E EXECUÇÃO
if btn_executar:
  if not arquivo_enviado:
    st.sidebar.error("Por favor, envie um arquivo .py antes de executar!")
  else:
    with st.spinner(f"Executando código da equipe {nome_equipe}..."):
      inicio = time.time()

      # SIMULAÇÃO DE EXECUÇÃO DO CÓDIGO DO ALUNO
      # Em produção, aqui entraria o subprocess ou Docker rodando o arquivo_enviado.
      # Para o MVP simulado, vamos fingir que o aluno acertou perfeitamente:
      time.sleep(1.2)  # Simula tempo de processamento
      matriz_resposta_aluno = GABARITO_OFICIAL.copy()

      # Injetando um erro proposital em simulação caso queira testar métrica (opcional)
      # matriz_resposta_aluno[0, 1] = 99.0

      fim = time.time()
      tempo_execucao = fim - inicio

      # --- VALIDAÇÕES ---
      # RF04: Validação de Formato
      if (
          matriz_resposta_aluno.shape != GABARITO_OFICIAL.shape
          or np.isnan(matriz_resposta_aluno).any()
      ):
        status = "Reprovado (Saída Inválida ou com NaNs)"
        erro_oculto = None
      else:
        status = "Sucesso"
        # RF05: Cálculo de Erro estritamente nas posições ocultas (onde máscara é False)
        posicoes_ocultas = ~MASCARE_OFICIAL
        valores_aluno_ocultos = matriz_resposta_aluno[posicoes_ocultas]
        valores_gabarito_ocultos = GABARITO_OFICIAL[posicoes_ocultas]

        # Cálculo do Erro Quadrático Médio (MSE)
        erro_oculto = np.mean(
            (valores_aluno_ocultos - valores_gabarito_ocultos) ** 2
        )

      # --- RELATÓRIO DE RESULTADOS (RF09) ---
      st.header("📋 Relatório de Resultados")

      m1, m2, m3 = st.columns(3)
      m1.metric("Status da Execução", status)
      m2.metric("Tempo de Execução", f"{tempo_execucao:.4f} s")
      m3.metric(
          "Erro nas Posições Ocultas (MSE)",
          f"{erro_oculto:.4f}" if erro_oculto is not None else "N/A",
      )

      st.subheader("Matriz Retornada pela Equipe")
      st.dataframe(matriz_resposta_aluno, use_container_width=True)