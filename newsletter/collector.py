"""Fase 1: coleta de notícias via RSS.

Busca todos os feeds configurados em config.yaml, normaliza cada entrada
(título, URL canônica, fonte, data de publicação, excerpt), filtra pela
janela de horas configurada e grava no SQLite (tabela `artigos`).
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from newsletter.config import Config, Fonte
from newsletter.db import log


@dataclass
class ArtigoBruto:
    url_canonica: str
    titulo: str
    fonte_id: str
    data_publicacao: datetime | None
    excerpt: str


def _parse_data(entry: dict) -> datetime | None:
    """feedparser expõe published_parsed/updated_parsed como struct_time em UTC."""
    for campo in ("published_parsed", "updated_parsed"):
        struct = entry.get(campo)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    # fallback: tenta parsear a string bruta (alguns feeds têm formato não padrão)
    for campo in ("published", "updated"):
        valor = entry.get(campo)
        if valor:
            try:
                dt = parsedate_to_datetime(valor)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                continue
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _fetch_feed(client: httpx.AsyncClient, url: str) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    # bytes crus: feedparser lê a declaração de encoding do próprio XML
    # (ex. ISO-8859-1 no feed da Folha) melhor do que a heurística do httpx.
    return resp.content


async def _coletar_fonte(
    client: httpx.AsyncClient, fonte: Fonte, janela: timedelta
) -> tuple[str, list[ArtigoBruto], list[str]]:
    """Retorna (fonte_id, artigos_dentro_da_janela, erros)."""
    artigos: list[ArtigoBruto] = []
    erros: list[str] = []
    agora = datetime.now(timezone.utc)

    for feed_url in fonte.feeds:
        try:
            conteudo = await _fetch_feed(client, feed_url)
        except Exception as exc:  # noqa: BLE001 — queremos seguir coletando as outras fontes
            erros.append(f"{feed_url}: {exc!r}")
            continue

        parsed = feedparser.parse(conteudo)
        for entry in parsed.entries:
            link = entry.get("link")
            titulo = entry.get("title")
            if not link or not titulo:
                continue

            data_pub = _parse_data(entry)
            if data_pub is not None and (agora - data_pub) > janela:
                continue  # fora da janela de coleta

            excerpt = entry.get("summary", "") or entry.get("description", "")
            artigos.append(
                ArtigoBruto(
                    url_canonica=link.strip(),
                    titulo=titulo.strip(),
                    fonte_id=fonte.id,
                    data_publicacao=data_pub,
                    excerpt=excerpt.strip(),
                )
            )

    return fonte.id, artigos, erros


async def coletar_tudo(config: Config) -> tuple[list[ArtigoBruto], dict[str, list[str]]]:
    """Coleta todas as fontes em paralelo. Retorna (artigos, erros_por_fonte)."""
    janela = timedelta(hours=config.coleta.janela_horas)
    headers = {"User-Agent": config.coleta.user_agent}
    timeout = httpx.Timeout(config.coleta.timeout_segundos)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        tarefas = [_coletar_fonte(client, fonte, janela) for fonte in config.fontes]
        resultados = await asyncio.gather(*tarefas)

    todos_artigos: list[ArtigoBruto] = []
    erros_por_fonte: dict[str, list[str]] = {}
    for fonte_id, artigos, erros in resultados:
        todos_artigos.extend(artigos)
        if erros:
            erros_por_fonte[fonte_id] = erros

    return todos_artigos, erros_por_fonte


def salvar_artigos(conn: sqlite3.Connection, artigos: list[ArtigoBruto]) -> tuple[int, int]:
    """Insere artigos novos no banco (ignora duplicados por url_canonica).

    Retorna (novos, ja_existentes).
    """
    novos = 0
    existentes = 0
    for artigo in artigos:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO artigos
                (url_canonica, titulo, fonte_id, data_publicacao, excerpt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                artigo.url_canonica,
                artigo.titulo,
                artigo.fonte_id,
                artigo.data_publicacao.isoformat() if artigo.data_publicacao else None,
                artigo.excerpt,
            ),
        )
        if cur.rowcount:
            novos += 1
        else:
            existentes += 1
    conn.commit()
    return novos, existentes


def executar_coleta(config: Config, conn: sqlite3.Connection) -> list[ArtigoBruto]:
    """Ponto de entrada síncrono usado pelo __main__."""
    artigos, erros = asyncio.run(coletar_tudo(config))
    novos, existentes = salvar_artigos(conn, artigos)

    por_fonte: dict[str, int] = {}
    for a in artigos:
        por_fonte[a.fonte_id] = por_fonte.get(a.fonte_id, 0) + 1

    print(f"[Fase 1] Coleta concluída: {len(artigos)} artigos dentro da janela de "
          f"{config.coleta.janela_horas}h ({novos} novos, {existentes} já existiam no banco).")
    for fonte in config.fontes:
        qtd = por_fonte.get(fonte.id, 0)
        marca = " ⚠️ erro" if fonte.id in erros else ""
        print(f"  {fonte.nome:25s} {qtd:4d} artigos{marca}")

    if erros:
        for fonte_id, lista_erros in erros.items():
            for e in lista_erros:
                print(f"  [erro] {fonte_id}: {e}")
                log(conn, fase="fase1_coleta", status="erro", mensagem=f"{fonte_id}: {e}")

    log(
        conn,
        fase="fase1_coleta",
        status="ok",
        mensagem=f"{len(artigos)} artigos coletados, {novos} novos, {len(erros)} fontes com erro",
    )
    return artigos
