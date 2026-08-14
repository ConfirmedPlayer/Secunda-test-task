import logging

from faststream import AckPolicy, FastStream
from faststream.rabbit import Channel

from app import gateway, payments, webhooks
from app.broker import broker, payments_exchange, payments_queue, setup_topology
from app.db import session_factory
from app.models import PaymentStatus
from app.schemas import PaymentCreatedEvent

logger = logging.getLogger(__name__)

app = FastStream(broker)


@app.after_startup
async def declare_topology() -> None:
    await setup_topology(broker)


@broker.subscriber(
    payments_queue,
    payments_exchange,
    ack_policy=AckPolicy.REJECT_ON_ERROR,
    # обработка одного платежа занимает секунды, забирать больше десятка разом незачем
    channel=Channel(prefetch_count=10),
)
async def handle_payment_created(event: PaymentCreatedEvent) -> None:
    async with session_factory() as session:
        payment = await payments.get_payment(session, event.payment_id)
        if payment is None:
            # строка outbox пишется в одной транзакции с платежом, так что сюда
            # мы попасть не должны; повторять всё равно нечего
            logger.warning("payment %s not found, skipping", event.payment_id)
            return

        if payment.status == PaymentStatus.PENDING:
            status = await gateway.charge(payment.id)
            payment = await payments.mark_processed(session, payment.id, status)

        await webhooks.deliver(payment)
        logger.info("payment %s processed with status %s", payment.id, payment.status)
