import sqlite3
import os
from contextlib import contextmanager

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "competicao.db")

@contextmanager
def _conexao():
    conexao = sqlite3.connect(DB_NAME, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("PRAGMA foreign_keys=ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()

#retornar conexão ativa com o SQLite
def obter_conexao():
    conexao = sqlite3.connect(DB_NAME)
    conexao.row_factory = sqlite3.Row
    return conexao

#criar arquivo do banco e as tabelas (se não existirem)
def inicializar_banco():
    with _conexao() as conexao:
        cursor = conexao.cursor()

        #tabela de histórico de tentativas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentativas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipe_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                arquivo_codigo TEXT NOT NULL,
                status_geral TEXT NOT NULL,
                nrmse REAL NOT NULL,
                tempo_total REAL NOT NULL
            )
        """)

        #tabela de detalhes por matriz para cada tentativa
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detalhes_tentativas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tentativa_id INTEGER,
                matriz_id INTEGER,
                status_matriz TEXT NOT NULL,
                rmse_bruto REAL,
                nrmse REAL,
                tempo REAL,
                FOREIGN KEY (tentativa_id) REFERENCES tentativas (id) ON DELETE CASCADE
            )
        """)

        #tabela de submissão final
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissao_final (
                equipe_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                arquivo_codigo TEXT NOT NULL,
                nrmse REAL NOT NULL,
                tempo_total REAL NOT NULL,
                hash_sha256 TEXT NOT NULL,
                codigo_fonte TEXT NOT NULL
            )
        """)

        #tabela de estado de congelamento
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_torneio (
                chave TEXT PRIMARY KEY,
                valor INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO config_torneio (chave, valor)
            VALUES ('congelamento_manual', 0)
        """)

    print("Banco de dados SQLite inicializado com sucesso!")

#função para adicionar tentativa no histórico
def salvar_tentativa(equipe_id, timestamp, arquivo_codigo, status_geral, nrmse, tempo_total, detalhes=None):
    with _conexao() as conexao:
        cursor = conexao.cursor()

        #salvar os metadados da tentativa
        cursor.execute("""
            INSERT INTO tentativas (equipe_id, timestamp, arquivo_codigo, status_geral, nrmse, tempo_total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(equipe_id), timestamp, arquivo_codigo, status_geral, nrmse, tempo_total))

        tentativa_id = cursor.lastrowid

        #salvar os detalhes de cada matriz
        if detalhes:
            if isinstance(detalhes, dict):
                itens_detalhes = detalhes.items()
            else:
                itens_detalhes = enumerate(detalhes, start=1)
                
            for chave, det in itens_detalhes:
                matriz_id = det.get("matriz_id", chave)
                status_matriz = det.get("status", "Erro")
                tempo_matriz = det.get("tempo", 0.0)
                rmse_bruto = det.get("rmse_bruto", 0.0)
                nrmse_matriz = det.get("nrmse", 0.0)
                
                cursor.execute("""
                    INSERT INTO detalhes_tentativas (tentativa_id, matriz_id, status_matriz, rmse_bruto, nrmse, tempo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tentativa_id, matriz_id, status_matriz, rmse_bruto, nrmse_matriz, tempo_matriz))
                
        conexao.commit()
    

#função para adicionar ou atualizar o código final da equipe
def salvar_ou_atualizar_final(equipe_id, timestamp, arquivo_codigo, nrmse, tempo_total, hash_sha256, codigo_fonte):
    with _conexao() as conexao:
        conexao.execute("""
            INSERT OR REPLACE INTO submissao_final
                (equipe_id, timestamp, arquivo_codigo, nrmse, tempo_total, hash_sha256, codigo_fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(equipe_id), timestamp, arquivo_codigo, nrmse, tempo_total, hash_sha256, codigo_fonte))

#função para retornar as tentativas de uma equipe
def consultar_historico_equipe(equipe_id):
    with _conexao() as conexao:
        cursor = conexao.execute("""
            SELECT id, timestamp, arquivo_codigo, status_geral, nrmse, tempo_total
            FROM tentativas
            WHERE equipe_id = ?
            ORDER BY id DESC
        """, (str(equipe_id),))
        return [dict(row) for row in cursor.fetchall()]

#função para retornar a submissão final de uma equipe
def consultar_submissao_final(equipe_id):
    with _conexao() as conexao:
        cursor = conexao.execute("""
            SELECT equipe_id, timestamp, arquivo_codigo, nrmse, tempo_total, hash_sha256, codigo_fonte
            FROM submissao_final
            WHERE equipe_id = ?
        """, (str(equipe_id),))
        row = cursor.fetchone()
        return dict(row) if row else None

#função para deletar uma tentativa  e seus detalhes pelo ID
def deletar_tentativa(tentativa_id):
    try:
        id_limpo = int(tentativa_id)
    except (ValueError, TypeError):
        id_limpo = tentativa_id

    with _conexao() as conexao:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM detalhes_tentativas WHERE tentativa_id = ?", (id_limpo,))
        cursor.execute("DELETE FROM tentativas WHERE id = ?", (id_limpo,))
        return cursor.rowcount > 0  #confirmar que algo foi realmente apagado

#função para remover submissão final
def deletar_submissao_final(equipe_id):
    with _conexao() as conexao:
        cursor = conexao.execute(
            "DELETE FROM submissao_final WHERE equipe_id = ?", (str(equipe_id),)
        )
        return cursor.rowcount > 0

#função para puxar submissões pro ranking
def consultar_todas_submissoes_finais():
    try:
        with _conexao() as conexao:
            cursor = conexao.execute("""
                SELECT equipe_id, timestamp, arquivo_codigo, nrmse, tempo_total, hash_sha256, codigo_fonte
                FROM submissao_final
            """)
            return [dict(linha) for linha in cursor.fetchall()]
    except Exception as e:
        print(f"Erro ao consultar submissões finais: {e}")
        return []

#função para ler o estado de congelamento
def carregar_config_torneio():
    try:
        with _conexao() as conexao:
            cursor = conexao.execute(
                "SELECT valor FROM config_torneio WHERE chave = 'congelamento_manual'"
            )
            resultado = cursor.fetchone()
            congelado = bool(resultado[0]) if resultado else False
            return {"congelamento_manual": congelado}
    except Exception as e:
        print(f"Erro ao carregar config: {e}")
        return {"congelamento_manual": False}

#função para atualizar o estado do congelamento
def salvar_config_torneio(congelado: bool):
    try:
        valor_int = 1 if congelado else 0
        with _conexao() as conexao:
            conexao.execute("""
                INSERT OR REPLACE INTO config_torneio (chave, valor)
                VALUES ('congelamento_manual', ?)
            """, (valor_int,))
    except Exception as e:
        print(f"Erro ao salvar config: {e}")

if __name__ == "__main__":
    inicializar_banco()

#função para retornar os detalhes por matriz de uma tentativa
def consultar_detalhes_tentativa(tentativa_id):
    with _conexao() as conexao:
        cursor = conexao.execute("""
            SELECT matriz_id, status_matriz, rmse_bruto, nrmse, tempo
            FROM detalhes_tentativas
            WHERE tentativa_id = ?
            ORDER BY matriz_id ASC
        """, (tentativa_id,))
        return [dict(row) for row in cursor.fetchall()]

