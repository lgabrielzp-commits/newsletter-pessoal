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

CREATE TABLE IF NOT EXISTS materias (
    cluster_id INTEGER PRIMARY KEY,
    categoria TEXT NOT NULL,
    titulo TEXT NOT NULL,
    resumo TEXT NOT NULL,
    texto_completo TEXT NOT NULL,
    perspectivas TEXT,  -- JSON: [{"fonte": "...", "texto": "..."}]
    badges TEXT NOT NULL,  -- JSON: ["Folha de S.Paulo", "G1"]
    url TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
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
        "categorias_feed": "TEXT",  # categoria(s) do feed RSS de origem, ex. "financas" ou "politica,financas"
        "ordem_edicao": "INTEGER",  # posição de relevância dentro da categoria (1 = melhor), da Fase 4
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


def podar(conn: sqlite3.Connection, retencao_artigos_dias: int, janela_dedupe_dias: int) -> None:
    """Apaga dados que já não servem pra nada.

    Sem isso o banco cresce ~4MB/dia indefinidamente (estourando o limite de
    100MB por arquivo do GitHub em poucas semanas) e, pior, o clustering da
    Fase 3b — que é O(n²) sobre tudo que estiver na tabela — passaria a
    comparar centenas de milhares de artigos, consumindo dezenas de GB de RAM.

    `artigos` é cache de trabalho: o que interessa é a janela de coleta atual,
    reconstruída a cada execução a partir dos feeds. `urls_enviadas` é o que
    de fato precisa sobreviver, e só dentro da janela de dedupe.
    """
    artigos = conn.execute(
        "DELETE FROM artigos WHERE data_coleta < datetime('now', ?)",
        (f"-{retencao_artigos_dias} days",),
    ).rowcount

    urls = conn.execute(
        "DELETE FROM urls_enviadas WHERE data_envio < datetime('now', ?)",
        (f"-{janela_dedupe_dias} days",),
    ).rowcount

    # matérias órfãs (cluster já podado) e logs antigos
    conn.execute(
        "DELETE FROM materias WHERE cluster_id NOT IN (SELECT DISTINCT cluster_id FROM artigos)"
    )
    logs = conn.execute(
        "DELETE FROM log_execucao WHERE timestamp < datetime('now', '-30 days')"
    ).rowcount
    conn.commit()

    if artigos or urls or logs:
        conn.execute("VACUUM")
        print(f"[Poda] {artigos} artigos, {urls} URLs expiradas e {logs} linhas de log removidas.")
