from kafka import KafkaConsumer, KafkaProducer
from market_anomaly.config import app_config

import json

from pydantic import BaseModel, Field
from collections import deque
import logging
from statistics import mean, stdev

logging.basicConfig(
    level=logging.INFO,
    format=logging.BASIC_FORMAT,
)
logger = logging.getLogger(__name__)


class QuoteMessage(BaseModel):
    current_price: float = Field(alias="c")  #
    price_change: float | None = Field(alias="d")  #
    price_change_percent: float | None = Field(alias="dp")  #
    high_price_of_day: float = Field(alias="h")  #
    low_price_of_day: float = Field(alias="l")  #
    open_price_of_day: float = Field(alias="o")  #
    previous_close_price: float = Field(alias="pc")  #
    timestamp: int = Field(alias="t")  #

    def is_valid(self) -> bool:
        return (
            self.current_price > 0
            and self.high_price_of_day > 0
            and self.low_price_of_day > 0
            and self.open_price_of_day > 0
            and self.previous_close_price > 0
            and self.timestamp > 0
            and self.price_change is not None
            and self.price_change_percent is not None
        )


class AnomalyMessage(BaseModel):
    quote_timestamp: int
    symbol: str
    price: float
    price_z_score: float


def key_deserializer(key: bytes) -> str:
    return key.decode(encoding="utf8")


def value_deserializer(value: bytes) -> QuoteMessage:
    return QuoteMessage(**json.loads(value))


def get_consumer():
    consumer_config = (
        app_config.kafka.model_dump() | app_config.raw_ticker_consumer.model_dump()
    )
    return KafkaConsumer(
        "raw_ticks",
        key_deserializer=key_deserializer,
        value_deserializer=value_deserializer,
        **consumer_config,
    )


def add_price_change(
    previous_quote_prices: dict,
    quote_name: str,
    quote_current_price: float,
    price_change_window: deque,
) -> None:
    previous_price = previous_quote_prices.get(quote_name)
    if previous_price:
        price_change_pct = (quote_current_price - previous_price) / previous_price * 100
        price_change_window.append(price_change_pct)
        previous_quote_prices[quote_name] = quote_current_price
    else:
        previous_quote_prices[quote_name] = quote_current_price


def detect_anomaly(quote: str, prices: deque) -> float | None:
    """Detects a tick-to-tick price change anomaly."""

    if len(prices) < app_config.stream.rolling_window_size or len(prices) == 0:
        logger.info(
            "Not enough price change info for quote %s. Continuing without anomaly detection.",
            quote,
        )
        z_score = None
    elif stdev(prices) == 0.0:
        logger.info(
            "Price didn't change for quote %s. Continuing anomaly detection for next tick.",
            quote,
        )
        z_score = None
    else:
        # Anomaly detection logic
        current_value = prices[-1]
        z_score = (current_value - mean(prices)) / stdev(prices)
        is_anomaly = abs(z_score) > app_config.stream.anomaly_z_threshold

        if is_anomaly:
            logger.warning("Detected price change anomaly for quote %s", quote)
        else:
            z_score = None

    return z_score


def get_anomaly_producer() -> KafkaProducer:
    kafka_config = app_config.kafka
    producer_config = app_config.anomaly_producer
    configs = kafka_config.model_dump() | producer_config.model_dump()
    return KafkaProducer(**configs)


def create_anomaly_message(message, z_score: float) -> AnomalyMessage:
    quote = message.value
    return AnomalyMessage(
        quote_timestamp=quote.timestamp,
        symbol=message.key,
        price=quote.current_price,
        price_z_score=z_score,
    )


# TODO - kafka producer related code - extract (valid for KafkaProducer, callbacks)
def on_send_success(record_metadata) -> None:
    logger.info(
        "Successfully published message to topic %s, partition %s, offset %s",
        record_metadata.topic,
        record_metadata.partition,
        record_metadata.offset,
    )


def on_send_error(e) -> None:
    logger.error("Failed to publish message", exc_info=e)


def process_message(message, price_change_window: deque) -> None:
    """Processes quote message"""

    z_score = detect_anomaly(message.key, price_change_window)
    if not z_score:
        pass  # short circuit: in there is no anomaly, then skip

    producer = get_anomaly_producer()
    anomaly_msg = create_anomaly_message(message, z_score)
    producer.send("anomaly", key=message.key, value=anomaly_msg).add_callback(
        on_send_success
    ).add_errback(on_send_error)


def main():

    # Initiate a dictionary where key is quote symbol and value is the last price,
    # from the GET /quote request, initially zero.
    previous_quote_prices = {symbol: 0 for symbol in app_config.stocks.tickers}

    # A windowed queue with N items for price change percent
    price_change_window = deque(maxlen=app_config.stream.rolling_window_size)

    consumer = None

    logger.info("Start processing")
    try:
        consumer = get_consumer()

        for message in consumer:
            quote_name = message.key
            quote_value = message.value
            if not quote_value.is_valid():
                # Skip invalid quotes
                continue

            add_price_change(
                previous_quote_prices,
                quote_name,
                quote_value.current_price,
                price_change_window,
            )

            process_message(message, price_change_window)

    finally:
        if consumer:
            consumer.close()


if __name__ == "__main__":
    main()
    
# TODO - CONTINUE next - loop over all tickers
