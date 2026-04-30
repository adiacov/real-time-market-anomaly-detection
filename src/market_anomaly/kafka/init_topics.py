import logging

from market_anomaly.config import app_config

from kafka.admin import KafkaAdminClient, NewTopic

logging.basicConfig(
    level=logging.INFO,
    format=logging.BASIC_FORMAT,
)
logger = logging.getLogger(__name__)


def _create_client():
    """Creates a KafkaAdmin client."""
    return KafkaAdminClient(
        bootstrap_servers=app_config.kafka.bootstrap_servers,
        client_id="market-anomaly-kafka-admin-client",
    )


def _handle_response(response) -> None:
    errors = response.topic_errors
    for topic, error_code, error_message in errors:
        if error_code == 0:
            logger.info("Successfully created topic %s", topic)
        else:
            logging.error(
                "Topic creation failed: topic=%s, error_message=%s",
                topic,
                error_message,
            )


def create_topics():
    """Creates topics if these not exists, skip otherwise."""

    client = None

    try:
        client = _create_client()
        existing_topics = set(client.list_topics())

        new_topics = [
            NewTopic(
                name=topic_name,
                num_partitions=topic.num_partitions,
                replication_factor=topic.replication_factor,
            )
            for topic_name, topic in app_config.topics.items()
            if topic_name not in existing_topics
        ]

        if new_topics:
            topic_names = [topic.name for topic in new_topics]
            logger.info("Creating new topics %s", topic_names)

            response = client.create_topics(new_topics)
            _handle_response(response)
        else:
            logger.info("There are no new topics to create. All topics exists already.")

    finally:
        if client:
            client.close()
