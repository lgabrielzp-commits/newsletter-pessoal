"""Carrega config.yaml e variáveis de ambiente (.env) em modelos tipados."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
DB_PATH = ROOT_DIR / "data" / "newsletter.db"


class Categoria(BaseModel):
    id: str
    nome: str


class FeedFonte(BaseModel):
    url: str
    categorias: list[str] = Field(default_factory=list)


class Fonte(BaseModel):
    id: str
    nome: str
    peso: float = 1.0
    paywall: bool = False
    feeds: list[FeedFonte] = Field(default_factory=list)

    @property
    def categorias(self) -> list[str]:
        """União das categorias de todos os feeds — usado só como fallback
        grosseiro; a categoria real do artigo vem do feed que o originou."""
        vistas: list[str] = []
        for feed in self.feeds:
            for cat in feed.categorias:
                if cat not in vistas:
                    vistas.append(cat)
        return vistas


class ColetaConfig(BaseModel):
    janela_horas: int = 48
    timeout_segundos: int = 15
    max_tentativas: int = 3
    user_agent: str = "NewsletterPessoalBot/0.1"


class CuradoriaConfig(BaseModel):
    max_noticias_por_categoria: int = 5
    candidatos_pre_filtro_por_categoria: int = 20
    janela_dedupe_dias: int = 7
    limiar_similaridade_titulo: float = 0.90
    limiar_similaridade_conteudo: float = 0.75


class ModelosConfig(BaseModel):
    triagem: str
    redacao: str


class ScheduleConfig(BaseModel):
    hora: str = "06:00"
    timezone: str = "America/Sao_Paulo"
    frequencia: str = "diaria"


class PublicacaoConfig(BaseModel):
    base_url: str = ""
    branch: str = "gh-pages"


class ArmazenamentoConfig(BaseModel):
    branch: str = "dados"


class EntregaConfig(BaseModel):
    metodo: str = "email"
    assunto_template: str = "Newsletter — {data}"


class DesignConfig(BaseModel):
    cor_primaria: str = "#c41e3a"
    cor_fundo_header: str = "#1a1a1a"


class Secrets(BaseModel):
    anthropic_api_key: str | None = None
    resend_api_key: str | None = None
    recipient: str | None = None


class Config(BaseModel):
    categorias: list[Categoria]
    fontes: list[Fonte]
    coleta: ColetaConfig
    curadoria: CuradoriaConfig
    modelos: ModelosConfig
    schedule: ScheduleConfig
    publicacao: PublicacaoConfig
    entrega: EntregaConfig
    design: DesignConfig
    armazenamento: ArmazenamentoConfig = Field(default_factory=ArmazenamentoConfig)
    secrets: Secrets = Field(default_factory=Secrets)

    def fontes_por_categoria(self, categoria_id: str) -> list[Fonte]:
        return [f for f in self.fontes if categoria_id in f.categorias]


def load_config(config_path: Path | None = None, env_path: Path | None = None) -> Config:
    load_dotenv(dotenv_path=env_path or (ROOT_DIR / ".env"))

    path = config_path or CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    secrets = Secrets(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        resend_api_key=os.getenv("RESEND_API_KEY") or None,
        recipient=os.getenv("NEWSLETTER_RECIPIENT") or None,
    )

    return Config(**raw, secrets=secrets)
