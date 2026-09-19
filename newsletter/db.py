"""Schema e conexão SQLite.

Tabelas:
  artigos        — cada matéria coletada, deduplicada e opcionalmente agrupada em cluster
  edicoes        — uma linha por edição diária publicada/enviada
  urls_enviadas  — histórico de URLs já usadas, para não repetir notícia numa janela de dias
  log_execucao   — registro de cada etapa do pipeline (sucesso/falha) para diagnóstico
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS artigos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_canonica TEXT NOT NULL UNIQUE,
    titulo TEXT NOT NULL,
    fonte_id TEXT NOT NULL,
    categoria TEXT,
    data_publicacao TEXT,
    data_coleta TEXT NOT NULL DEFAULT (datetime('now')),
    excerpt TEXT,
    texto_extraido TEXT,
    hash_conteudo TEXT,
    cluster_id INTEGER,
    incluido_na_edicao INTEGER
);

CREATE INDEX IF NOT EXISTS idx_artigos_cluster ON artigos(cluster_id);
CREATE INDEX IF NOT EXISTS idx_artigos_data ON artigos(data_coleta);

CREATE TABLE IF NOT EXISTS edicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL UNIQUE,
    caminho_html TEXT,
    url_publicada TEXT,
    enviado_em TEXT,
    status TEXT NOT NULL DEFAULT 'pendente'
);

CREATE TABLE IF NOT EXISTS urls_enviadas (
    url_canonica TEXT PRIMARY KEY,
    data_envio TEXT NOT NULL,
    edicao_id INTEGER REFERENCES edicoes(id)
);

CREATE TABLE IF NOT EXISTS log_execucao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    fase TEXT NOT NULL,
    status TEXT NOT NULL,
    mensagem TEXT
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Colunas adicionadas depois do schema inicial (Fase 2+). Migração simples via
# ALTER TABLE em vez de recriar o banco, pra não perder o histórico coletado.
_COLUNAS_NOVAS = {
    "artigos": {
        "url_final": "TEXT",
        "http_status": "INTEGER",
        "paywall_provavel": "INTEGER",
    },
}


def _migrar(conn: sqlite3.Connection) -> None:
    for tabela, colunas in _COLUNAS_NOVAS.items():
        existentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({tabela})")}
        for coluna, tipo in colunas.items():
            if coluna not in existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
    conn.commit()


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar(conn)
    return conn


def log(conn: sqlite3.Connection, fase: str, status: str, mensagem: str = "") -> None:
    conn.execute(
        "INSERT INTO log_execucao (fase, status, mensagem) VALUES (?, ?, ?)",
        (fase, status, mensagem),
    )
    conn.commit()
