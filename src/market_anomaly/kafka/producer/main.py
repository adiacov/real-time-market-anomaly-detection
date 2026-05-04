from market_anomaly.config import app_config, settings
import signal
import threading
import logging
import json
import requests

from kafka import KafkaProducer

logging.basicConfig(
    level=logging.INFO,
    format=logging.BASIC_FORMAT,
)
logger = logging.getLogger(__name__)

# Shared event used to signal graceful shutdown across the main loop and signal handlers.
stop_event = threading.Event()


def handle_signal(signum, frame):
    """Handle OS termination signals (SIGINT, SIGTERM) by setting the stop event."""
    logger.info("Termination signal received. Setting stop event.")
    stop_event.set()


# Register so both CTRL+C (SIGINT) and process managers (SIGTERM) trigger clean shutdown.
signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def key_serializer(key: str) -> bytes:
    """Serialize a Kafka message key to bytes."""
    return json.dumps(key).encode("utf8")


def get_producer() -> KafkaProducer:
    """Create and return a KafkaProducer configured from application config."""
    kafka_config = app_config.kafka
    producer_config = app_config.raw_ticker_producer
    configs = kafka_config.model_dump() | producer_config.model_dump()
    return KafkaProducer(
        **configs,
        key_serializer=key_serializer,
    )


def fetch_quote(symbol: str) -> bytes | None:
    """Fetch a stock quote from Finnhub for the given symbol.

    Returns the raw response bytes on success, or None if the request fails.
    """
    quote_url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={settings.finnhub_api_key}"
    logger.info(f"Fetching quote data for {symbol} stock")

    try:
        r = requests.get(quote_url, timeout=10)
        r.raise_for_status()
        return r.content
    except requests.exceptions.RequestException as e:
        logger.error("Request failed: {%s}", e)
        return None


def on_send_success(record_metadata) -> None:
    logger.info(
        "Successfully published message to topic %s, partition %s, offset %s",
        record_metadata.topic,
        record_metadata.partition,
        record_metadata.offset,
    )


def on_send_error(e) -> None:
    logger.error("Failed to publish message", exc_info=e)


def publish(producer: KafkaProducer, key: str, message: bytes) -> None:
    """Publish a message to the raw_ticks Kafka topic.

    Args:
        producer: The KafkaProducer instance.
        key: The message key (stock symbol).
        message: The raw message bytes to publish.
    """
    producer.send("raw_ticks", key=key, value=message).add_callback(
        on_send_success
    ).add_errback(on_send_error)


def run(producer: KafkaProducer) -> None:
    """Poll all configured tickers on a fixed interval, publishing quotes to Kafka.

    Fetches quotes for every ticker in each cycle, then waits for the configured
    interval before the next cycle. Skips symbols where fetch fails.
    Runs until a stop signal is received.
    """
    while not stop_event.is_set():
        for quote in app_config.stocks.tickers:
            quote_result = fetch_quote(quote)
            if quote_result is None:
                logger.warning("Skipping publish for %s - fetch failed", quote)
                continue
            publish(producer, quote, quote_result)

        # Blocks for fetch_interval_seconds, but wakes immediately if stop is signaled.
        stop_event.wait(timeout=app_config.stocks.fetch_interval_seconds)


def main() -> None:
    """Entry point. Initializes the producer and starts the polling loop.

    Ensures the producer is flushed and closed on exit regardless of how
    the program terminates.
    """
    producer = get_producer()
    try:
        logger.info("Producer started. Press CTRL+C to stop.")
        run(producer)

    finally:
        logger.info("Flushing and closing producer.")
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()
