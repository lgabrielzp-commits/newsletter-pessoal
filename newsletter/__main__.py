"""Entry point do pipeline da newsletter.

Cada fase roda isolada: uma falha é registrada e o pipeline segue (pra não
perder a edição inteira por causa de uma etapa), mas o processo termina com
código de saída != 0. Isso é o que faz o workflow do GitHub Actions ficar
VERMELHO — e o GitHub te mandar email — em vez de falhar em silêncio.
"""

from __future__ import annotations

import argparse
import sys
import traceback

from newsletter.clustering import executar_clustering
from newsletter.collector import executar_coleta
from newsletter.config import DB_PATH, load_config
from newsletter.curadoria import executar_curadoria
from newsletter.db import init_db, log, podar
from newsletter.entrega import executar_entrega
from newsletter.extraction import executar_extracao
from newsletter.links import executar_gestao_links
from newsletter.persistencia import restaurar_estado, salvar_estado
from newsletter.publicacao import executar_publicacao
from newsletter.redacao import executar_redacao
from newsletter.render import executar_renderizacao


def fase0_setup():
    try:
        config = load_config()
    except Exception as exc:
        print(f"[Fase 0] Falha ao carregar config.yaml: {exc}", file=sys.stderr)
        raise SystemExit(1)

    conn = init_db(DB_PATH)
    restaurar_estado(config, conn)
    podar(
        conn,
        config.armazenamento.retencao_artigos_dias,
        config.curadoria.janela_dedupe_dias,
    )
    log(conn, fase="fase0_setup", status="ok", mensagem="config e banco inicializados")

    print("[Fase 0] Config carregada com sucesso.")
    print(f"  Categorias: {[c.id for c in config.categorias]}")
    print(f"  Fontes: {[f.id for f in config.fontes]}")
    print(f"  Banco de dados: {DB_PATH}")
    print(f"  ANTHROPIC_API_KEY definida: {config.secrets.anthropic_api_key is not None}")
    print(f"  RESEND_API_KEY definida: {config.secrets.resend_api_key is not None}")

    return config, conn


def main() -> int:
    parser = argparse.ArgumentParser(prog="newsletter")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roda só a Fase 0 (valida config e banco), sem coletar notícias",
    )
    args = parser.parse_args()

    config, conn = fase0_setup()

    if args.dry_run:
        print("[Fase 0] --dry-run: nenhuma outra etapa do pipeline será executada.")
        conn.close()
        return 0

    fases = [
        ("fase1_coleta", lambda: executar_coleta(config, conn)),
        ("fase2_links", lambda: executar_gestao_links(config, conn)),
        ("fase3a_extracao", lambda: executar_extracao(config, conn)),
        ("fase3b_clustering", lambda: executar_clustering(config, conn)),
        ("fase4_curadoria", lambda: executar_curadoria(config, conn)),
        ("fase5_redacao", lambda: executar_redacao(config, conn)),
        ("fase6_renderizacao", lambda: executar_renderizacao(config, conn)),
        ("fase7_publicacao", lambda: executar_publicacao(config, conn)),
        ("fase8_entrega", lambda: executar_entrega(config, conn)),
    ]

    falhas: list[str] = []
    for nome, executar in fases:
        try:
            # fases que podem falhar sem lançar exceção devolvem False
            if executar() is False:
                falhas.append(nome)
        except Exception as exc:
            falhas.append(nome)
            print(f"\n[ERRO] {nome} falhou: {exc!r}", file=sys.stderr)
            traceback.print_exc()
            try:
                log(conn, fase=nome, status="erro", mensagem=repr(exc)[:500])
            except Exception:
                pass

    if not salvar_estado(config, conn):
        falhas.append("persistencia")

    conn.close()

    if falhas:
        print(f"\n[RESULTADO] Pipeline terminou COM FALHAS em: {', '.join(falhas)}",
              file=sys.stderr)
        return 1

    print("\n[RESULTADO] Pipeline completo, todas as fases OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
