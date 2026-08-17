# Payments

Сервис асинхронной обработки платежей: принимает платёж по HTTP, обрабатывает его в фоне
через эмуляцию платёжного шлюза и присылает результат вебхуком.

FastAPI, SQLAlchemy 2.0 (asyncio), PostgreSQL, RabbitMQ (FastStream), Alembic.

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

API — `http://localhost:8000` (swagger на `/docs`), панель RabbitMQ — `http://localhost:15672`
(guest / guest). Постгрес на 5433, чтобы не конфликтовать с локальным.

## API

Все запросы — с заголовком `X-API-Key` (значение из `.env`).

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: local-dev-key" \
  -H "Idempotency-Key: order-123" \
  -H "Content-Type: application/json" \
  -d '{"amount": "100.50", "currency": "RUB", "description": "Заказ 123",
       "metadata": {"order_id": 123}, "webhook_url": "https://example.com/hook"}'
```

Ответ `202` с `payment_id`, дальше статус можно смотреть через
`GET /api/v1/payments/{payment_id}` или ждать вебхук:

```json
{"payment_id": "...", "status": "succeeded", "amount": "100.50", "currency": "RUB", "processed_at": "..."}
```

Повтор с тем же `Idempotency-Key` вернёт тот же платёж, с другим телом — `409`.
Сумму лучше передавать строкой.

## Как устроено

- `POST` пишет платёж и событие в таблицу `outbox` одной транзакцией. Фоновый релеер
  (в процессе api) публикует события в RabbitMQ и помечает их отправленными. Если брокер
  недоступен, события копятся в базе.
- Consumer читает платёж из базы, вызывает шлюз (2-5 с, 90% успех), условным `UPDATE`
  ставит статус и шлет вебхук — до 3 попыток с задержками 1/2/4 с. `4xx` (кроме 429)
  не ретраится.
- Повторная доставка сообщения безопасна: если статус уже не `pending`, шлюз не вызывается,
  повторяется только вебхук. Результат шлюза детерминирован по `payment_id`.
- Исчерпал попытки — сообщение реджектится и через `x-dead-letter-exchange` уходит в
  `payments.dlq`. Отказ шлюза — это статус `failed` и штатный вебхук, не DLQ.

## Настройки

`DATABASE_URL`, `RABBITMQ_URL`, `API_KEY` — обязательные. Остальное с дефолтами:
`GATEWAY_DELAY_MIN/MAX` (2/5), `GATEWAY_SUCCESS_RATE` (0.9), `WEBHOOK_TIMEOUT` (5),
`WEBHOOK_MAX_ATTEMPTS` (3), `WEBHOOK_BACKOFF_BASE` (1), `OUTBOX_POLL_INTERVAL` (0.5),
`OUTBOX_BATCH_SIZE` (50).

## Тесты

Ходят в постгрес из compose (база `payments_test`), RabbitMQ не нужен.

```bash
docker compose up -d postgres
uv sync
uv run pytest
```

## Ограничения

Вебхук доставляется at-least-once — при падении consumer'а между отправкой и ack клиент
получит его дважды. Причина ошибки в DLQ не пишется, только в логи. Тесты покрывают API,
consumer и релеер проверялись прогоном в compose.
