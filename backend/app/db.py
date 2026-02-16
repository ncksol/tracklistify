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


def _get_database_url() -> str:
    """Get database URL, using managed identity token if available."""
    # If explicit DATABASE_URL is set, use it (local dev)
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Cloud: build URL from components + AAD token
    host = os.getenv("POSTGRES_HOST")
    db = os.getenv("POSTGRES_DB", "tracklistify")
    if not host:
        raise ValueError("Either DATABASE_URL or POSTGRES_HOST must be set")

    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
    # The username for Entra auth is the managed identity name
    user = os.getenv("POSTGRES_USER", "tracklistify-backend-api")
    return f"postgresql+asyncpg://{user}:{token}@{host}/{db}?ssl=require"


def _get_engine() -> AsyncEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        url = _get_database_url()
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
