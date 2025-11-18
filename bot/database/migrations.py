import logging

from asyncpg import Connection

from .pool import get_pool
from .schema import STATEMENTS

logger = logging.getLogger(__name__)


async def run_schema_setup() -> None:
    pool = get_pool()
    async with pool.acquire() as connection:
        await _apply_statements(connection)


async def _apply_statements(connection: Connection) -> None:
    for i, statement in enumerate(STATEMENTS, 1):
        try:
            await connection.execute(statement)
            logger.debug(f"Migration {i}/{len(STATEMENTS)} applied successfully")
        except Exception as e:
            logger.warning(f"Migration {i}/{len(STATEMENTS)} failed (may already be applied): {e}")
            continue

