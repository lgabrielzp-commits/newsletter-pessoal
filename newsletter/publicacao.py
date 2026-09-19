"""Fase 7: publicação no GitHub Pages.

Cada edição já renderizada (output/<data>/index.html, Fase 6) é copiada
pra uma branch órfã (config.publicacao.branch, padrão "gh-pages") por
meio de um git worktree dedicado. /hoje/ sempre aponta pra edição mais
recente, e a raiz lista o arquivo histórico completo.

Não publica o email.html — esse é só pro corpo do email (Fase 8), não
faz sentido ficar acessível por URL pública.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from newsletter.config import Config, ROOT_DIR
from newsletter.db import log
from newsletter.git_utils import garantir_worktree, run
from newsletter.render import OUTPUT_DIR, TEMPLATES_DIR, _data_extenso

WORKTREE_DIR = ROOT_DIR / ".gh-pages-worktree"


def _montar_arquivo_index(config: Config) -> str:
    """Lista todas as edições já publicadas (pastas de data em output/)."""
    datas = sorted(
        (p.name for p in OUTPUT_DIR.iterdir() if p.is_dir() and p.name != "hoje"),
        reverse=True,
    )
    edicoes = []
    for data_iso in datas:
        dt = datetime.strptime(data_iso, "%Y-%m-%d")
        edicoes.append({"data_iso": data_iso, "data_extenso": _data_extenso(dt)})

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    return env.get_template("arquivo.html.jinja").render(edicoes=edicoes, design=config.design)


def executar_publicacao(config: Config, conn: sqlite3.Connection) -> None:
    if not OUTPUT_DIR.exists() or not any(OUTPUT_DIR.glob("*/index.html")):
        print("[Fase 7] Nenhuma edição renderizada (rode a Fase 6 antes). Nada a publicar.")
        return

    branch = config.publicacao.branch
    try:
        garantir_worktree(WORKTREE_DIR, branch)
    except RuntimeError as exc:
        print(f"[Fase 7] {exc}")
        log(conn, fase="fase7_publicacao", status="erro", mensagem=str(exc))
        return

    # sincroniza cada edição (só o index.html — o email.html fica de fora do site público)
    datas_publicadas = []
    for pasta_data in sorted(OUTPUT_DIR.iterdir()):
        if not pasta_data.is_dir() or pasta_data.name == "hoje":
            continue
        index_origem = pasta_data / "index.html"
        if not index_origem.exists():
            continue

        destino = WORKTREE_DIR / pasta_data.name
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy2(index_origem, destino / "index.html")
        datas_publicadas.append(pasta_data.name)

    if not datas_publicadas:
        print("[Fase 7] Nenhum index.html encontrado em output/. Nada a publicar.")
        return

    mais_recente = sorted(datas_publicadas)[-1]
    hoje_dir = WORKTREE_DIR / "hoje"
    hoje_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORKTREE_DIR / mais_recente / "index.html", hoje_dir / "index.html")

    arquivo_html = _montar_arquivo_index(config)
    (WORKTREE_DIR / "index.html").write_text(arquivo_html, encoding="utf-8")

    run(["git", "add", "-A"], cwd=WORKTREE_DIR)
    diff_check = run(["git", "diff", "--cached", "--quiet"], cwd=WORKTREE_DIR)
    if diff_check.returncode == 0:
        print("[Fase 7] Nada novo pra publicar (site já está atualizado).")
        log(conn, fase="fase7_publicacao", status="ok", mensagem="sem mudanças")
        return

    commit = run(
        ["git", "commit", "-m", f"Publica edição de {mais_recente}"],
        cwd=WORKTREE_DIR,
    )
    if commit.returncode != 0:
        print(f"[Fase 7] Falha ao commitar: {commit.stderr}")
        log(conn, fase="fase7_publicacao", status="erro", mensagem=commit.stderr)
        return

    push = run(["git", "push", "origin", branch], cwd=WORKTREE_DIR)
    if push.returncode != 0:
        print(f"[Fase 7] Falha ao publicar (push): {push.stderr}")
        log(conn, fase="fase7_publicacao", status="erro", mensagem=push.stderr)
        return

    url_hoje = f"{config.publicacao.base_url}/hoje/" if config.publicacao.base_url else "(base_url não configurada)"
    print(f"[Fase 7] Publicado com sucesso: {url_hoje}")
    print(f"  {len(datas_publicadas)} edição(ões) no ar, mais recente: {mais_recente}")

    log(
        conn,
        fase="fase7_publicacao",
        status="ok",
        mensagem=f"{len(datas_publicadas)} edições publicadas em {branch}, mais recente {mais_recente}",
    )
