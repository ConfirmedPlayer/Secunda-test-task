import asyncio
import random
from uuid import UUID

from app.config import get_settings
from app.models import PaymentStatus


async def charge(payment_id: UUID) -> PaymentStatus:
    """Эмуляция внешнего платёжного шлюза.

    Результат детерминирован по payment_id: настоящий шлюз идемпотентен по ключу
    запроса, иначе падение consumer'а между списанием и записью статуса означало
    бы повторное списание при следующей доставке сообщения.
    """
    settings = get_settings()
    rng = random.Random(str(payment_id))
    await asyncio.sleep(rng.uniform(settings.gateway_delay_min, settings.gateway_delay_max))
    if rng.random() < settings.gateway_success_rate:
        return PaymentStatus.SUCCEEDED
    return PaymentStatus.FAILED
