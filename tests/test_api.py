import os

from sqlalchemy import select

from app.models import OutboxMessage

HEADERS = {"X-API-Key": os.environ["API_KEY"]}


def body(**overrides):
    payload = {
        "amount": "100.50",
        "currency": "RUB",
        "description": "тестовый платёж",
        "metadata": {"order_id": 1},
        "webhook_url": "https://example.com/hook",
    }
    payload.update(overrides)
    return payload


def headers(key: str) -> dict[str, str]:
    return {**HEADERS, "Idempotency-Key": key}


async def test_create_returns_202(client):
    response = await client.post("/api/v1/payments", json=body(), headers=headers("k1"))

    assert response.status_code == 202
    assert response.json()["status"] == "pending"


async def test_create_writes_outbox(client, sessions):
    await client.post("/api/v1/payments", json=body(), headers=headers("k2"))

    async with sessions() as session:
        messages = (await session.scalars(select(OutboxMessage))).all()

    assert len(messages) == 1
    assert messages[0].event_type == "payment.created"
    assert messages[0].published_at is None


async def test_same_key_same_body_returns_same_payment(client):
    first = await client.post("/api/v1/payments", json=body(), headers=headers("k3"))
    second = await client.post("/api/v1/payments", json=body(), headers=headers("k3"))

    assert second.status_code == 202
    assert first.json()["payment_id"] == second.json()["payment_id"]


async def test_same_key_same_body_does_not_duplicate_outbox(client, sessions):
    await client.post("/api/v1/payments", json=body(), headers=headers("k4"))
    await client.post("/api/v1/payments", json=body(), headers=headers("k4"))

    async with sessions() as session:
        messages = (await session.scalars(select(OutboxMessage))).all()

    assert len(messages) == 1


async def test_same_key_other_body_returns_409(client):
    await client.post("/api/v1/payments", json=body(), headers=headers("k5"))
    response = await client.post(
        "/api/v1/payments", json=body(amount="999.00"), headers=headers("k5")
    )

    assert response.status_code == 409


async def test_without_api_key_returns_401(client):
    response = await client.post(
        "/api/v1/payments", json=body(), headers={"Idempotency-Key": "k6"}
    )

    assert response.status_code == 401


async def test_without_idempotency_key_returns_422(client):
    response = await client.post("/api/v1/payments", json=body(), headers=HEADERS)

    assert response.status_code == 422


async def test_unknown_currency_returns_422(client):
    response = await client.post(
        "/api/v1/payments", json=body(currency="GBP"), headers=headers("k7")
    )

    assert response.status_code == 422


async def test_negative_amount_returns_422(client):
    response = await client.post(
        "/api/v1/payments", json=body(amount="-1.00"), headers=headers("k8")
    )

    assert response.status_code == 422


async def test_get_returns_payment(client):
    created = await client.post("/api/v1/payments", json=body(), headers=headers("k9"))
    payment_id = created.json()["payment_id"]

    response = await client.get(f"/api/v1/payments/{payment_id}", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["metadata"] == {"order_id": 1}
    assert response.json()["processed_at"] is None


async def test_get_unknown_returns_404(client):
    response = await client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000", headers=HEADERS
    )

    assert response.status_code == 404
