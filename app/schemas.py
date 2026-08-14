from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
Currency = Literal["RUB", "USD", "EUR"]


class PaymentCreate(BaseModel):
    amount: Amount
    currency: Currency
    description: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentAccepted(BaseModel):
    payment_id: UUID
    status: str
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: str
    description: str | None
    metadata: dict[str, Any] = Field(validation_alias="payment_metadata")
    status: str
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
