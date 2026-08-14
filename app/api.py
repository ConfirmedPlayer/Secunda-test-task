from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import payments
from app.db import get_session
from app.schemas import PaymentAccepted, PaymentCreate, PaymentRead

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create_payment(
    data: PaymentCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> PaymentAccepted:
    payment, created = await payments.create_payment(session, data, idempotency_key)
    if not created and not payments.matches_request(payment, data):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Idempotency-Key already used with a different payload",
        )
    return PaymentAccepted(
        payment_id=payment.id, status=payment.status, created_at=payment.created_at
    )


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment(
    payment_id: UUID, session: AsyncSession = Depends(get_session)
) -> PaymentRead:
    payment = await payments.get_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "payment not found")
    return PaymentRead.model_validate(payment)
