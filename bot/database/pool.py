import asyncio
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None
_lock = asyncio.Lock()


async def init_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    async with _lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                dsn,
                min_size=5,
                max_size=10,
                command_timeout=5,
                server_settings={
                    "application_name": "povod_bot",
                },
            )
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    async with _lock:
        if _pool is not None:
            await _pool.close()
            _pool = None

