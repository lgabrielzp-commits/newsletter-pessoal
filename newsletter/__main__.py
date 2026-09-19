"""Entry point do pipeline da newsletter.

Cada fase é testada em conjunto com as anteriores: por padrão o comando
roda Fase 0 (setup) seguida de todas as fases já implementadas.
"""

from __future__ import annotations

import argparse
import sys

from newsletter.collector import executar_coleta
from newsletter.config import DB_PATH, load_config
from newsletter.db import init_db, log
from newsletter.links import executar_gestao_links


def fase0_setup():
    try:
        config = load_config()
    except Exception as exc:
        print(f"[Fase 0] Falha ao carregar config.yaml: {exc}", file=sys.stderr)
        raise SystemExit(1)

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

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
