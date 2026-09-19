"""Helpers HTTP: download com teto de tamanho e checagem de robots.txt."""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx


class RespostaGrandeDemais(Exception):
    """A resposta passou do teto de bytes configurado."""


async def get_limitado(client: httpx.AsyncClient, url: str, max_bytes: int) -> httpx.Response:
    """GET que aborta se o corpo passar de `max_bytes`.

    Sem isso, uma única página gigante (ou um servidor mal-intencionado
    mandando bytes indefinidamente) consome memória do runner até travar.
    """
    async with client.stream("GET", url) as resp:
        corpo = bytearray()
        async for chunk in resp.aiter_bytes():
            corpo.extend(chunk)
            if len(corpo) > max_bytes:
                raise RespostaGrandeDemais(f"{url} passou de {max_bytes} bytes")
        resp._content = bytes(corpo)
    return resp


class RobotsCache:
    """Consulta robots.txt uma vez por host e guarda o resultado.

    Política: se o robots.txt não puder ser lido (404, timeout, erro), libera
    o acesso — é o comportamento padrão e evita derrubar a coleta inteira por
    causa de um servidor instável.
    """

    def __init__(self, client: httpx.AsyncClient, user_agent: str, habilitado: bool = True):
        self._client = client
        self._user_agent = user_agent
        self._habilitado = habilitado
        self._cache: dict[str, RobotFileParser | None] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _carregar(self, base: str) -> RobotFileParser | None:
        try:
            resp = await self._client.get(f"{base}/robots.txt", timeout=10)
            if resp.status_code != 200:
                return None
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
        except Exception:
            return None

    async def permitido(self, url: str) -> bool:
        if not self._habilitado:
            return True

        partes = urlsplit(url)
        base = f"{partes.scheme}://{partes.netloc}"

        if base not in self._cache:
            lock = self._locks.setdefault(base, asyncio.Lock())
            async with lock:
                if base not in self._cache:  # outra corrotina pode ter carregado
                    self._cache[base] = await self._carregar(base)

        parser = self._cache[base]
        if parser is None:
            return True
        try:
            return parser.can_fetch(self._user_agent, url)
        except Exception:
            return True
