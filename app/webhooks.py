import asyncio
import logging

import httpx

from app.config import get_settings
from app.models import Payment

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    pass


def _payload(payment: Payment) -> dict[str, str | None]:
    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
    }


async def deliver(payment: Payment) -> None:
    settings = get_settings()
    payload = _payload(payment)
    reason = "unknown"

    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        for attempt in range(1, settings.webhook_max_attempts + 1):
            try:
                response = await client.post(payment.webhook_url, json=payload)
            except httpx.HTTPError as exc:
                reason = repr(exc)
            else:
                if response.status_code < 400:
                    return
                if response.status_code < 500 and response.status_code != 429:
                    # клиент осознанно отверг payload, повторы ничего не изменят
                    raise WebhookDeliveryError(
                        f"{payment.id}: rejected with {response.status_code}"
                    )
                reason = f"got {response.status_code}"

            logger.warning("webhook %s attempt %s failed: %s", payment.id, attempt, reason)
            if attempt < settings.webhook_max_attempts:
                await asyncio.sleep(settings.webhook_backoff_base * 2 ** (attempt - 1))

    raise WebhookDeliveryError(f"{payment.id}: {reason}")
