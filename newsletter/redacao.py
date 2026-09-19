"""Fase 5: redação com Claude.

Uma chamada ao Sonnet por história selecionada (cluster), recebendo o
texto de TODAS as fontes daquele cluster e devolvendo título, resumo,
texto completo e perspectivas divergentes (quando genuinamente existirem).

Anti-alucinação por construção: a LLM nunca escolhe URL nem nomes de
fonte livremente — o código computa a URL final e a lista de badges a
partir do banco, e qualquer "fonte" citada numa perspectiva que não
bata com uma fonte real do cluster é descartada antes de salvar.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from newsletter.config import Config
from newsletter.db import log

CONCORRENCIA_LLM_MAX = 5
MAX_CHARS_TEXTO_FONTE = 3000

SYSTEM_PROMPT = """\
Você escreve matérias para uma newsletter pessoal de finanças/economia, \
política brasileira e IA/tecnologia. Regras obrigatórias:

- Título: reescreva em português, direto, sem clickbait.
- Resumo: 2-3 linhas — o que aconteceu e por que importa.
- Texto completo: 3-4 parágrafos, na ordem fato → contexto → implicação.
- Traduza conteúdo em inglês (ex. New York Times) para português, mas \
mantenha em inglês termos técnicos cujo uso comum já é em inglês \
(ex. "machine learning", "paper", nomes próprios de produtos).
- NUNCA afirme algo que não esteja no texto-fonte fornecido. Não invente \
números, datas, nomes ou citações.
- Se o texto-fonte for curto (trecho de matéria paga), escreva um resumo \
mais enxuto em vez de complementar com conhecimento próprio.
- "perspectivas": preencha SÓ quando as fontes fornecidas tiverem \
enquadramentos genuinamente diferentes sobre o mesmo fato (ex. um lado \
cobre a crítica, outro a defesa oficial). Se as fontes concordam ou só \
uma fonte foi fornecida, devolva uma lista vazia. Use exatamente o nome \
de fonte como aparece no material — nunca invente um nome de veículo.
"""

TOOL_SCHEMA = {
    "name": "redigir_materia",
    "description": "Registra a matéria redigida para a newsletter",
    "input_schema": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string"},
            "resumo": {"type": "string"},
            "texto_completo": {"type": "string"},
            "perspectivas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fonte": {"type": "string"},
                        "texto": {"type": "string"},
                    },
                    "required": ["fonte", "texto"],
                },
            },
        },
        "required": ["titulo", "resumo", "texto_completo", "perspectivas"],
    },
}


class Perspectiva(BaseModel):
    fonte: str
    texto: str


class MateriaRedigida(BaseModel):
    titulo: str
    resumo: str
    texto_completo: str
    perspectivas: list[Perspectiva] = Field(default_factory=list)


def _montar_prompt_fontes(membros: list[dict]) -> str:
    blocos = []
    for m in membros:
        texto = (m["texto_extraido"] or m["excerpt"] or "")[:MAX_CHARS_TEXTO_FONTE]
        paywall = "sim" if m["paywall_provavel"] else "não"
        blocos.append(
            f"FONTE: {m['fonte_nome']} (paywall: {paywall})\n"
            f"Título original: {m['titulo']}\n"
            f"Texto: {texto}\n"
        )
    return "\n---\n".join(blocos)


async def _redigir_um(
    client: AsyncAnthropic,
    sem: asyncio.Semaphore,
    config: Config,
    cluster_id: int,
    membros: list[dict],
) -> MateriaRedigida | None:
    prompt = _montar_prompt_fontes(membros)

    async with sem:
        try:
            resp = await client.messages.create(
                model=config.modelos.redacao,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                tools=[TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "redigir_materia"},
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            print(f"  [erro] cluster {cluster_id}: {exc!r}")
            return None

        for block in resp.content:
            if block.type == "tool_use":
                try:
                    return MateriaRedigida(**block.input)
                except Exception as exc:
                    print(f"  [erro] cluster {cluster_id}: resposta fora do schema ({exc})")
                    return None
        return None


def _escolher_url_representativa(membros: list[dict]) -> str:
    candidatos = [m for m in membros if m["url_final"]]
    if not candidatos:
        return membros[0]["url_canonica"]
    # prioriza: texto mais completo (matéria que mais embasou a redação)
    return max(
        candidatos, key=lambda m: len(m["texto_extraido"] or m["excerpt"] or "")
    )["url_final"]


async def _redigir_todos(
    config: Config, clusters: dict[int, list[dict]]
) -> dict[int, MateriaRedigida]:
    client = AsyncAnthropic(api_key=config.secrets.anthropic_api_key)
    sem = asyncio.Semaphore(CONCORRENCIA_LLM_MAX)

    tarefas = {
        cluster_id: _redigir_um(client, sem, config, cluster_id, membros)
        for cluster_id, membros in clusters.items()
    }
    resultados = await asyncio.gather(*tarefas.values())
    return {
        cluster_id: r
        for cluster_id, r in zip(tarefas.keys(), resultados)
        if r is not None
    }


def executar_redacao(config: Config, conn: sqlite3.Connection) -> None:
    if not config.secrets.anthropic_api_key:
        print("[Fase 5] ANTHROPIC_API_KEY não definida — pulando redação.")
        return

    linhas = conn.execute(
        """
        SELECT id, cluster_id, categoria, titulo, texto_extraido,
               excerpt, fonte_id, url_final, url_canonica, paywall_provavel
        FROM artigos
        WHERE incluido_na_edicao = 1
        """
    ).fetchall()

    if not linhas:
        print("[Fase 5] Nenhum artigo selecionado (rode a Fase 4 antes). Nada a redigir.")
        return

    # remove matérias de clusters que já não fazem parte da seleção atual
    # (ex.: Haiku reclassificou entre execuções e outra história tomou o lugar)
    cluster_ids_atuais = {row["cluster_id"] for row in linhas}
    if cluster_ids_atuais:
        placeholders = ",".join("?" for _ in cluster_ids_atuais)
        removidas = conn.execute(
            f"DELETE FROM materias WHERE cluster_id NOT IN ({placeholders})",
            tuple(cluster_ids_atuais),
        ).rowcount
        if removidas:
            print(f"[Fase 5] {removidas} matéria(s) de edições anteriores removida(s) (não fazem mais parte da seleção atual).")
        conn.commit()

    nomes_por_fonte = {f.id: f.nome for f in config.fontes}

    clusters: dict[int, list[dict]] = {}
    categoria_por_cluster: dict[int, str] = {}
    for row in linhas:
        membro = dict(row)
        membro["fonte_nome"] = nomes_por_fonte.get(row["fonte_id"], row["fonte_id"])
        clusters.setdefault(row["cluster_id"], []).append(membro)
        categoria_por_cluster[row["cluster_id"]] = row["categoria"]

    print(f"[Fase 5] Redigindo {len(clusters)} matérias com {config.modelos.redacao}...")
    resultados = asyncio.run(_redigir_todos(config, clusters))
    print(f"[Fase 5] Redação concluída: {len(resultados)}/{len(clusters)} matérias com sucesso.")

    for cluster_id, materia in resultados.items():
        membros = clusters[cluster_id]
        nomes_validos = {m["fonte_id"] and nomes_por_fonte.get(m["fonte_id"]) for m in membros}
        badges = sorted({nomes_por_fonte.get(m["fonte_id"], m["fonte_id"]) for m in membros})

        if len(badges) < 2:
            # "perspectivas divergentes" só faz sentido com cobertura cruzada
            # entre VEÍCULOS diferentes. Um cluster com um único veículo (mesmo
            # que apareça em 2 linhas por duplicata de feed) não qualifica —
            # mesmo que o modelo tenha citado o nome da fonte corretamente,
            # não é o "vários jornais, ângulos diferentes" que essa seção promete.
            if materia.perspectivas:
                print(f"  [aviso] cluster {cluster_id}: {len(materia.perspectivas)} "
                      f"perspectiva(s) descartada(s) — só 1 veículo real no cluster")
            perspectivas_validas = []
        else:
            perspectivas_validas = [
                p for p in materia.perspectivas if p.fonte in nomes_validos
            ]
            if len(perspectivas_validas) != len(materia.perspectivas):
                descartadas = len(materia.perspectivas) - len(perspectivas_validas)
                print(f"  [aviso] cluster {cluster_id}: {descartadas} perspectiva(s) com "
                      f"nome de fonte inválido descartada(s)")
        url = _escolher_url_representativa(membros)

        conn.execute(
            """
            INSERT OR REPLACE INTO materias
                (cluster_id, categoria, titulo, resumo, texto_completo, perspectivas, badges, url, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                cluster_id,
                categoria_por_cluster[cluster_id],
                materia.titulo,
                materia.resumo,
                materia.texto_completo,
                json.dumps([p.model_dump() for p in perspectivas_validas], ensure_ascii=False),
                json.dumps(badges, ensure_ascii=False),
                url,
            ),
        )
    conn.commit()

    log(
        conn,
        fase="fase5_redacao",
        status="ok",
        mensagem=f"{len(resultados)}/{len(clusters)} matérias redigidas",
    )
