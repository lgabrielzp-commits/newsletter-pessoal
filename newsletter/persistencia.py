"""Persistência do estado mínimo entre execuções no GitHub Actions.

Os runners do GitHub Actions são efêmeros — cada execução agendada começa
do zero. Sem persistir nada, a deduplicação de N dias da Fase 4
(urls_enviadas) nunca funcionaria em produção: todo dia seria o primeiro.

IMPORTANTE — por que só o estado mínimo, e não o banco inteiro:
a branch de dados vive num repositório público. O banco completo contém
o texto integral de matérias (inclusive de fontes pagas, o que seria
redistribuição indevida), o email do destinatário nos logs e caminhos
locais da máquina. Nada disso é necessário pra dedupe. Então o que é
publicado é só um JSON pequeno e auditável a olho nu:
URLs já enviadas + registro das edições.

A tabela `artigos` é cache de trabalho de cada execução: é reconstruída
do zero a partir dos feeds toda vez, e podada por
config.armazenamento.retencao_artigos_dias.

Só entra em ação quando GITHUB_ACTIONS=true (setado automaticamente pelo
runner) — rodando local, o banco fica só na sua máquina.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from newsletter.config import Config, ROOT_DIR
from newsletter.git_utils import garantir_worktree, run

WORKTREE_DIR = ROOT_DIR / ".dados-worktree"
NOME_ARQUIVO_ESTADO = "estado.json"
VERSAO_ESTADO = 1


def em_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def restaurar_estado(config: Config, conn: sqlite3.Connection) -> None:
    """Carrega urls_enviadas/edicoes da branch de dados pro banco local."""
    if not em_ci():
        return

    branch = config.armazenamento.branch
    try:
        garantir_worktree(WORKTREE_DIR, branch)
    except RuntimeError as exc:
        print(f"[Persistência] {exc} — começando sem histórico.")
        return

    origem = WORKTREE_DIR / NOME_ARQUIVO_ESTADO
    if not origem.exists():
        print(f"[Persistência] Nenhum estado anterior em '{branch}' — começando do zero.")
        return

    try:
        estado = json.loads(origem.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[Persistência] Estado anterior ilegível ({exc}) — começando do zero.")
        return

    edicoes = estado.get("edicoes", [])
    for e in edicoes:
        conn.execute(
            """
            INSERT OR IGNORE INTO edicoes (data, url_publicada, enviado_em, status)
            VALUES (?, ?, ?, ?)
            """,
            (e.get("data"), e.get("url_publicada"), e.get("enviado_em"), e.get("status", "enviado")),
        )

    urls = estado.get("urls_enviadas", [])
    for u in urls:
        conn.execute(
            "INSERT OR IGNORE INTO urls_enviadas (url_canonica, data_envio) VALUES (?, ?)",
            (u.get("url"), u.get("data_envio")),
        )
    conn.commit()

    print(f"[Persistência] Estado restaurado de '{branch}': "
          f"{len(urls)} URLs já enviadas, {len(edicoes)} edições.")


def salvar_estado(config: Config, conn: sqlite3.Connection) -> bool:
    """Exporta o estado mínimo pra branch de dados. Retorna False se falhar."""
    if not em_ci():
        return True

    branch = config.armazenamento.branch
    if not WORKTREE_DIR.exists():
        try:
            garantir_worktree(WORKTREE_DIR, branch)
        except RuntimeError as exc:
            print(f"[Persistência] {exc} — estado não foi salvo.")
            return False

    # só o que ainda importa pra dedupe — o resto expira e some
    janela = config.curadoria.janela_dedupe_dias
    urls = [
        {"url": r["url_canonica"], "data_envio": r["data_envio"]}
        for r in conn.execute(
            "SELECT url_canonica, data_envio FROM urls_enviadas "
            "WHERE data_envio >= datetime('now', ?) ORDER BY data_envio",
            (f"-{janela} days",),
        )
    ]
    edicoes = [
        {
            "data": r["data"],
            "url_publicada": r["url_publicada"],
            "enviado_em": r["enviado_em"],
            "status": r["status"],
        }
        for r in conn.execute(
            "SELECT data, url_publicada, enviado_em, status FROM edicoes ORDER BY data DESC LIMIT 90"
        )
    ]

    estado = {
        "versao": VERSAO_ESTADO,
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "urls_enviadas": urls,
        "edicoes": edicoes,
    }

    (WORKTREE_DIR / NOME_ARQUIVO_ESTADO).write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # limpa resquício da versão antiga, que publicava o banco inteiro
    db_antigo = WORKTREE_DIR / "newsletter.db"
    if db_antigo.exists():
        db_antigo.unlink()

    run(["git", "add", "-A"], cwd=WORKTREE_DIR)
    if run(["git", "diff", "--cached", "--quiet"], cwd=WORKTREE_DIR).returncode == 0:
        print("[Persistência] Estado sem mudanças — nada a salvar.")
        return True

    commit = run(["git", "commit", "-m", "Atualiza estado (URLs enviadas)"], cwd=WORKTREE_DIR)
    if commit.returncode != 0:
        print(f"[Persistência] Falha ao commitar estado: {commit.stderr}")
        return False

    push = run(["git", "push", "origin", branch], cwd=WORKTREE_DIR)
    if push.returncode != 0:
        print(f"[Persistência] Falha ao salvar estado (push): {push.stderr}")
        return False

    tamanho = (WORKTREE_DIR / NOME_ARQUIVO_ESTADO).stat().st_size
    print(f"[Persistência] Estado salvo em '{branch}' ({tamanho} bytes, {len(urls)} URLs).")
    return True
