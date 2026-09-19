import os
import shutil
import time
import numpy as np
import streamlit as st
import plotly.express as px
import pandas as pd
from funcoes_suporte import (
    timestamp_formatado,
    destacar_buracos,
    validar_pin_equipe,
    calcular_hash_sha256,
    verificar_congelamento,
    deletar_tentativa_historico,
    deletar_codigo_final)
from core_avaliador import (
    avaliar_todas_as_matrizes,
    salvar_historico_local,
)
from banco import (
    consultar_historico_equipe,
    consultar_submissao_final,
    deletar_tentativa,
    deletar_submissao_final,
    salvar_ou_atualizar_final,
    consultar_todas_submissoes_finais,
    carregar_config_torneio,
    salvar_config_torneio,
    consultar_detalhes_tentativa
)

#constantes secretas
tamanho_max_bytes = st.secrets["TAMANHO_MAX_BYTES"] * 1024 * 1024
senha_monitor_correta = st.secrets["SENHA_MESTRE_MONITORES"]

#função para carregar banco público
@st.cache_resource
def carregar_banco(pasta_banco):
    banco = []
    if not os.path.exists(pasta_banco):
        return []

    for arquivo in sorted([
        f for f in os.listdir(pasta_banco) if f.startswith("gabarito_") and f.endswith(".npy")
    ]):
        prefixo = arquivo.replace("gabarito_", "").replace(".npy", "")
        banco.append({
            "observada": np.load(
                os.path.join(pasta_banco, f"observada_{prefixo}.npy")
            ),
            "mascara": np.load(
                os.path.join(pasta_banco, f"mascara_{prefixo}.npy")
            ),
            "gabarito": np.load(
                os.path.join(pasta_banco, f"gabarito_{prefixo}.npy")
            ),
        })
    return banco

#=====================================================================================

#configuração da página
st.set_page_config(
    page_title="Programa Avaliador",
    layout="centered",
)

#inicializar o estado de autenticação na sessão
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.equipe_id = None

