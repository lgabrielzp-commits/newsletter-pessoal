"""Helpers git compartilhados: worktrees pra branches órfãs que guardam
artefatos gerados (site publicado, snapshot do banco) fora do histórico
principal de código."""

from __future__ import annotations

import subprocess
from pathlib import Path

from newsletter.config import ROOT_DIR


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def branch_existe_no_remoto(branch: str) -> bool:
    resultado = run(["git", "ls-remote", "--heads", "origin", branch], cwd=ROOT_DIR)
    return bool(resultado.stdout.strip())


def garantir_worktree(worktree_dir: Path, branch: str) -> None:
    """Cria (ou reaproveita) um worktree local apontando pra `branch`.

    Se a branch já existe no remoto, faz checkout normal. Se não existe
    ainda (primeiro uso), cria como branch órfã — sem histórico
    compartilhado com main, só o necessário pro artefato que vai nela.
    """
    if worktree_dir.exists():
        return

    run(["git", "fetch", "origin", branch], cwd=ROOT_DIR)

    if branch_existe_no_remoto(branch):
        resultado = run(["git", "worktree", "add", str(worktree_dir), branch], cwd=ROOT_DIR)
    else:
        resultado = run(
            ["git", "worktree", "add", "--orphan", "-b", branch, str(worktree_dir)],
            cwd=ROOT_DIR,
        )

    if resultado.returncode != 0:
        raise RuntimeError(f"Falha ao criar worktree da branch '{branch}': {resultado.stderr}")
