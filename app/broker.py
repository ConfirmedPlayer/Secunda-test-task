from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import get_settings

ROUTING_KEY = "payments.new"
DEAD_ROUTING_KEY = "payments.dead"

broker = RabbitBroker(get_settings().rabbitmq_url)

payments_exchange = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
dlx_exchange = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)

payments_queue = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key=ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": DEAD_ROUTING_KEY,
    },
)

dlq_queue = RabbitQueue("payments.dlq", durable=True, routing_key=DEAD_ROUTING_KEY)


async def setup_topology(broker: RabbitBroker) -> None:
    """Объявляет обменники, очереди и привязки.

    Вызывается и в api, и в consumer: объявление идемпотентно, а если очередь
    заведёт только consumer, то на холодном старте релеер успеет опубликовать
    событие в обменник без привязок, и оно молча пропадёт.
    """
    payments_ex = await broker.declare_exchange(payments_exchange)
    dlx = await broker.declare_exchange(dlx_exchange)

    queue = await broker.declare_queue(payments_queue)
    await queue.bind(payments_ex, ROUTING_KEY)

    dead = await broker.declare_queue(dlq_queue)
    await dead.bind(dlx, DEAD_ROUTING_KEY)