#tela se não estiver autenticado
if not st.session_state.autenticado:
    modo_acesso = st.sidebar.radio("Selecione o Painel", ["Área do Aluno", "Painel dos Monitores"])

    if modo_acesso == "Área do Aluno":
        st.subheader("Identificação da Equipe")
        st.info("Insira o ID da sua equipe e o PIN secreto fornecido pelos monitores para acessar o avaliador.")
        
        with st.form("form_login"):
            input_id = st.number_input("Número da Equipe (ID):", min_value=1, max_value=50, step=1, value=1)
            input_pin = st.text_input("PIN Secreto:", type="password")
            botao_login = st.form_submit_button("Entrar no Painel da Equipe")
            
            if botao_login:
                if not input_pin or input_pin.strip() == "":
                    st.error("Insira o PIN fornecido para a equipe.")
                elif validar_pin_equipe(int(input_id), input_pin):
                    st.session_state.autenticado = True
                    st.session_state.equipe_id = int(input_id)
                    st.success("Autenticado com sucesso.")
                    st.rerun()
                else:
                    st.error("PIN incorreto para este ID de equipe.")

    #painel dos monitores para ranking automatizado
    if modo_acesso == "Painel dos Monitores":
        st.subheader("Painel dos Monitores")
        st.info("Área restrita para visualização do ranking final das equipes. Insira a senha da monitoria para acessar as funções de administrador.")
            
        senha_monitor = st.text_input("Digite a senha de monitor:", type="password", key="senha_monitor_input")
        
        if senha_monitor == senha_monitor_correta:
            st.success("Acesso liberado ao Ranking Oficial.")

            #carregar estado atual de congelamento
            config_atual = carregar_config_torneio()

            #botão para fazer o ranking
            if st.button("Executar Avaliação Geral"):
                banco_oficial = carregar_banco("banco_oficial")
                with st.spinner("Avaliando códigos finais de todas as equipes no Banco Oficial..."):
                    diretorio_base = "historico_local_tentativas"
                    dados_ranking = []

                    #buscar todas as submissões das equipes
                    todas_submissoes = consultar_todas_submissoes_finais()

                    #procurar por todas as pastas de equipes
                    for sub in todas_submissoes:
                        equipe_id = sub["equipe_id"]
                        codigo_fonte = sub.get("codigo_fonte")

                        #se a equipe enviou o código final
                        if codigo_fonte:
                            caminho_temp_ranking = f"temp_ranking_equipe_{equipe_id}.py"
                            with open(caminho_temp_ranking, "w", encoding="utf-8") as temp_file:
                                temp_file.write(codigo_fonte)
                            
                            try:
                                #executa a avaliação contra o banco oficial
                                timestamp_oficial = time.strftime("%Y-%m-%d_%H-%M-%S")
                                relatorio_oficial = avaliar_todas_as_matrizes(equipe_id, caminho_temp_ranking, banco_oficial, timestamp_oficial)
                                status = relatorio_oficial.get("status_geral", "mensagem_erro")
                                nrmse = relatorio_oficial.get("nrmse_medio_agregado")
                                tempo = relatorio_oficial.get("tempo_total_acumulado", 0.0)
                                
                                if "Sucesso" in status and nrmse is not None:
                                    dados_ranking.append({
                                        "Equipe": f"Equipe #{equipe_id}",
                                        "Status": "Válido",
                                        "NRMSE Agregado": float(nrmse),
                                        "Tempo Total (s)": float(tempo)
                                    })
                                else:
                                    dados_ranking.append({
                                        "Equipe": f"Equipe #{equipe_id}",
                                        "Status": f"Falha ({status})",
                                        "NRMSE Agregado": float('inf'),
                                        "Tempo Total (s)": float(tempo)
                                    })
                                    
                            finally:
                                if os.path.exists(caminho_temp_ranking):
                                    try:
                                        os.remove(caminho_temp_ranking)
                                    except Exception:
                                        pass
                        else:
                            dados_ranking.append({
                                "Equipe": f"Equipe #{equipe_id}",
                                "Status": "Falha (Código ausente no banco)",
                                "NRMSE Agregado": float('inf'),
                                "Tempo Total (s)": 0.0
                            })
                    #ordenação
                    if dados_ranking:
                        df_ranking = pd.DataFrame(dados_ranking)
                        df_ranking = df_ranking.sort_values(by=["NRMSE Agregado", "Tempo Total (s)"], ascending=[True, True]).reset_index(drop=True)
                        
                        df_ranking.index += 1
                        df_ranking.index.name = "Posição"
                        
                        st.subheader("Ranking Oficial do Torneio")
                        st.dataframe(df_ranking, use_container_width=True)
                    else:
                        st.info("Nenhum código final encontrado nas pastas das equipes para compor o ranking.")

            novo_estado_congelamento = st.toggle(
                "Congelar Torneio Manualmente (Bloqueia envios das equipes)", 
                value=config_atual.get("congelamento_manual", False)
            )

            #se o monitor alterar o botão, salva no JSON
            if novo_estado_congelamento != config_atual.get("congelamento_manual", False):
                salvar_config_torneio(novo_estado_congelamento)
                st.rerun()

        elif senha_monitor:
            st.error("Senha incorreta.")

