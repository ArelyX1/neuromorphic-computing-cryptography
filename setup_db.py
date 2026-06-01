import asyncio
from puf_crypto.db.config import engine, AsyncSessionLocal
from puf_crypto.db.base import Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tablas creadas en crypto_puf:")
    for table in Base.metadata.tables:
        print(f"  - {table}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
