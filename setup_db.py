import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from puf_crypto.db.config import engine
from puf_crypto.db.base import Base

import api.infrastructure.db.models  # noqa: registers all models on Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tablas creadas en crypto_puf:")
    for table in Base.metadata.tables:
        print(f"  - {table}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
