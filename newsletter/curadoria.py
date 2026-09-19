"""Fase 4: curadoria e ranking.

1. Agrupa artigos já clusterizados (Fase 3) em objetos Cluster.
2. Calcula um score heurístico: peso da fonte × recência × cobertura
   multi-fonte. Usa isso só pra cortar o volume antes de gastar tokens.
3. Manda os melhores candidatos por categoria pro Haiku classificar
   (categoria final, se é notícia substantiva ou clickbait/fofoca, e
   uma nota de relevância).
4. Corta para as N melhores por categoria (config.curadoria.max_noticias_por_categoria)
   e marca no banco (artigos.categoria, artigos.incluido_na_edicao).
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from newsletter.config import Config
from newsletter.db import log

CONCORRENCIA_LLM_MAX = 5


@dataclass
class Cluster:
    cluster_id: int
    membro_ids: list[int]
    fontes: set[str]
    titulo_repr: str
    texto_repr: str
    data_mais_recente: datetime | None
    categorias_candidatas: set[str]
    score_heuristico: float = 0.0


class TriagemResultado(BaseModel):
    categoria: str
    substantiva: bool
    relevancia: int = Field(ge=1, le=10)


def _montar_clusters(conn: sqlite3.Connection, config: Config) -> list[Cluster]:
    linhas = conn.execute(
        """
        SELECT id, cluster_id, titulo, texto_extraido, excerpt, fonte_id,
               data_publicacao, categorias_feed
        FROM artigos
        """
    ).fetchall()

    por_cluster: dict[int, list[sqlite3.Row]] = {}
    for row in linhas:
        por_cluster.setdefault(row["cluster_id"], []).append(row)

    clusters = []
    for cluster_id, membros in por_cluster.items():
        # representante: quem tem o texto mais completo (mais contexto pro Haiku/redação)
        representante = max(membros, key=lambda r: len(r["texto_extraido"] or r["excerpt"] or ""))

        fontes = {m["fonte_id"] for m in membros}
        # hint de categoria vem do FEED RSS de origem de cada membro, não da
        # fonte inteira — uma notícia de política da Folha não deve "vazar"
        # pro pool de IA só porque a Folha, no geral, também cobre IA.
        categorias_candidatas: set[str] = set()
        for m in membros:
            if m["categorias_feed"]:
                categorias_candidatas.update(m["categorias_feed"].split(","))

        datas = [
            datetime.fromisoformat(m["data_publicacao"])
            for m in membros
            if m["data_publicacao"]
        ]
        data_mais_recente = max(datas) if datas else None

        clusters.append(
            Cluster(
                cluster_id=cluster_id,
                membro_ids=[m["id"] for m in membros],
                fontes=fontes,
                titulo_repr=representante["titulo"],
                texto_repr=(representante["texto_extraido"] or representante["excerpt"] or "")[:4000],
                data_mais_recente=data_mais_recente,
                categorias_candidatas=categorias_candidatas or {"financas"},
            )
        )
    return clusters


def _score_heuristico(cluster: Cluster, config: Config) -> float:
    fontes_por_id = {f.id: f for f in config.fontes}
    peso_fonte = max((fontes_por_id[f].peso for f in cluster.fontes if f in fontes_por_id), default=1.0)

    if cluster.data_mais_recente:
        agora = datetime.now(timezone.utc)
        horas_atras = (agora - cluster.data_mais_recente).total_seconds() / 3600
        janela = config.coleta.janela_horas
        recencia = max(0.1, 1 - horas_atras / janela)
    else:
        recencia = 0.5  # sem data: nem penaliza nem favorece

    multi_fonte_boost = 1 + 0.25 * (len(cluster.fontes) - 1)

    return peso_fonte * recencia * multi_fonte_boost


def _pre_filtrar(clusters: list[Cluster], config: Config) -> list[Cluster]:
    k = config.curadoria.candidatos_pre_filtro_por_categoria
    candidatos_ids: set[int] = set()

    for categoria in config.categorias:
        pool = [c for c in clusters if categoria.id in c.categorias_candidatas]
        pool.sort(key=lambda c: c.score_heuristico, reverse=True)
        for c in pool[:k]:
            candidatos_ids.add(c.cluster_id)

    return [c for c in clusters if c.cluster_id in candidatos_ids]


async def _classificar_um(
    client: AsyncAnthropic, sem: asyncio.Semaphore, config: Config, cluster: Cluster
) -> tuple[int, TriagemResultado | None]:
    categorias_validas = [c.id for c in config.categorias]
    prompt = (
        f"Título: {cluster.titulo_repr}\n\n"
        f"Texto: {cluster.texto_repr}\n\n"
        f"Fontes que cobriram: {', '.join(sorted(cluster.fontes))}"
    )

    async with sem:
        try:
            resp = await client.messages.create(
                model=config.modelos.triagem,
                max_tokens=200,
                system=(
                    "Você classifica notícias para uma newsletter pessoal de "
                    "finanças/economia, política brasileira e IA/tecnologia. "
                    "Marque substantiva=false para clickbait, colunismo de opinião "
                    "raso, fofoca de celebridade ou conteúdo irrelevante às três "
                    "editorias. relevancia é de 1 (irrelevante) a 10 (essencial "
                    "saber hoje)."
                ),
                tools=[{
                    "name": "classificar_noticia",
                    "description": "Classifica uma notícia para curadoria da newsletter",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "categoria": {"type": "string", "enum": categorias_validas},
                            "substantiva": {"type": "boolean"},
                            "relevancia": {"type": "integer", "minimum": 1, "maximum": 10},
                        },
                        "required": ["categoria", "substantiva", "relevancia"],
                    },
                }],
                tool_choice={"type": "tool", "name": "classificar_noticia"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            return cluster.cluster_id, None

        for block in resp.content:
            if block.type == "tool_use":
                try:
                    return cluster.cluster_id, TriagemResultado(**block.input)
                except Exception:
                    return cluster.cluster_id, None
        return cluster.cluster_id, None


async def _classificar_todos(
    config: Config, candidatos: list[Cluster]
) -> dict[int, TriagemResultado]:
    client = AsyncAnthropic(api_key=config.secrets.anthropic_api_key)
    sem = asyncio.Semaphore(CONCORRENCIA_LLM_MAX)

    tarefas = [_classificar_um(client, sem, config, c) for c in candidatos]
    resultados = await asyncio.gather(*tarefas)

    return {cid: resultado for cid, resultado in resultados if resultado is not None}


def executar_curadoria(config: Config, conn: sqlite3.Connection) -> None:
    if not config.secrets.anthropic_api_key:
        print("[Fase 4] ANTHROPIC_API_KEY não definida — pulando curadoria.")
        return

    clusters = _montar_clusters(conn, config)
    for c in clusters:
        c.score_heuristico = _score_heuristico(c, config)

    candidatos = _pre_filtrar(clusters, config)
    print(f"[Fase 4] {len(clusters)} clusters totais → {len(candidatos)} candidatos "
          f"pré-filtrados enviados para triagem (Haiku).")

    resultados = asyncio.run(_classificar_todos(config, candidatos))
    print(f"[Fase 4] Triagem concluída: {len(resultados)}/{len(candidatos)} classificados com sucesso.")

    # combina: score final = score heurístico normalizado * relevância do LLM, filtra não-substantivas
    finais_por_categoria: dict[str, list[tuple[Cluster, float, TriagemResultado]]] = {
        c.id: [] for c in config.categorias
    }
    por_id = {c.cluster_id: c for c in candidatos}

    for cluster_id, resultado in resultados.items():
        if not resultado.substantiva:
            continue
        if resultado.categoria not in finais_por_categoria:
            continue
        cluster = por_id[cluster_id]
        score_final = cluster.score_heuristico * resultado.relevancia
        finais_por_categoria[resultado.categoria].append((cluster, score_final, resultado))

    # limpa seleção anterior (idempotente entre execuções)
    conn.execute("UPDATE artigos SET incluido_na_edicao = NULL, ordem_edicao = NULL")

    max_por_categoria = config.curadoria.max_noticias_por_categoria
    for categoria_id, itens in finais_por_categoria.items():
        itens.sort(key=lambda x: x[1], reverse=True)
        escolhidos = itens[:max_por_categoria]

        print(f"\n  === {categoria_id} ({len(escolhidos)} escolhidas de {len(itens)} substantivas) ===")
        for posicao, (cluster, score, resultado) in enumerate(escolhidos, start=1):
            print(f"    [{score:6.2f}] (rel={resultado.relevancia}, {len(cluster.fontes)} fonte(s)) {cluster.titulo_repr[:70]}")

            conn.executemany(
                "UPDATE artigos SET categoria = ?, incluido_na_edicao = 1, ordem_edicao = ? WHERE id = ?",
                [(categoria_id, posicao, mid) for mid in cluster.membro_ids],
            )
    conn.commit()

    total_escolhidas = sum(len(v[:max_por_categoria]) for v in finais_por_categoria.values())
    log(
        conn,
        fase="fase4_curadoria",
        status="ok",
        mensagem=f"{len(candidatos)} candidatos, {len(resultados)} classificados, "
                 f"{total_escolhidas} histórias escolhidas para a edição",
    )
