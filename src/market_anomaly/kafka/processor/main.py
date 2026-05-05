from kafka import KafkaConsumer
from market_anomaly.config import app_config

import json

from pydantic import BaseModel, Field
from collections import deque


class Quote(BaseModel):
    current_price: float = Field(alias="c")
    price_change: float | None = Field(alias="d")
    price_change_percent: float | None = Field(alias="dp")
    high_price_of_day: float = Field(alias="h")
    low_price_of_day: float = Field(alias="l")
    open_price_of_day: float = Field(alias="o")
    previous_close_price: float = Field(alias="pc")
    timestamp: int = Field(alias="t")

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


def main():

    # Quotes window
    quotes = deque(maxlen=app_config.stream.rolling_window_size)

    print("Start processing")
    consumer = None
    try:
        consumer = get_consumer()

        for message in consumer:
            quote = message.value
            if not quote.is_valid():
                # Skip invalid quotes
                continue

            # print(f"Quote: {quote}")
            # print(f"Quote: is_valid={quote.is_valid()} {quote}")
            quotes.append(quote.current_price)
            # print(f"Quotes size: {len(quotes)}")

    finally:
        if consumer:
            consumer.close()


if __name__ == "__main__":
    main()
