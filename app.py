import os
import json
import numpy as np
import streamlit as st
import plotly.express as px
import pandas as pd
from core_avaliador import (
    avaliar_todas_as_matrizes,
    salvar_historico_local,
)

#função para apagar tentativa do histórico local
def deletar_tentativa_historico(arquivo_codigo, timestamp):
    diretorio_base = "historico_local_tentativas"
    caminho_json = os.path.join(diretorio_base, "historico.json")
    caminho_py = os.path.join(diretorio_base, arquivo_codigo)

    #remover o arquivo .py se ele existir
    if os.path.exists(caminho_py):
        try:
            os.remove(caminho_py)
        except Exception:
            pass

    #remover o registro do arquivo historico.json
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                historico_geral = json.load(f)
            
            #tirar o item com o timestamp correspondente
            historico_geral = [t for t in historico_geral if t["timestamp"] != timestamp]

            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(historico_geral, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    #recarrega a interface para sumir o item deletado
    st.rerun()

#=====================================================================================

#configuração da página
st.set_page_config(
    page_title="Programa Avaliador",
    layout="centered",
)

#header da página
st.title("Programa Avaliador de Código")
st.info(
    "Utilize este painel para testar o seu código contra "
    "o lote público de matrizes, retornar os resultados e consultar o histórico "
    "das suas tentativas anteriores."
)

#carregar o banco público
@st.cache_resource
def carregar_banco_publico():
    pasta_banco = "banco_publico"
    banco = []
    if not os.path.exists(pasta_banco):
        return []

    for arquivo in sorted([
        f for f in os.listdir(pasta_banco) if f.endswith("_gabarito.npy")
    ]):
        prefixo = arquivo.replace("_gabarito.npy", "")
        banco.append({
            "observada": np.load(
                os.path.join(pasta_banco, f"{prefixo}_observada.npy")
            ),
            "mascara": np.load(os.path.join(pasta_banco, f"{prefixo}_mascara.npy")),
            "gabarito": np.load(os.path.join(pasta_banco, f"{prefixo}_gabarito.npy")),
        })
    return banco

banco_publico = carregar_banco_publico()

#mensagens de sucesso/erro após carregar banco público
st.subheader("Banco de Matrizes Públicas")
if not banco_publico:
    st.write(
        "Pasta 'banco_publico' não encontrada ou vazia. Certifique-se de"
        " gerar as matrizes públicas primeiro."
    )
else:
    st.write(
        "**Atenção:** Este **não** é o banco de matrizes "
        "oficial do torneio, mas uma seleção de matrizes para treino e refino"
        " dos algoritmos."
    )

    #visualização das matrizes públicas
    with st.expander("Explorar Matrizes Públicas"):
        st.write(
            "Selecione uma matriz para visualizar os dados observados e a máscara"
            " booleana correspondente."
        )

        nomes_matrizes = [
            f"Matriz {i+1} (Dimensão: {m['observada'].shape[0]}x{m['observada'].shape[1]})"
            for i, m in enumerate(banco_publico)
        ]
        escolha_idx = st.selectbox(
            "Escolha a matriz:",
            range(len(banco_publico)),
            format_func=lambda x: nomes_matrizes[x],
        )

        matriz_selecionada = banco_publico[escolha_idx]
        obs = matriz_selecionada["observada"]
        mascara = matriz_selecionada["mascara"]
        df_obs = pd.DataFrame(obs)

        #fazer download da matriz
        st.markdown("**Download da Matriz:**")
        csv_data = df_obs.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"📥 Baixar Matriz #{escolha_idx + 1} (CSV)",
            data=csv_data,
            file_name=f"matriz_{escolha_idx + 1}_observada.csv",
            mime="text/csv",
            key=f"download_matriz_{escolha_idx}"
        )

        #mostrar matriz observada
        st.markdown("**Observada (Branco = Dado | Preto = Oculto):**")
        def destacar_buracos(val):
            if pd.isna(val):
                return 'background-color: black; color: black;'
            return 'background-color: white; color: black;'
        df_estilizado = df_obs.style.map(destacar_buracos).format(
            lambda x: f"{x:.4f}" if pd.notna(x) else ""
        )
        st.dataframe(df_estilizado, use_container_width=True)

        #mostrar máscara
        st.markdown("**Máscara (Branco = Dado | Preto = Oculto):**")
        fig_mask = px.imshow(
            mascara.astype(int),
            color_continuous_scale=["black", "white"],
            aspect="auto",
        )
        fig_mask.update_traces(xgap=2, ygap=2)
        fig_mask.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            height=300,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_mask, use_container_width=True)

    #form para enviar e testar o código
    st.divider()
    st.subheader("Envio de Código para Teste em Lote")
    st.write("**Atenção:** O arquivo deve ser em Python e conter "
             "a função `principal(observada, mascara)`.")
    with st.expander("Enviar Código"):
        with st.form("form_teste"):
            arquivo_enviado = st.file_uploader(
                "Clique em Upload e selecione o arquivo desejado",
                type=["py"],
            )
            botao_testar = st.form_submit_button("Executar Teste")

    if botao_testar and arquivo_enviado is not None:
        caminho_temp = "temp_teste_aluno.py"
        with open(caminho_temp, "wb") as f:
            f.write(arquivo_enviado.getbuffer())

        with st.spinner("Rodando testes..."):
            relatorio = avaliar_todas_as_matrizes(caminho_temp, banco_publico)

            #salvar automaticamente o histórico local e uma cópia do código
            salvar_historico_local(caminho_temp, relatorio)

        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)

        st.divider()
        st.subheader("Resultado do Teste Atual")

        status = relatorio["status_geral"]

        #status de sucesso
        if "Sucesso" in status:
            st.success("Seu código passou com sucesso em todas as matrizes públicas!")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "NRMSE Médio Agregado",
                    f"{relatorio['nrmse_medio_agregado']:.6f}",
                )
            with col2:
                st.metric(
                    "Tempo Total", f"{relatorio['tempo_total_acumulado']:.4f} s"
                )

            st.dataframe(relatorio["detalhes_por_matriz"], use_container_width=True)
        else:
            #status de erro
            st.error(f"Status: {status}")
            if relatorio.get("mensagem_erro"):
                st.warning(f"Detalhes: {relatorio['mensagem_erro']}")
            if relatorio.get("detalhes_por_matriz"):
                st.json(relatorio["detalhes_por_matriz"])

