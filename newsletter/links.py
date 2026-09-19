"""Fase 2: gestão de links.

Para cada artigo novo (url_final IS NULL):
  1. Segue redirects (ex.: wrapper de tracking da Folha) até a URL final
  2. Lê a tag <link rel="canonical"> da página, se existir — geralmente
     é a forma mais limpa da URL (sem variante AMP, sem parâmetros)
  3. Remove parâmetros de tracking (utm_*, fbclid, gclid, etc.)
  4. Grava url_final + http_status no banco

Nunca perde o link: se a resolução falhar, url_final cai de volta para
url_canonica (a URL original do RSS) em vez de ficar vazio.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from newsletter.config import Config
from newsletter.db import log
from newsletter.extraction import extrair_texto
from newsletter.http_utils import RobotsCache, get_limitado

CONCORRENCIA_MAX = 10

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "gclsrc", "mc_cid", "mc_eid", "igshid", "ref_src",
    "spm", "cmpid", "cmp",
    # "s", "from" e "ref" foram removidos da lista: são genéricos demais e
    # alguns sites os usam pra identificar a própria matéria — tirá-los
    # transformava um link bom num 404.
}

_ESQUEMAS_PERMITIDOS = {"http", "https"}


def url_segura(url: str | None) -> bool:
    """Só http/https com host. Barra javascript:, data:, file: etc.

    Sem isso, uma URL vinda de um feed comprometido vira um href ativo na
    página publicada — o autoescape do Jinja escapa HTML, mas não neutraliza
    o esquema de um link.
    """
    if not url:
        return False
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return False
    return partes.scheme.lower() in _ESQUEMAS_PERMITIDOS and bool(partes.netloc)

_CANONICAL_RE = re.compile(
    r"""<link[^>]+rel=["']canonical["'][^>]*href=["']([^"']+)["']""",
    re.IGNORECASE,
)


def _limpar_query(url: str) -> str:
    partes = urlsplit(url)
    query_limpa = [
        (k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(query_limpa), ""))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
async def _get_com_retry(client: httpx.AsyncClient, url: str, max_bytes: int) -> httpx.Response:
    return await get_limitado(client, url, max_bytes)


async def _resolver_um(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    robots: RobotsCache,
    max_bytes: int,
    artigo_id: int,
    url_original: str,
) -> tuple[int, str, int | None, str | None]:
    """Retorna (artigo_id, url_final, http_status, texto). Nunca lança."""
    async with sem:
        if not await robots.permitido(url_original):
            # o link segue válido pro leitor; só não baixamos a página
            return artigo_id, url_original, None, None

        try:
            resp = await _get_com_retry(client, url_original, max_bytes)
        except Exception:
            return artigo_id, url_original, None, None

        url_final = str(resp.url)
        texto = None

        try:
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                html = resp.text
                match = _CANONICAL_RE.search(html[:30000])
                if match:
                    candidato = match.group(1).strip()
                    # só aceita canonical do MESMO host: senão um site
                    # comprometido aponta o link da newsletter pra onde quiser
                    if url_segura(candidato) and urlsplit(candidato).netloc == urlsplit(url_final).netloc:
                        url_final = candidato
                # aproveita o HTML que já está na mão: antes, a Fase 3a
                # baixava a MESMA página de novo (2 requisições por artigo,
                # ~1.350/dia, convite a bloqueio por parte dos jornais)
                texto = extrair_texto(html)
        except Exception:
            pass  # página ilegível não invalida o link

        if not url_segura(url_final):
            url_final = url_original

        return artigo_id, _limpar_query(url_final), resp.status_code, texto


async def _resolver_todos(config: Config, pendentes: list[tuple[int, str]]):
    headers = {"User-Agent": config.coleta.user_agent}
    timeout = httpx.Timeout(config.coleta.timeout_segundos)
    sem = asyncio.Semaphore(CONCORRENCIA_MAX)
    max_bytes = config.coleta.max_bytes_resposta

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        robots = RobotsCache(client, config.coleta.user_agent, config.coleta.respeitar_robots)
        tarefas = [
            _resolver_um(client, sem, robots, max_bytes, artigo_id, url)
            for artigo_id, url in pendentes
        ]
        return await asyncio.gather(*tarefas)


def executar_gestao_links(config: Config, conn: sqlite3.Connection) -> None:
    """Ponto de entrada síncrono usado pelo __main__."""
    pendentes = conn.execute(
        "SELECT id, url_canonica FROM artigos WHERE url_final IS NULL"
    ).fetchall()
    pendentes = [(row["id"], row["url_canonica"]) for row in pendentes]

    if not pendentes:
        print("[Fase 2] Nenhum artigo pendente de resolução de link.")
        return

    resultados = asyncio.run(_resolver_todos(config, pendentes))

    falhas = 0
    extraidos = 0
    for artigo_id, url_final, http_status, texto in resultados:
        if http_status is None:
            falhas += 1
        if texto:
            extraidos += 1
            conn.execute(
                "UPDATE artigos SET url_final = ?, http_status = ?, texto_extraido = ?, "
                "hash_conteudo = ? WHERE id = ?",
                (url_final, http_status, texto,
                 hashlib.sha256(texto.encode("utf-8")).hexdigest(), artigo_id),
            )
        else:
            conn.execute(
                "UPDATE artigos SET url_final = ?, http_status = ? WHERE id = ?",
                (url_final, http_status, artigo_id),
            )
    conn.commit()

    # paywall_provavel: por ora, herda direto da fonte (config.yaml). Um heurístico
    # baseado no tamanho do texto extraído entra na Fase 3, quando tivermos o corpo
    # do artigo via trafilatura.
    fontes_paywall = {f.id for f in config.fontes if f.paywall}
    if fontes_paywall:
        placeholders = ",".join("?" for _ in fontes_paywall)
        conn.execute(
            f"UPDATE artigos SET paywall_provavel = 1 "
            f"WHERE fonte_id IN ({placeholders}) AND paywall_provavel IS NULL",
            tuple(fontes_paywall),
        )
        conn.execute(
            "UPDATE artigos SET paywall_provavel = 0 WHERE paywall_provavel IS NULL"
        )
        conn.commit()

    print(f"[Fase 2] Links resolvidos: {len(resultados)} artigos ({falhas} com falha de rede, "
          f"mantido fallback para a URL original do RSS nesses casos). "
          f"{extraidos} textos já extraídos de brinde (sem segunda requisição).")

    log(
        conn,
        fase="fase2_links",
        status="ok",
        mensagem=f"{len(resultados)} links resolvidos, {falhas} falhas, {extraidos} textos extraídos",
    )
