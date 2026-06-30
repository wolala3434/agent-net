"""Database connection and initialisation."""

import logging

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .config import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create tables and run migrations on startup."""
    import os

    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "database", "schema.sql"
    )
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "database", "migrations", "001_fix_domains_index.sql"
    )

    # In production, use Alembic. For MVP we run SQL files directly.
    async with engine.begin() as conn:
        # Run schema
        if os.path.exists(schema_path):
            with open(schema_path) as f:
                for statement in f.read().split(";"):
                    stmt = statement.strip()
                    if stmt and not stmt.startswith("PRAGMA"):
                        try:
                            await conn.exec_driver_sql(stmt)
                        except OperationalError as e:
                            # Ignore "already exists" errors on re-run
                            if "already exists" in str(e).lower():
                                logger.debug(f"Skipping (already exists): {stmt[:60]}...")
                            else:
                                raise

        # Run migration
        if os.path.exists(migration_path):
            with open(migration_path) as f:
                for statement in f.read().split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            await conn.exec_driver_sql(stmt)
                        except OperationalError as e:
                            # Ignore "duplicate column" and "already exists" on re-run
                            msg = str(e).lower()
                            if "duplicate column" in msg or "already exists" in msg:
                                logger.debug(f"Skipping migration (already applied): {stmt[:60]}...")
                            else:
                                raise