#histórico de tentativas locais
st.divider()
st.subheader("Histórico de Tentativas Locais")

caminho_historico_local = os.path.join(
    "historico_local_tentativas", "historico.json"
)

if os.path.exists(caminho_historico_local):
    try:
        with open(caminho_historico_local, "r", encoding="utf-8") as f:
            historico_data = json.load(f)

        st.write(
            f"Total de submissões realizadas nesta máquina: **{len(historico_data)}**"
        )

        for idx, tentativa in enumerate(reversed(historico_data), 1):
            res = tentativa["resultado"]
            status_tentativa = res["status_geral"]
            nrmse_val = res.get("nrmse_medio_agregado")
            nrmse_str = f" - NRMSE: {nrmse_val:.6f}" if nrmse_val is not None else ""

            titulo_expander = (
                f"Tentativa #{len(historico_data) - idx + 1} | Data:"
                f" {tentativa['timestamp']} | {status_tentativa}{nrmse_str}"
            )

            with st.expander(titulo_expander):
                caminho_arquivo_codigo = os.path.join(
                    "historico_local_tentativas", tentativa["arquivo_codigo"]
                )
                if os.path.exists(caminho_arquivo_codigo):
                    with open(caminho_arquivo_codigo, "r", encoding="utf-8") as arq_py:
                        codigo_fonte = arq_py.read()
                    
                    with st.expander("Ver Código Fonte Enviado"):
                        st.code(codigo_fonte, language="python")

                with st.expander("Ver Status Geral"):
                    if "mensagem_erro" in res and res["mensagem_erro"]:
                        st.error(f"**Status Geral:** {status_tentativa}")
                        st.error(f"**Mensagem de Erro:** {res['mensagem_erro']}")
                    else:
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            nrmse_val = res.get("nrmse_medio_agregado")
                            if nrmse_val is not None:
                                    st.metric("NRMSE Médio Agregado", f"{nrmse_val:.6f}")
                            else:
                                    st.metric("Status Geral", res.get("status_geral", "Erro"))
                        with col_m2:
                            st.metric("Tempo Total Acumulado", f"{res.get('tempo_total_acumulado', 0):.4f} s")

                detalhes = res.get("detalhes_por_matriz")
                if detalhes:
                    with st.expander("Ver Detalhes por Matriz"):
                        for item in detalhes:
                            matriz_id = item.get("matriz_id")
                            status_matriz = item.get("status")
                        
                            icone = "✅" if status_matriz == "Sucesso" else "❌"
                        
                            with st.expander(f"{icone} Matriz #{matriz_id} — Status: {status_matriz}"):
                                col_det1, col_det2 = st.columns(2)
                                with col_det1:
                                    st.write(f"**ID da Matriz:** {matriz_id}")
                                    st.write(f"**Status:** {status_matriz}")
                                    if "tempo" in item:
                                        st.write(f"**Tempo:** {item['tempo']:.6f} s")
                                with col_det2:
                                    if "rmse_bruto" in item:
                                        st.write(f"**RMSE Bruto:** {item['rmse_bruto']:.6f}")
                                    if "nrmse" in item:
                                        st.write(f"**NRMSE:** {item['nrmse']:.6f}")

                if st.button("🗑️ Deletar esta tentativa", key=f"btn_del_{tentativa['timestamp']}"):
                    deletar_tentativa_historico(
                        tentativa['arquivo_codigo'], 
                        tentativa['timestamp']
                    )

                
    except Exception:
        st.info("Não foi possível carregar o histórico de tentativas.")
else:
    st.caption("Nenhum histórico registrado ainda. Faça um teste acima para gerar registros.")