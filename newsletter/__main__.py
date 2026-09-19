"""Entry point do pipeline da newsletter.

Fase 0: apenas valida que config e banco de dados sobem corretamente.
Fases seguintes vão adicionar os passos reais (coleta, extração, redação, etc.)
"""

from __future__ import annotations

import argparse
import sys

from newsletter.config import DB_PATH, load_config
from newsletter.db import init_db, log


def main() -> int:
    parser = argparse.ArgumentParser(prog="newsletter")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida config e banco sem rodar o pipeline completo",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as exc:
        print(f"[Fase 0] Falha ao carregar config.yaml: {exc}", file=sys.stderr)
        return 1

    conn = init_db(DB_PATH)
    log(conn, fase="fase0_setup", status="ok", mensagem="config e banco inicializados")

    print("[Fase 0] Config carregada com sucesso.")
    print(f"  Categorias: {[c.id for c in config.categorias]}")
    print(f"  Fontes: {[f.id for f in config.fontes]}")
    print(f"  Banco de dados: {DB_PATH}")
    print(f"  ANTHROPIC_API_KEY definida: {config.secrets.anthropic_api_key is not None}")
    print(f"  RESEND_API_KEY definida: {config.secrets.resend_api_key is not None}")

    if args.dry_run:
        print("[Fase 0] --dry-run: nenhuma outra etapa do pipeline será executada ainda.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
