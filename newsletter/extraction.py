"""Fase 3a: extração de texto completo de cada matéria.

Busca o HTML de cada artigo (url_final, status 200) e usa trafilatura
para extrair o corpo do texto, descartando menu/anúncio/rodapé. Para
fontes com paywall, o que sobra costuma ser só o trecho público — é
esperado e compensado na Fase 5 (redação) com o excerpt do RSS.
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3

import httpx
import trafilatura
from tenacity import retry, stop_after_attempt, wait_exponential

from newsletter.config import Config
from newsletter.db import log
from newsletter.http_utils import RobotsCache, get_limitado

CONCORRENCIA_MAX = 10


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=6))
async def _get_com_retry(client: httpx.AsyncClient, url: str, max_bytes: int) -> httpx.Response:
    return await get_limitado(client, url, max_bytes)


def extrair_texto(html: str) -> str | None:
    """Extrai o corpo do artigo. Nunca lança — HTML malformado vira None."""
    try:
        return trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception:
        return None


async def _extrair_um(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    robots: RobotsCache,
    max_bytes: int,
    artigo_id: int,
    url: str,
) -> tuple[int, str | None]:
    async with sem:
        if not await robots.permitido(url):
            return artigo_id, None

        # tudo dentro do try: antes, o resp.text e o trafilatura ficavam de
        # fora e qualquer erro ali subia pelo asyncio.gather e derrubava o
        # pipeline inteiro (sem email, sem publicação, sem salvar estado).
        try:
            resp = await _get_com_retry(client, url, max_bytes)
            if resp.status_code != 200:
                return artigo_id, None
            return artigo_id, extrair_texto(resp.text)
        except Exception:
            return artigo_id, None


async def _extrair_todos(config: Config, pendentes: list[tuple[int, str]]) -> list[tuple[int, str | None]]:
    headers = {"User-Agent": config.coleta.user_agent}
    timeout = httpx.Timeout(config.coleta.timeout_segundos)
    sem = asyncio.Semaphore(CONCORRENCIA_MAX)
    max_bytes = config.coleta.max_bytes_resposta

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        robots = RobotsCache(client, config.coleta.user_agent, config.coleta.respeitar_robots)
        tarefas = [
            _extrair_um(client, sem, robots, max_bytes, artigo_id, url)
            for artigo_id, url in pendentes
        ]
        return await asyncio.gather(*tarefas)


def executar_extracao(config: Config, conn: sqlite3.Connection) -> None:
    pendentes = conn.execute(
        """
        SELECT id, url_final FROM artigos
        WHERE texto_extraido IS NULL AND http_status = 200 AND url_final IS NOT NULL
        """
    ).fetchall()
    pendentes = [(row["id"], row["url_final"]) for row in pendentes]

    if not pendentes:
        print("[Fase 3a] Nenhum artigo pendente de extração de texto.")
        return

    resultados = asyncio.run(_extrair_todos(config, pendentes))

    extraidos = 0
    vazios = 0
    for artigo_id, texto in resultados:
        if texto:
            hash_conteudo = hashlib.sha256(texto.encode("utf-8")).hexdigest()
            conn.execute(
                "UPDATE artigos SET texto_extraido = ?, hash_conteudo = ? WHERE id = ?",
                (texto, hash_conteudo, artigo_id),
            )
            extraidos += 1
        else:
            vazios += 1
    conn.commit()

    print(f"[Fase 3a] Extração concluída: {extraidos} artigos com texto, "
          f"{vazios} sem texto extraível (paywall forte, bloqueio ou página não-HTML).")

    log(
        conn,
        fase="fase3a_extracao",
        status="ok",
        mensagem=f"{extraidos} extraídos, {vazios} vazios de {len(pendentes)} pendentes",
    )
