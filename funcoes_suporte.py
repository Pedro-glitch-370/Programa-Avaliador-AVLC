import json
import os
import hashlib
import streamlit as st
from datetime import datetime

#função para calcular o hash SHA-256 de um arquivo
def calcular_hash_sha256(caminho_arquivo):
    sha256_hash = hashlib.sha256()
    with open(caminho_arquivo, "rb") as f:
        for byte_bloco in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_bloco)
    return sha256_hash.hexdigest()

#função para controlar o congelamento dos códigos
def verificar_congelamento():
    #congelar por data (a partir de 21 de novembro)
    data_limite = datetime(2026, 11, 21, 0, 0, 0)
    if datetime.now() >= data_limite:
        return True, "O prazo limite de submissões foi encerrado."
    
    #congelar pelo painel dos monitores
    caminho_config = "config_torneio.json"
    if os.path.exists(caminho_config):
        try:
            with open(caminho_config, "r", encoding="utf-8") as f:
                config = json.load(f)
                if config.get("congelamento_manual", False):
                    return True, "O torneio foi congelado pelos monitores."
        except Exception:
            pass
            
    return False, ""

#função para apagar tentativa do histórico local
def deletar_tentativa_historico(equipe_id, arquivo_codigo, timestamp):
    diretorio_base = os.path.join("historico_local_tentativas", f"equipe_{equipe_id}")
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