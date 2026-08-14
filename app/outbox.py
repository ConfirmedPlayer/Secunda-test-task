import asyncio
import logging
from datetime import UTC, datetime

from faststream.rabbit import RabbitBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import ROUTING_KEY, payments_exchange
from app.config import get_settings
from app.db import session_factory
from app.models import OutboxMessage

logger = logging.getLogger(__name__)


async def publish_pending(session: AsyncSession, broker: RabbitBroker) -> int:
    settings = get_settings()
    messages = (
        await session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.published_at.is_(None))
            .order_by(OutboxMessage.created_at)
            .limit(settings.outbox_batch_size)
            # SKIP LOCKED, чтобы две копии релеера не разобрали одну строку
            .with_for_update(skip_locked=True)
        )
    ).all()

    for message in messages:
        await broker.publish(
            {
                "event_id": str(message.id),
                "event_type": message.event_type,
                **message.payload,
            },
            exchange=payments_exchange,
            routing_key=ROUTING_KEY,
            # без persist durable-очередь всё равно потеряет сообщения при рестарте брокера
            persist=True,
        )
        message.published_at = datetime.now(UTC)

    await session.commit()
    return len(messages)


async def run_relay(broker: RabbitBroker) -> None:
    interval = get_settings().outbox_poll_interval
    while True:
        published = 0
        try:
            async with session_factory() as session:
                published = await publish_pending(session, broker)
        except Exception:
            logger.exception("outbox relay iteration failed")
        # спим только когда разбирать нечего, иначе накопившаяся пачка уйдёт сразу
        if published == 0:
            await asyncio.sleep(interval)
