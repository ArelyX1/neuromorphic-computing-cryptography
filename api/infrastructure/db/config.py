import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env")

ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://arelyxl:elmomero123@localhost:5432/crypto_puf")

if ASYNC_DATABASE_URL and not ASYNC_DATABASE_URL.startswith("postgresql+asyncpg://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

SYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("+asyncpg", "", 1)

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)
SyncSessionLocal = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_db():
    with SyncSessionLocal() as session:
        yield session
