from asyncpg import Connection

from .pool import get_pool
from .schema import STATEMENTS


async def run_schema_setup() -> None:
    pool = get_pool()
    async with pool.acquire() as connection:
        await _apply_statements(connection)


async def _apply_statements(connection: Connection) -> None:
    for statement in STATEMENTS:
        await connection.execute(statement)