#tela se estiver autenticado
else:
    equipe_id = st.session_state.equipe_id

    with st.sidebar:
        st.success(f"Logado: Equipe {equipe_id}")
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.session_state.equipe_id = None
            st.rerun()

    #header da página
    st.title("Programa Avaliador de Código")
    st.info(
        "Utilize este avaliador para testar o seu código contra "
        "o lote público de matrizes, retornar os resultados e consultar o histórico "
        "das suas tentativas anteriores."
    )

    #mensagens de sucesso/erro após carregar banco público
    banco_publico = carregar_banco("banco_publico")
    st.subheader("Banco de Matrizes Públicas")
    if not banco_publico:
        st.error(
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
            arquivo_enviado = st.file_uploader(
                "Clique em Upload e selecione o arquivo desejado",
                type=["py"],
                key="uploader_codigo_teste"
            )
            botao_testar = st.button("Executar Teste", key="btn_salvar_codigo_teste")

        if botao_testar:
            if arquivo_enviado is None:
                st.error("Selecione um arquivo .py antes de executar.")
            elif arquivo_enviado.size > tamanho_max_bytes:
                st.error(f"O arquivo é muito grande ({arquivo_enviado.size / (1024*1024):.2f} MB). O limite máximo permitido é de 5MB.")
            else:
                caminho_temp = "temp_teste_aluno.py"
                with open(caminho_temp, "wb") as f:
                    f.write(arquivo_enviado.getbuffer())

                with st.spinner("Rodando testes..."):
                    timestamp_str = time.strftime("%Y-%m-%d_%H-%M-%S")
                    relatorio = avaliar_todas_as_matrizes(equipe_id, caminho_temp, banco_publico, timestamp_str)

                    #salvar automaticamente o histórico e uma cópia do código
                    salvar_historico_local(caminho_temp, relatorio, equipe_id, timestamp_str)

                if os.path.exists(caminho_temp):
                    os.remove(caminho_temp)

                st.divider()
                st.subheader(f"Resultado do Teste Atual — Equipe {equipe_id}")

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

    #histórico de tentativas locais
    st.divider()
    st.subheader("Histórico de Tentativas Locais")

    historico_data = consultar_historico_equipe(equipe_id)

    if historico_data:
        try:
            st.write(
                f"Total de submissões realizadas: **{len(historico_data)}**"
            )

            for idx, tentativa in enumerate(historico_data):
                tentativa_id = tentativa["id"]
                status_tentativa = tentativa["status_geral"]
                timestamp_tentativa = timestamp_formatado(tentativa["timestamp"])
                tempo_total_val = tentativa["tempo_total"]

                nrmse_val = tentativa["nrmse"]
                nrmse_str = f" - NRMSE: {nrmse_val:.6f}" if status_tentativa == "Sucesso" else ""

                titulo_expander = (
                    f"Tentativa #{len(historico_data) - idx} | Data:"
                    f" {timestamp_tentativa} | {status_tentativa}{nrmse_str}"
                )

                with st.expander(titulo_expander):
                    caminho_arquivo_codigo = tentativa["arquivo_codigo"]
                    if os.path.exists(caminho_arquivo_codigo):
                        with open(caminho_arquivo_codigo, "r", encoding="utf-8") as arq_py:
                            codigo_fonte = arq_py.read()
                        
                        with st.expander("Ver Código Fonte Enviado"):
                            st.code(codigo_fonte, language="python")

                    with st.expander("Ver Status Geral"):
                        if status_tentativa != "Sucesso":
                            st.error(f"**Status de Erro:** {status_tentativa}")
                        else:
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                if nrmse_val is not None:
                                        st.metric("NRMSE Médio Agregado", f"{nrmse_val:.6f}")
                                else:
                                        st.metric("Status Geral", status_tentativa)
                            with col_m2:
                                st.metric("Tempo Total Acumulado", f"{tempo_total_val:.4f} s")

                    pasta_saidas = os.path.join("historico_local_tentativas", f"equipe_{equipe_id}", f"tentativa_{tentativa['timestamp']}", "saidas")
                    detalhes_banco = consultar_detalhes_tentativa(tentativa_id)
                    mapa_detalhes = {d["matriz_id"]: d for d in detalhes_banco}

                    with st.expander("Ver Detalhes por Matriz"):
                        if status_tentativa == "Sucesso":
                            for matriz_id in range(1, 11):
                                caminho_saida_aluno = os.path.join(pasta_saidas, f"saida_{matriz_id}.npy")
                                caminho_mascara = os.path.join("banco_publico", f"mascara_{matriz_id:02d}.npy")

                                info_matriz = mapa_detalhes.get(matriz_id, {})
                                status_matriz = info_matriz.get("status_matriz", status_tentativa)

                                #visualização da matriz retornada
                                with st.expander(f"Matriz #{matriz_id} — Status: {status_matriz}"):

                                    #exibição das métricas de cada matriz
                                    if status_matriz == "Sucesso":
                                        col_det1, col_det2 = st.columns(2)
                                        with col_det1:
                                            st.write(f"**Tempo:** {info_matriz.get('tempo', 0.0):.6f} s")
                                            st.write(f"**RMSE Bruto:** {info_matriz.get('rmse_bruto', 0.0):.6f}")
                                        with col_det2:
                                            st.write(f"**NRMSE:** {info_matriz.get('nrmse', 0.0):.6f}")
                                    
                                        if os.path.exists(caminho_saida_aluno) and os.path.exists(caminho_mascara):
                                            try:
                                                matriz_aluno = np.load(caminho_saida_aluno)
                                                mascara_atual = np.load(caminho_mascara)
                                                df_saida = pd.DataFrame(matriz_aluno)
                                                
                                                def destacar_preenchidos_estilo(val, row_idx, col_idx):
                                                    try:
                                                        if mascara_atual[row_idx, col_idx] == 0:
                                                            return 'background-color: black; color: white;'
                                                    except Exception:
                                                        pass
                                                    return 'background-color: white; color: black;'
                                                
                                                df_estilizado = df_saida.style.apply(
                                                    lambda df: pd.DataFrame(
                                                        [[destacar_preenchidos_estilo(df.iat[r, c], r, c) for c in range(df.shape[1])] for r in range(df.shape[0])],
                                                        index=df.index,
                                                        columns=df.columns
                                                    ),
                                                    axis=None
                                                ).format(lambda x: f"{x:.4f}" if pd.notna(x) else "")
                                                
                                                st.markdown("**Matriz Reconstruída (Branco = Observada | Preto = Preenchida):**")
                                                st.dataframe(df_estilizado, use_container_width=True)

                                            except Exception as e:
                                                st.error(f"**Visualização de Matriz Indisponível**: {e}")
                        else:
                            st.error(f"**Visualização Indisponível**: {status_tentativa}")

                    if st.button("🗑️ Deletar esta tentativa", key=f"btn_del_{tentativa_id}"):
                        try:
                            apagado_no_banco = deletar_tentativa(tentativa_id)
                            if not apagado_no_banco:
                                st.error(
                                    f"O registro (ID {tentativa_id}) não foi encontrado no banco "
                                    "— nada foi apagado."
                                )
                            else:
                                removido_do_disco = deletar_tentativa_historico(caminho_arquivo_codigo)
                                if removido_do_disco:
                                    st.success("Tentativa removida do banco e do histórico local.")
                                else:
                                    st.warning(
                                        "Tentativa removida do banco, mas a pasta local ainda não pôde "
                                        "ser apagada (arquivo em uso). Ela será limpa numa próxima tentativa."
                                    )
                                st.rerun()
                        except Exception as e:
                            st.error(f"Falha ao deletar tentativa do banco de dados: {e}")

        except Exception:
            st.info("Não foi possível carregar o histórico de tentativas.")
    else:
        st.caption("Nenhum histórico registrado ainda. Faça um teste acima para gerar registros.")

    #campo de submissão final
    st.divider()
    st.subheader("Submissão do Código Final")
    st.write(
        "**Atenção:** Este é o canal oficial de entrega do **código final** da equipe."
        " A equipe pode enviar quantas vezes precisar. O envio mais recente **sobrescreverá** o anterior. "
        "Após o encerramento do prazo, as submissões serão **congeladas** para o cálculo do ranking."
    )

    caminho_pasta_equipe = os.path.join("historico_local_tentativas", f"equipe_{equipe_id}")
    os.makedirs(caminho_pasta_equipe, exist_ok=True)
        
    caminho_arquivo_final = os.path.join(caminho_pasta_equipe, "codigo_final.py")
    submissao_final = consultar_submissao_final(equipe_id)

    #status caso já exista uma submissão oficial
    if submissao_final and os.path.exists(caminho_arquivo_final):
        st.success("Sua equipe já possui um **Código Final** registrado no sistema.")
        timestamp_bruto = submissao_final.get("timestamp")
        timestamp_legivel = timestamp_formatado(timestamp_bruto)

        st.info(f"Última Atualização: **{timestamp_legivel}**")
        st.info(f"NRMSE Agregado no Lote Público: **{submissao_final.get("nrmse", 0):.6f}**")
            
        with st.expander("Ver Código Final Cadastrado"):
            with open(caminho_arquivo_final, "r", encoding="utf-8") as arq_final:
                st.code(arq_final.read(), language="python")

            if st.button("🗑️ Deletar Código Final Cadastrado", key=f"btn_del_final_{equipe_id}"):
                try:
                    apagado_no_banco = deletar_submissao_final(equipe_id)
                    if not apagado_no_banco:
                        st.error("Nenhuma submissão final encontrada no banco para esta equipe.")
                    else:
                        removido_do_disco = deletar_codigo_final(equipe_id)
                        if removido_do_disco:
                            st.success("Código final removido do banco e do disco.")
                        else:
                            st.warning(
                                "Submissão removida do banco, mas o arquivo local ainda não pôde "
                                "ser apagado (arquivo em uso). Ele será limpo numa próxima tentativa."
                            )
                        st.rerun()
                except Exception as e:
                    st.error(f"Falha ao deletar submissão final: {e}")
    else:
        st.error("Nenhum Código Final enviado por esta equipe ainda.")

    #checar status de congelamento
    esta_congelado, motivo_congelamento = verificar_congelamento()

    if esta_congelado:
        st.warning(f"**Atenção:** {motivo_congelamento} Não é mais permitido enviar ou alterar o código final.")
    else:
        #form para envio ou sobrescrita do código final
        with st.expander("Enviar Código Final"):
            arquivo_oficial = st.file_uploader(
                "Selecione o arquivo Python (.py) definitivo para concorrer",
                type=["py"],
                key="uploader_codigo_final"
            )
            botao_enviar_oficial = st.button("Salvar Código", key="btn_salvar_codigo_final")

        if botao_enviar_oficial:
            #dupla checagem caso o estado mude enquanto o form estava aberto
            bloqueado_agora, motivo_agora = verificar_congelamento()
            if bloqueado_agora:
                st.error(f"Erro: {motivo_agora}")
            elif arquivo_oficial is None:
                st.error("Selecione um arquivo .py antes de enviar.")
            elif arquivo_oficial.size > tamanho_max_bytes:
                st.error(f"O arquivo é muito grande ({arquivo_oficial.size / (1024*1024):.2f} MB). O limite máximo permitido é de 5MB.")
            else:
                caminho_temp_oficial = os.path.join(caminho_pasta_equipe, "temp_oficial_aluno.py")
                with open(caminho_temp_oficial, "wb") as f:
                    f.write(arquivo_oficial.getbuffer())

                with st.spinner("Validando e avaliando o código final nas matrizes públicas..."):
                    timestamp_oficial = time.strftime("%Y-%m-%d_%H-%M-%S")
                    #executar a avaliação para checar se o código é válido e extrair o NRMSE
                    relatorio_oficial = avaliar_todas_as_matrizes(equipe_id, caminho_temp_oficial, banco_publico, timestamp_oficial)

                if "Sucesso" in relatorio_oficial["status_geral"]:
                    #copiar o código para o destino final
                    shutil.copy(caminho_temp_oficial, caminho_arquivo_final)
                    
                    nrmse_oficial = relatorio_oficial["nrmse_medio_agregado"]

                    #calcular o hash SHA-256 do arquivo salvo e salvar os metadados
                    hash_arquivo_final = calcular_hash_sha256(caminho_arquivo_final)
                    with open(caminho_arquivo_final, "r", encoding="utf-8") as arq_fonte:
                        codigo_fonte_final = arq_fonte.read()

                    salvar_ou_atualizar_final(
                        equipe_id=str(equipe_id),
                        timestamp=timestamp_oficial,
                        arquivo_codigo="codigo_final.py",
                        nrmse=float(nrmse_oficial),
                        tempo_total=float(relatorio_oficial["tempo_total_acumulado"]),
                        hash_sha256=hash_arquivo_final,
                        codigo_fonte=codigo_fonte_final,
                    )

                    st.success("A submissão oficial foi registrada com sucesso.")
                else:
                    st.error(f"**Código final rejeitado.** Confirme antes que o código está sem erros estruturais e válido para todas as matrizes públicas.")
                    st.error(f"Status: {relatorio_oficial["status_geral"]}")
                    if relatorio_oficial.get("mensagem_erro"):
                        st.warning(f"Detalhes: {relatorio_oficial["mensagem_erro"]}")

                if os.path.exists(caminho_temp_oficial):
                    os.remove(caminho_temp_oficial)

                if "Sucesso" in relatorio_oficial["status_geral"]:
                    #pequeno atraso visual pro aluno ver o sucesso
                    time.sleep(3)
                    st.rerun()