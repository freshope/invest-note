"""Alembic 환경 — raw SQL 러너(ORM/autogenerate 미사용).

연결 URL은 ``MIGRATION_DATABASE_URL``(없으면 ``DATABASE_URL``)에서 읽는다.
앱 런타임은 asyncpg(평문 ``postgresql://``)를 쓰지만 alembic 은 동기 psycopg v3 로
연결하므로 scheme 을 ``postgresql+psycopg://`` 로 다시 쓴다.

마이그레이션 URL 은 direct 5432 + superuser(postgres) 를 권장한다 — baseline 의
``create extension pg_trgm`` 과 role 조작은 NOSUPERUSER ``invest_note_app`` 권한으로
불가하고, transaction-mode pooler 뒤에서는 alembic 의 버전 테이블 락이 충돌한다.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# raw SQL 러너이므로 autogenerate 대상 메타데이터가 없다.
target_metadata = None


def _load_dotenv_fallback() -> None:
    """로컬 편의: 환경변수가 없을 때만 api/.env.local 에서 마이그레이션 URL 을 읽어온다.

    운영/CI 는 환경변수를 직접 주입하므로 이 경로를 타지 않는다(python-dotenv 의존 없이 최소 파싱).
    """
    if os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL"):
        return
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in ("MIGRATION_DATABASE_URL", "DATABASE_URL") and key not in os.environ:
            os.environ[key] = value.strip()


def _migration_url() -> str:
    _load_dotenv_fallback()
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL 또는 DATABASE_URL 이 필요합니다 "
            "(direct 5432 + superuser 권장)."
        )
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _migration_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
