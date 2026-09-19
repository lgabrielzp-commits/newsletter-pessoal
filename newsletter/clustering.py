"""Fase 3b: dedupe e agrupamento em clusters.

Duas passadas, unidas por union-find:
  1. Título com similaridade alta (rapidfuzz) — pega manchetes quase
     idênticas entre fontes diferentes.
  2. Conteúdo com similaridade de cosseno alta (TF-IDF) — pega a mesma
     história contada com título diferente.

Artigos no mesmo cluster não são descartados: cluster_id > 1 membro é
exatamente o insumo da seção de "perspectivas divergentes" na Fase 5.
"""

from __future__ import annotations

import sqlite3

from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from newsletter.config import Config
from newsletter.db import log


class UnionFind:
    def __init__(self, itens: list[int]):
        self._pai = {item: item for item in itens}

    def find(self, x: int) -> int:
        while self._pai[x] != x:
            self._pai[x] = self._pai[self._pai[x]]
            x = self._pai[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # raiz sempre o menor id, pra dar um cluster_id determinístico
        if ra < rb:
            self._pai[rb] = ra
        else:
            self._pai[ra] = rb

    def grupos(self) -> dict[int, list[int]]:
        grupos: dict[int, list[int]] = {}
        for item in self._pai:
            raiz = self.find(item)
            grupos.setdefault(raiz, []).append(item)
        return grupos


def _clusterizar_por_url_identica(ids: list[int], urls: list[str], uf: UnionFind) -> None:
    """Mesma URL final == garantidamente o mesmo artigo (ex.: apareceu em dois
    feeds da mesma fonte). Sempre seguro fundir, independente de fonte."""
    por_url: dict[str, list[int]] = {}
    for artigo_id, url in zip(ids, urls):
        if url:
            por_url.setdefault(url, []).append(artigo_id)
    for grupo in por_url.values():
        for outro in grupo[1:]:
            uf.union(grupo[0], outro)


def _clusterizar_por_titulo(
    ids: list[int], titulos: list[str], fontes: list[str], limiar: float, uf: UnionFind
) -> None:
    limiar_pct = limiar * 100
    matriz = process.cdist(titulos, titulos, scorer=fuzz.token_sort_ratio)
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            if fontes[i] == fontes[j]:
                # mesma fonte + título "template" parecido (ex.: recaps diários,
                # séries de pesquisa) tende a ser matéria DIFERENTE, não
                # duplicata — URL idêntica já foi tratada acima.
                continue
            if matriz[i][j] >= limiar_pct:
                uf.union(ids[i], ids[j])


def _clusterizar_por_conteudo(
    ids: list[int], textos: list[str], fontes: list[str], limiar: float, uf: UnionFind
) -> None:
    # só considera artigos com texto de verdade (não excerpt curto vazio)
    indices_validos = [i for i, t in enumerate(textos) if t and len(t) > 200]
    if len(indices_validos) < 2:
        return

    corpus = [textos[i] for i in indices_validos]
    vectorizer = TfidfVectorizer(max_df=0.9, min_df=1, stop_words=None)
    try:
        matriz_tfidf = vectorizer.fit_transform(corpus)
    except ValueError:
        return  # vocabulário vazio (textos só com stopwords/pontuação)

    sim = cosine_similarity(matriz_tfidf)
    for a in range(len(indices_validos)):
        for b in range(a + 1, len(indices_validos)):
            ia, ib = indices_validos[a], indices_validos[b]
            if fontes[ia] == fontes[ib]:
                # mesma fonte + títulos parecidos de conteúdo (ex.: pesquisas
                # eleitorais em série, edições sucessivas de uma newsletter)
                # tendem a ser matérias DIFERENTES sobre um tema em andamento,
                # não a mesma história contada duas vezes — não cluster.
                continue
            if sim[a][b] >= limiar:
                uf.union(ids[ia], ids[ib])


def executar_clustering(config: Config, conn: sqlite3.Connection) -> None:
    curadoria = config.curadoria
    # Só a janela de coleta atual. O custo aqui é O(n²) em tempo E em memória
    # (matrizes n×n), então deixar a tabela inteira entrar seria o suficiente
    # pra estourar a RAM do runner conforme o histórico cresce.
    linhas = conn.execute(
        """
        SELECT id, titulo, texto_extraido, excerpt, fonte_id, url_final
        FROM artigos
        WHERE data_coleta >= datetime('now', ?)
        """,
        (f"-{config.coleta.janela_horas} hours",),
    ).fetchall()

    if not linhas:
        print("[Fase 3b] Nenhum artigo no banco para clusterizar.")
        return

    ids = [r["id"] for r in linhas]
    titulos = [r["titulo"] or "" for r in linhas]
    textos = [r["texto_extraido"] or r["excerpt"] or "" for r in linhas]
    fontes = [r["fonte_id"] for r in linhas]
    urls = [r["url_final"] for r in linhas]

    uf = UnionFind(ids)
    _clusterizar_por_url_identica(ids, urls, uf)
    _clusterizar_por_titulo(ids, titulos, fontes, curadoria.limiar_similaridade_titulo, uf)
    _clusterizar_por_conteudo(ids, textos, fontes, curadoria.limiar_similaridade_conteudo, uf)

    grupos = uf.grupos()

    conn.executemany(
        "UPDATE artigos SET cluster_id = ? WHERE id = ?",
        [(raiz, membro) for raiz, membros in grupos.items() for membro in membros],
    )
    conn.commit()

    tamanhos = sorted((len(m) for m in grupos.values()), reverse=True)
    multi = [t for t in tamanhos if t > 1]
    print(f"[Fase 3b] Clustering concluído: {len(ids)} artigos → {len(grupos)} clusters "
          f"({len(multi)} clusters com múltiplas fontes, maior com {tamanhos[0] if tamanhos else 0} artigos).")

    log(
        conn,
        fase="fase3b_clustering",
        status="ok",
        mensagem=f"{len(ids)} artigos em {len(grupos)} clusters, {len(multi)} multi-fonte",
    )
