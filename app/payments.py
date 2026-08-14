import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxMessage, Payment
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
    await session.commit()
    return payment, True


async def get_payment(session: AsyncSession, payment_id: UUID) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.id == payment_id))
