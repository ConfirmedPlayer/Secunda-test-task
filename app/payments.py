import uuid
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxMessage, Payment, PaymentStatus
from app.schemas import PaymentCreate


async def create_payment(
    session: AsyncSession, data: PaymentCreate, idempotency_key: str
) -> tuple[Payment, bool]:
    # id генерим сами: строка outbox пишется в этой же транзакции, и id нужен
    # до flush, иначе в payload уедет None
    payment = Payment(
        id=uuid.uuid4(),
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        payment_metadata=data.metadata,
        webhook_url=str(data.webhook_url),
        idempotency_key=idempotency_key,
    )
    session.add(payment)
    session.add(
        OutboxMessage(
            event_type="payment.created",
            payload={"payment_id": str(payment.id)},
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # ключ уже занят, платёж создал предыдущий запрос
        await session.rollback()
        existing = await get_by_idempotency_key(session, idempotency_key)
        if existing is None:
            raise
        return existing, False
    return payment, True


async def get_payment(session: AsyncSession, payment_id: UUID) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.id == payment_id))


async def get_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.idempotency_key == key))


async def mark_processed(
    session: AsyncSession, payment_id: UUID, status: PaymentStatus
) -> Payment | None:
    # условие по статусу защищает от гонки с параллельной доставкой того же события
    await session.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
        .values(status=status, processed_at=func.now())
    )
    await session.commit()
    return await get_payment(session, payment_id)


def matches_request(payment: Payment, data: PaymentCreate) -> bool:
    return (
        payment.amount == data.amount
        and payment.currency == data.currency
        and payment.description == data.description
        and payment.payment_metadata == data.metadata
        and payment.webhook_url == str(data.webhook_url)
    )
