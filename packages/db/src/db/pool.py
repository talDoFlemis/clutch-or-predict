"""
PostgreSQL connection pool module using psycopg3 async.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from psycopg import AsyncConnection, AsyncCursor
from psycopg_pool import AsyncConnectionPool

from conf import get_connection_params


class DatabasePool:
    """
    PostgreSQL async connection pool manager using psycopg3.
    """

    def __init__(
        self,
        min_size: int = 2,
        max_size: int = 10,
        timeout: float = 30.0,
        max_idle: float = 300.0,
    ):
        """
        Initialize the database connection pool.

        Args:
            min_size: Minimum number of connections in the pool
            max_size: Maximum number of connections in the pool
            timeout: Timeout for getting a connection from the pool (seconds)
            max_idle: Maximum idle time for a connection (seconds)
        """
        conn_params = get_connection_params()

        # Build connection string for psycopg3
        conninfo = (
            f"host={conn_params['host']} "
            f"port={conn_params['port']} "
            f"user={conn_params['user']} "
            f"password={conn_params['password']} "
            f"dbname={conn_params['dbname']} "
            f"sslmode={conn_params['sslmode']}"
        )

        self.pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            max_idle=max_idle,
            open=False,  # Will be opened with async open()
        )

    async def open(self):
        """Open the connection pool asynchronously."""
        await self.pool.open()

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        Get a connection from the pool as an async context manager.

        Yields:
            AsyncConnection: Database connection
        """
        async with self.pool.connection() as conn:
            yield conn

    @asynccontextmanager
    async def get_cursor(self, row_factory=None) -> AsyncGenerator[AsyncCursor, None]:
        """
        Get a cursor from a pooled connection as an async context manager.

        Args:
            row_factory: Optional row factory (e.g., dict_row for dict results)

        Yields:
            AsyncCursor: Database cursor
        """
        async with self.pool.connection() as conn:
            if row_factory:
                cursor = conn.cursor(row_factory=row_factory)
            else:
                cursor = conn.cursor()
            try:
                yield cursor
            finally:
                await cursor.close()

    async def close(self):
        """
        Close the connection pool and all connections asynchronously.
        """
        await self.pool.close()

    async def __aenter__(self):
        """Support using DatabasePool as an async context manager."""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the pool when exiting async context."""
        await self.close()


# Global pool instance (optional - for convenience)
_global_pool: DatabasePool | None = None


async def get_pool(
    min_size: int = 2,
    max_size: int = 10,
    timeout: float = 30.0,
    max_idle: float = 300.0,
) -> DatabasePool:
    """
    Get or create the global database pool instance.

    Args:
        min_size: Minimum number of connections in the pool
        max_size: Maximum number of connections in the pool
        timeout: Timeout for getting a connection from the pool (seconds)
        max_idle: Maximum idle time for a connection (seconds)

    Returns:
        DatabasePool: The global database pool instance
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = DatabasePool(
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            max_idle=max_idle,
        )
        await _global_pool.open()
    return _global_pool


async def close_pool():
    """Close the global database pool if it exists."""
    global _global_pool
    if _global_pool is not None:
        await _global_pool.close()
        _global_pool = None
