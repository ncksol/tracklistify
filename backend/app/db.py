"""Database connection and session management."""

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

load_dotenv()

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _engine


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker  # noqa: PLW0603
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with _get_session_maker()() as session:
        yield session
