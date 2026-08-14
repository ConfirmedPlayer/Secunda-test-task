import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI

from app.api import router
from app.broker import broker, setup_topology
from app.outbox import run_relay
from app.security import require_api_key


@asynccontextmanager
async def lifespan(_: FastAPI):
    await broker.connect()
    await setup_topology(broker)
    relay = asyncio.create_task(run_relay(broker))
    try:
        yield
    finally:
        relay.cancel()
        with suppress(asyncio.CancelledError):
            await relay
        await broker.stop()


app = FastAPI(title="Payments", lifespan=lifespan)
app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_api_key)])
