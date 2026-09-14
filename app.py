import json
import os
import shutil
import time
import numpy as np
import streamlit as st
import plotly.express as px
import pandas as pd
from gerar_pins import validar_pin_equipe
from funcoes_suporte import (
    calcular_hash_sha256,
    verificar_congelamento,
    deletar_tentativa_historico)
from core_avaliador import (
    avaliar_todas_as_matrizes,
    salvar_historico_local,
)

#função para carregar banco público
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

#função para carregar banco oficial
@st.cache_resource
def carregar_banco_oficial():
    pasta_banco = "banco_oficial"
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
    st.subheader("Identificação da Equipe")
    st.info("Insira o ID da sua equipe e o PIN secreto fornecido pelos monitores para acessar o avaliador.")
    
    with st.form("form_login"):
        input_id = st.number_input("Número da Equipe (ID):", min_value=1, max_value=50, step=1, value=1)
        input_pin = st.text_input("PIN Secreto:", type="password")
        botao_login = st.form_submit_button("Entrar no Painel")
        
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
    st.divider()
    caminho_config = "config_torneio.json"
    with st.expander("Painel dos Monitores"):
        st.write("Área restrita para visualização do ranking final das equipes.")
        
        senha_monitor = st.text_input("Digite a senha de monitor:", type="password", key="senha_monitor_input")
        
        SENHA_MESTRE_MONITORES = "temp"
        
        if senha_monitor == SENHA_MESTRE_MONITORES:
            st.success("Acesso liberado ao Ranking Oficial.")

            #carregar estado atual do torneio
            config_atual = {"congelamento_manual": False}
            if os.path.exists(caminho_config):
                try:
                    with open(caminho_config, "r", encoding="utf-8") as f:
                        config_atual = json.load(f)
                except:
                    pass

            #botão para fazer o ranking
            if st.button("Executar Avaliação Geral"):
                banco_oficial = carregar_banco_oficial()
                with st.spinner("Avaliando códigos finais de todas as equipes no Banco Oficial..."):
                    diretorio_base = "historico_local_tentativas"
                    dados_ranking = []
                    
                    if os.path.exists(diretorio_base):
                        #procurar por todas as pastas de equipes
                        for nome_pasta in os.listdir(diretorio_base):
                            if nome_pasta.startswith("equipe_"):
                                try:
                                    equipe_id_str = nome_pasta.split("_")[1]
                                    equipe_id = int(equipe_id_str)
                                except ValueError:
                                    continue
                                    
                                caminho_codigo_final = os.path.join(diretorio_base, nome_pasta, "codigo_final.py")
                                
                                #se a equipe enviou o código final
                                if os.path.exists(caminho_codigo_final):
                                    #executa a avaliação contra o banco oficial
                                    relatorio_oficial = avaliar_todas_as_matrizes(caminho_codigo_final, banco_oficial)
                                    
                                    status = relatorio_oficial.get("status_geral", "Erro")
                                    nrmse = relatorio_oficial.get("nrmse_medio_agregado")
                                    tempo = relatorio_oficial.get("tempo_total_acumulado", 0.0)
                                    
                                    if "Sucesso" in status and nrmse is not None:
                                        dados_ranking.append({
                                            "Equipe": f"Equipe #{equipe_id}",
                                            "Status": "Válido",
                                            "NRMSE Agregado": nrmse,
                                            "Tempo Total (s)": tempo
                                        })
                                    else:
                                        dados_ranking.append({
                                            "Equipe": f"Equipe #{equipe_id}",
                                            "Status": f"Falha ({status})",
                                            "NRMSE Agregado": float('inf'),
                                            "Tempo Total (s)": tempo
                                        })

                    #ordenação
                    if dados_ranking:
                        df_ranking = pd.DataFrame(dados_ranking)
                        df_ranking = df_ranking.sort_values(by="NRMSE Agregado", ascending=True).reset_index(drop=True)
                        
                        df_ranking.index = df_ranking.index + 1
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
                config_atual["congelamento_manual"] = novo_estado_congelamento
                with open(caminho_config, "w", encoding="utf-8") as f:
                    json.dump(config_atual, f)
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
    banco_publico = carregar_banco_publico()
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

        if botao_testar:
            if arquivo_enviado is None:
                st.error("Selecione um arquivo .py antes de executar.")
            else:
                caminho_temp = "temp_teste_aluno.py"
                with open(caminho_temp, "wb") as f:
                    f.write(arquivo_enviado.getbuffer())

                with st.spinner("Rodando testes..."):
                    relatorio = avaliar_todas_as_matrizes(caminho_temp, banco_publico)

                    #salvar automaticamente o histórico e uma cópia do código
                    salvar_historico_local(caminho_temp, relatorio, equipe_id=int(equipe_id))

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
                    if relatorio.get("detalhes_por_matriz"):
                        st.json(relatorio["detalhes_por_matriz"])

    #histórico de tentativas locais
    st.divider()
    st.subheader("Histórico de Tentativas Locais")

    caminho_historico_equipe = os.path.join(
        "historico_local_tentativas", f"equipe_{equipe_id}", "historico.json"
    )

    if os.path.exists(caminho_historico_equipe):
        try:
            with open(caminho_historico_equipe, "r", encoding="utf-8") as f:
                historico_data = json.load(f)

            st.write(
                f"Total de submissões realizadas: **{len(historico_data)}**"
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
                        "historico_local_tentativas", f"equipe_{equipe_id}", tentativa["arquivo_codigo"]
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
                            equipe_id,
                            tentativa['arquivo_codigo'], 
                            tentativa['timestamp']
                        )
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
    caminho_meta_final = os.path.join(caminho_pasta_equipe, "meta_final.json")

    #status caso já exista uma submissão oficial
    if os.path.exists(caminho_arquivo_final):
        st.success("Sua equipe já possui um **Código Final** registrado no sistema.")
            
        if os.path.exists(caminho_meta_final):
            try:
                with open(caminho_meta_final, "r", encoding="utf-8") as f:
                    meta_final = json.load(f)
                st.info(
                    f"Última Atualização: **{meta_final.get('timestamp', 'Desconhecida')}** | "
                    f"NRMSE Agregado no Lote Público: **{meta_final.get('nrmse', 0):.6f}**"
                )
            except Exception:
                pass
            
        with st.expander("Ver Código Final Cadastrado"):
            with open(caminho_arquivo_final, "r", encoding="utf-8") as arq_final:
                st.code(arq_final.read(), language="python")
    else:
        st.error("Nenhum Código Final enviado por esta equipe ainda.")

    #checar status de congelamento
    esta_congelado, motivo_congelamento = verificar_congelamento()

    if esta_congelado:
        st.warning(f"**Atenção:** {motivo_congelamento} Não é mais permitido enviar ou alterar o código final.")
    else:
        #form para envio ou sobrescrita do código final
        with st.expander("Enviar Código Final"):
            with st.form("form_submissao_oficial"):
                arquivo_oficial = st.file_uploader(
                    "Selecione o arquivo Python (.py) definitivo para concorrer",
                    type=["py"],
                )
                botao_enviar_oficial = st.form_submit_button("Salvar Código")

        if botao_enviar_oficial:
            #dupla checagem caso o estado mude enquanto o form estava aberto
            bloqueado_agora, motivo_agora = verificar_congelamento()
            if bloqueado_agora:
                st.error(f"Erro: {motivo_agora}")
            elif arquivo_oficial is None:
                st.error("Selecione um arquivo .py antes de enviar.")
            else:
                caminho_temp_oficial = "temp_oficial_aluno.py"
                with open(caminho_temp_oficial, "wb") as f:
                    f.write(arquivo_oficial.getbuffer())

                with st.spinner("Validando e avaliando o código final nas matrizes públicas..."):
                    #executar a avaliação para checar se o código é válido e extrair o NRMSE
                    relatorio_oficial = avaliar_todas_as_matrizes(caminho_temp_oficial, banco_publico)

                if "Sucesso" in relatorio_oficial["status_geral"]:
                    #copiar o código para o destino final
                    shutil.copy(caminho_temp_oficial, caminho_arquivo_final)
                        
                    timestamp_oficial = time.strftime("%Y-%m-%d_%H-%M-%S")
                    nrmse_oficial = relatorio_oficial["nrmse_medio_agregado"]

                    #calcular o hash SHA-256 do arquivo salvo e salvar os metadados
                    hash_arquivo_final = calcular_hash_sha256(caminho_arquivo_final)
                    meta_dados = {
                        "timestamp": timestamp_oficial,
                        "equipe_id": equipe_id,
                        "arquivo": "codigo_final.py",
                        "nrmse": nrmse_oficial,
                        "tempo_total": relatorio_oficial["tempo_total_acumulado"],
                        "hash_sha256": hash_arquivo_final
                    }
                    with open(caminho_meta_final, "w", encoding="utf-8") as f:
                        json.dump(meta_dados, f, indent=4, ensure_ascii=False)

                    st.success("A submissão oficial foi registrada com sucesso.")
                        
                    #pequeno atraso visual pro aluno ver o sucesso
                    time.sleep(3)
                    st.rerun()
                else:
                    st.error(f"**Código final rejeitado.** Confirme antes que o código está sem erros estruturais e válido para todas as matrizes públicas.")
                    st.error(f"Status: {relatorio_oficial['status_geral']}")
                    if relatorio_oficial.get("mensagem_erro"):
                        st.warning(f"Detalhes: {relatorio_oficial['mensagem_erro']}")

                    if os.path.exists(caminho_temp_oficial):
                        os.remove(caminho_temp_oficial)