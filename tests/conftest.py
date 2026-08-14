import os

# выставляем до импорта приложения, иначе Settings соберётся на боевых значениях
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://payments:payments@localhost:5433/payments_test"
)
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("API_KEY", "test-key")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.models import Base


@pytest.fixture
async def sessions():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(sessions):
    async def override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override
    # ASGITransport не запускает lifespan, поэтому к rabbitmq тесты не ходят
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
