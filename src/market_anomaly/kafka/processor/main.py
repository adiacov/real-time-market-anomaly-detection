from kafka import KafkaConsumer
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

# Sample json with field name, example, description
# {
#   "c": 172.69,  // Current Price
#   "d": 1.21,    // Change (d), previous day close: Price increased by $1.21
#   "dp": 0.7058, // Percent Change (dp), previous day close: Price increased by 0.7058%
#   "h": 173.07,  // High price of the day
#   "l": 170.34,  // Low price of the day
#   "o": 170.57,  // Open price of the day
#   "pc": 171.48, // Previous close price
#   "t": 1699563600 // Timestamp
# }


class Quote(BaseModel):
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


def key_deserializer(key: bytes) -> str:
    return key.decode(encoding="utf8")


def value_deserializer(value: bytes) -> Quote:
    return Quote(**json.loads(value))


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


def detect_anomaly(quote: str, prices: deque) -> bool:
    """Detects a tick-to-tick price change anomaly.

    Returns True if the last price change is an anomaly, False otherwise.
    """

    if len(prices) < app_config.stream.rolling_window_size or len(prices) == 0:
        logger.info(
            "Not enough price change info for quote %s. Continuing without anomaly detection.",
            quote,
        )
        is_anomaly = False
    elif stdev(prices) == 0.0:
        logger.info(
            "Price didn't change for quote %s. Continuing anomaly detection for next tick.",
            quote,
        )
        is_anomaly = False
    else:
        # Anomaly detection logic
        current_value = prices[-1]
        z_score = (current_value - mean(prices)) / stdev(prices)
        is_anomaly = abs(z_score) > app_config.stream.anomaly_z_threshold

        if is_anomaly:
            logger.warning("Detected price change anomaly for quote %s", quote)

    return is_anomaly


def process_message(message, is_anomaly):
    # if anomaly -> publish to the anomaly topic
    pass


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

            # TODO - move anomaly detection to process_message
            is_anomaly = detect_anomaly(quote_name, price_change_window)
            process_message(message, is_anomaly)

    finally:
        if consumer:
            consumer.close()


if __name__ == "__main__":
    main()
