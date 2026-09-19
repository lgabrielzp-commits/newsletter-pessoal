"""Entry point do pipeline da newsletter.

Cada fase é testada em conjunto com as anteriores: por padrão o comando
roda Fase 0 (setup) seguida de todas as fases já implementadas.
"""

from __future__ import annotations

import argparse
import sys

from newsletter.clustering import executar_clustering
from newsletter.collector import executar_coleta
from newsletter.config import DB_PATH, load_config
from newsletter.curadoria import executar_curadoria
from newsletter.db import init_db, log
from newsletter.extraction import executar_extracao
from newsletter.links import executar_gestao_links
from newsletter.entrega import executar_entrega
from newsletter.persistencia import restaurar_db, salvar_db
from newsletter.publicacao import executar_publicacao
from newsletter.redacao import executar_redacao
from newsletter.render import executar_renderizacao


def fase0_setup():
    try:
        config = load_config()
    except Exception as exc:
        print(f"[Fase 0] Falha ao carregar config.yaml: {exc}", file=sys.stderr)
        raise SystemExit(1)

    restaurar_db(config)
    conn = init_db(DB_PATH)
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

    executar_coleta(config, conn)
    executar_gestao_links(config, conn)
    executar_extracao(config, conn)
    executar_clustering(conn, config.curadoria)
    executar_curadoria(config, conn)
    executar_redacao(config, conn)
    executar_renderizacao(config, conn)
    executar_publicacao(config, conn)
    executar_entrega(config, conn)

    conn.close()
    salvar_db(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
