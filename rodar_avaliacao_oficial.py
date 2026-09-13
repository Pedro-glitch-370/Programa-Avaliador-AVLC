import os
import json
import numpy as np
from core_avaliador import avaliar_todas_as_matrizes

def carregar_banco_oficial():
    """Carrega as 10 matrizes da pasta 'banco_oficial' para a memória."""
    pasta_banco = "banco_oficial"
    banco = []
    
    if not os.path.exists(pasta_banco):
        print(f"Erro: A pasta '{pasta_banco}' não foi encontrada. Execute o gerador primeiro.")
        return []

    # Identifica quantas matrizes existem contando os arquivos de gabarito
    arquivos_gabarito = sorted([f for f in os.listdir(pasta_banco) if f.endswith("_gabarito.npy")])
    
    for arquivo in arquivos_gabarito:
        prefixo = arquivo.replace("_gabarito.npy", "")
        
        caminho_obs = os.path.join(pasta_banco, f"{prefixo}_observada.npy")
        caminho_masc = os.path.join(pasta_banco, f"{prefixo}_mascara.npy")
        caminho_gab = os.path.join(pasta_banco, f"{prefixo}_gabarito.npy")
        
        observada = np.load(caminho_obs)
        mascara = np.load(caminho_masc)
        gabarito = np.load(caminho_gab)
        
        banco.append({
            "observada": observada,
            "mascara": mascara,
            "gabarito": gabarito
        })
        
    print(f"[{len(banco)} matrizes carregadas do banco oficial com sucesso]")
    return banco

def executar_avaliacao_oficial_todas_equipes():
    """Varrer as pastas das equipes e roda a avaliação oficial em lote."""
    diretorio_submissoes = "submissoes_armazenadas"
    
    if not os.path.exists(diretorio_submissoes):
        print(f"Nenhuma submissão encontrada na pasta '{diretorio_submissoes}'.")
        return

    banco_secreto = carregar_banco_oficial()
    if not banco_secreto:
        return

    ranking_geral = []

    # Lista todas as pastas de equipes (ex: equipe_1, equipe_2, ...)
    pastas_equipes = [p for p in os.listdir(diretorio_submissoes) if os.path.isdir(os.path.join(diretorio_submissoes, p))]

    print("\n--- INICIANDO AVALIAÇÃO OFICIAL EM LOTE DAS EQUIPES ---")

    for pasta_eq in sorted(pastas_equipes):
        caminho_codigo = os.path.join(diretorio_submissoes, pasta_eq, "codigo_submetido.py")
        
        if not os.path.exists(caminho_codigo):
            continue

        print(f"Avaliando a {pasta_eq}...")
        
        # Executa o código da equipe contra o banco secreto de 10 matrizes
        relatorio = avaliar_todas_as_matrizes(caminho_codigo, banco_secreto)
        
        # Prepara dados para o ranking
        status = relatorio["status_geral"]
        nrmse_medio = relatorio["nrmse_medio_agregado"]
        
        ranking_geral.append({
            "equipe": pasta_eq,
            "status_geral": status,
            "nrmse_medio_agregado": nrmse_medio if "Sucesso" in status else None,
            "tempo_total": relatorio["tempo_total_acumulado"],
            "detalhes": relatorio
        })

    # Ordena o ranking pelo menor NRMSE médio agregado (apenas os que obtiveram sucesso)
    sucessos = [eq for eq in ranking_geral if eq["nrmse_medio_agregado"] is not None]
    reprovados = [eq for eq in ranking_geral if eq["nrmse_medio_agregado"] is None]

    sucessos.sort(key=lambda x: x["nrmse_medio_agregado"])
    ranking_final = sucessos + reprovados

    # Salva o resultado oficial consolidado
    caminho_ranking = "ranking_final_oficial.json"
    with open(caminho_ranking, "w", encoding="utf-8") as f:
        json.dump(ranking_final, f, indent=4, ensure_ascii=False)

    print(f"\nAvaliação concluída! Ranking oficial salvo em '{caminho_ranking}'.")
    
    # Exibe um resumo no console
    print("\n--- RESUMO DO RANKING ---")
    for pos, eq in enumerate(ranking_final, 1):
        if eq["nrmse_medio_agregado"] is not None:
            print(f"{pos}º Lugar: {eq['equipe']} | NRMSE Médio: {eq['nrmse_medio_agregado']:.6f}")
        else:
            print(f"Reprovado: {eq['equipe']} | Motivo: {eq['status_geral']}")

if __name__ == "__main__":
    executar_avaliacao_oficial_todas_equipes()