"""Fase 8: entrega por email via Resend.

Sem domínio verificado no Resend, o remetente fica travado em
onboarding@resend.dev e só é possível enviar pro próprio email usado
no cadastro da conta Resend — suficiente pra uma newsletter pessoal de
destinatário único.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from newsletter.config import Config
from newsletter.db import log
from newsletter.render import OUTPUT_DIR, _data_extenso

RESEND_API_URL = "https://api.resend.com/emails"
REMETENTE_PADRAO = "Newsletter <onboarding@resend.dev>"


def _montar_assunto(config: Config, conn: sqlite3.Connection, data_iso: str) -> str:
    data_curta = datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m")
    linhas = conn.execute(
        """
        SELECT m.titulo FROM materias m
        JOIN artigos a ON a.cluster_id = m.cluster_id
        WHERE a.ordem_edicao IS NOT NULL
        GROUP BY m.cluster_id
        ORDER BY MIN(a.ordem_edicao) ASC
        LIMIT 2
        """
    ).fetchall()

    if not linhas:
        return config.entrega.assunto_template.format(data=data_curta)

    destaques = " · ".join(r["titulo"][:45] for r in linhas)
    return f"Newsletter {data_curta}: {destaques}"


def executar_entrega(config: Config, conn: sqlite3.Connection) -> None:
    if not config.secrets.resend_api_key:
        print("[Fase 8] RESEND_API_KEY não definida — pulando entrega.")
        return
    if not config.secrets.recipient:
        print("[Fase 8] NEWSLETTER_RECIPIENT não definido — pulando entrega.")
        return

    agora = datetime.now(ZoneInfo(config.schedule.timezone))
    data_iso = agora.strftime("%Y-%m-%d")
    email_path = OUTPUT_DIR / data_iso / "email.html"

    if not email_path.exists():
        print(f"[Fase 8] {email_path} não existe (rode a Fase 6 antes). Nada a enviar.")
        return

    html = email_path.read_text(encoding="utf-8")
    assunto = _montar_assunto(config, conn, data_iso)

    payload = {
        "from": REMETENTE_PADRAO,
        "to": [config.secrets.recipient],
        "subject": assunto,
        "html": html,
    }

    resp = httpx.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {config.secrets.resend_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    conn.execute(
        """
        INSERT INTO edicoes (data, caminho_html, url_publicada, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(data) DO UPDATE SET
            caminho_html = excluded.caminho_html,
            url_publicada = excluded.url_publicada,
            status = excluded.status
        """,
        (
            data_iso,
            str(email_path),
            f"{config.publicacao.base_url}/{data_iso}/" if config.publicacao.base_url else None,
            "enviado" if resp.status_code < 300 else "falha",
        ),
    )

    if resp.status_code >= 300:
        print(f"[Fase 8] Falha ao enviar ({resp.status_code}): {resp.text}")
        log(conn, fase="fase8_entrega", status="erro", mensagem=f"{resp.status_code}: {resp.text}")
        conn.commit()
        return

    resend_id = resp.json().get("id", "?")
    conn.execute(
        "UPDATE edicoes SET enviado_em = datetime('now') WHERE data = ?", (data_iso,)
    )

    # registra as URLs enviadas hoje pra Fase 4 não repetir a mesma história
    # numa janela de dias (config.curadoria.janela_dedupe_dias)
    edicao_id = conn.execute("SELECT id FROM edicoes WHERE data = ?", (data_iso,)).fetchone()["id"]
    urls_materias = conn.execute("SELECT url FROM materias").fetchall()
    conn.executemany(
        """
        INSERT OR REPLACE INTO urls_enviadas (url_canonica, data_envio, edicao_id)
        VALUES (?, datetime('now'), ?)
        """,
        [(r["url"], edicao_id) for r in urls_materias],
    )
    conn.commit()

    print(f'[Fase 8] Email enviado com sucesso pra {config.secrets.recipient} (assunto: "{assunto}", id Resend: {resend_id})')
    log(conn, fase="fase8_entrega", status="ok", mensagem=f"enviado para {config.secrets.recipient}, resend_id={resend_id}")
