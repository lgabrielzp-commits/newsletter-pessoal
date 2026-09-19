"""Fase 6: renderização.

Gera dois HTMLs a partir das matérias redigidas (Fase 5):
  - web: página interativa (abas, expandir/recolher) — o que vai pro
    GitHub Pages na Fase 7.
  - email: versão estática (sem JS, que nenhum cliente de email roda),
    com manchete + resumo de cada matéria e um botão pra edição completa.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from newsletter.config import Config, ROOT_DIR
from newsletter.db import log

TEMPLATES_DIR = ROOT_DIR / "newsletter" / "templates"
OUTPUT_DIR = ROOT_DIR / "output"

_MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_extenso(dt: datetime) -> str:
    return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"


def _carregar_edicao(conn: sqlite3.Connection, config: Config) -> dict[str, list[dict]]:
    linhas = conn.execute(
        """
        SELECT m.*, (
            SELECT MIN(ordem_edicao) FROM artigos WHERE cluster_id = m.cluster_id
        ) AS ordem
        FROM materias m
        """
    ).fetchall()

    edicao: dict[str, list[dict]] = {c.id: [] for c in config.categorias}
    for row in linhas:
        materia = dict(row)
        materia["perspectivas"] = json.loads(row["perspectivas"] or "[]")
        materia["badges"] = json.loads(row["badges"] or "[]")
        materia["paragrafos"] = [p for p in materia["texto_completo"].split("\n\n") if p.strip()]
        if materia["categoria"] in edicao:
            edicao[materia["categoria"]].append(materia)

    for categoria_id in edicao:
        edicao[categoria_id].sort(key=lambda m: (m["ordem"] is None, m["ordem"]))

    return edicao


def executar_renderizacao(config: Config, conn: sqlite3.Connection) -> None:
    edicao = _carregar_edicao(conn, config)
    total_materias = sum(len(v) for v in edicao.values())

    if total_materias == 0:
        print("[Fase 6] Nenhuma matéria redigida (rode a Fase 5 antes). Nada a renderizar.")
        return

    agora = datetime.now(ZoneInfo(config.schedule.timezone))
    data_extenso = _data_extenso(agora)
    data_iso = agora.strftime("%Y-%m-%d")

    nomes_fontes = sorted({f.nome for f in config.fontes})

    base_url = config.publicacao.base_url.rstrip("/") if config.publicacao.base_url else ""
    edicao_url = f"{base_url}/{data_iso}/" if base_url else f"(local) output/{data_iso}/index.html"

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "jinja"]),
    )

    contexto_comum = {
        "categorias": config.categorias,
        "edicao": edicao,
        "data_extenso": data_extenso,
        "nomes_fontes": nomes_fontes,
        "design": config.design,
        "total_materias": total_materias,
    }

    dia_dir = OUTPUT_DIR / data_iso
    dia_dir.mkdir(parents=True, exist_ok=True)

    web_html = env.get_template("web.html.jinja").render(**contexto_comum)
    web_path = dia_dir / "index.html"
    web_path.write_text(web_html, encoding="utf-8")

    email_html = env.get_template("email.html.jinja").render(
        **contexto_comum,
        edicao_url=edicao_url,
        preheader=f"{total_materias} notícias de finanças, política e IA — {data_extenso}",
    )
    email_path = dia_dir / "email.html"
    email_path.write_text(email_html, encoding="utf-8")

    # aponta output/hoje -> edição mais recente, pra sempre ter um link fixo local
    latest_link = OUTPUT_DIR / "hoje.html"
    latest_link.write_text(web_html, encoding="utf-8")

    print(f"[Fase 6] Renderização concluída: {total_materias} matérias em {sum(1 for v in edicao.values() if v)} categorias.")
    print(f"  Web:   {web_path}")
    print(f"  Email: {email_path}")

    log(
        conn,
        fase="fase6_renderizacao",
        status="ok",
        mensagem=f"{total_materias} matérias renderizadas em {web_path}",
    )
