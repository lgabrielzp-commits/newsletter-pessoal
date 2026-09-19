"""Persistência do SQLite entre execuções no GitHub Actions.

Os runners do GitHub Actions são efêmeros — cada execução agendada
começa do zero, sem nada do disco da vez anterior. Sem isso, a
deduplicação de 7 dias da Fase 4 (urls_enviadas) nunca funcionaria de
verdade em produção: todo dia seria como o primeiro dia.

Guarda o arquivo do banco numa branch órfã (config.armazenamento.branch,
via o mesmo mecanismo de git worktree da Fase 7), restaurando no início
da execução e salvando no final.

Só entra em ação quando GITHUB_ACTIONS=true (setado automaticamente
pelo runner) — rodando local, o banco fica só na sua máquina, sem
nenhum push pra branch remota.
"""

from __future__ import annotations

import os
import shutil

from newsletter.config import Config, DB_PATH, ROOT_DIR
from newsletter.git_utils import garantir_worktree, run

WORKTREE_DIR = ROOT_DIR / ".dados-worktree"
NOME_ARQUIVO_DB = "newsletter.db"


def em_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def restaurar_db(config: Config) -> None:
    if not em_ci():
        return

    branch = config.armazenamento.branch
    try:
        garantir_worktree(WORKTREE_DIR, branch)
    except RuntimeError as exc:
        print(f"[Persistência] {exc} — começando com banco vazio.")
        return

    origem = WORKTREE_DIR / NOME_ARQUIVO_DB
    if origem.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, DB_PATH)
        print(f"[Persistência] Banco restaurado da branch '{branch}' ({origem.stat().st_size} bytes).")
    else:
        print(f"[Persistência] Nenhum banco anterior encontrado em '{branch}' — começando vazio.")


def salvar_db(config: Config) -> None:
    if not em_ci():
        return
    if not DB_PATH.exists():
        return

    branch = config.armazenamento.branch
    if not WORKTREE_DIR.exists():
        try:
            garantir_worktree(WORKTREE_DIR, branch)
        except RuntimeError as exc:
            print(f"[Persistência] {exc} — banco não foi salvo.")
            return

    shutil.copy2(DB_PATH, WORKTREE_DIR / NOME_ARQUIVO_DB)

    run(["git", "add", "-A"], cwd=WORKTREE_DIR)
    diff_check = run(["git", "diff", "--cached", "--quiet"], cwd=WORKTREE_DIR)
    if diff_check.returncode == 0:
        print("[Persistência] Banco sem mudanças — nada a salvar.")
        return

    commit = run(["git", "commit", "-m", "Atualiza snapshot do banco"], cwd=WORKTREE_DIR)
    if commit.returncode != 0:
        print(f"[Persistência] Falha ao commitar snapshot do banco: {commit.stderr}")
        return

    push = run(["git", "push", "origin", branch], cwd=WORKTREE_DIR)
    if push.returncode != 0:
        print(f"[Persistência] Falha ao salvar banco (push): {push.stderr}")
        return

    print(f"[Persistência] Banco salvo na branch '{branch}'.")
