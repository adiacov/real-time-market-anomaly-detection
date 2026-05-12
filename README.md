# Real-Time Market Anomaly Detection

## Table of Contents

- [Problem Statement](#problem)
- [License](#license)

## Problem

Build a system that watches real market data for 5–10 stocks (configurable), detects unusual patterns
(anomalies) in price and volume, and uses an AI agent to explain what happened and why.

## Technical Decisions & Architecture Design

### 1. Asynchronous Event-Driven Storage Pattern

Instead of writing data to PostgreSQL directly during the HTTP ingestion phase, the architecture handles storage asynchronously via Kafka consumers.

- **Decoupling:** Decouples external API rates from database connection limits.
- **Resilience:** Prevents data loss during downstream database maintenance or connection bottlenecks.

### 2. Processing and Execution Sequence

#### Flow A: Quote Pipeline (Ingestion to Storage)

1. **Fetch:** Ingest raw payload via Finnhub HTTP client.
2. **Identity Generation:** Generate a unique `quote_id` (UUID) within the ingestion script.
3. **Stream:** Publish the payload with its explicit UUID to the `quotes` Kafka topic.
4. **Persist:** The Quote Consumer processes the topic stream and commits records to `public.quote`.

#### Flow B: Anomaly Pipeline (Analysis to Storage)

1. **Consume:** The Analytics Engine consumes data from the `quotes` Kafka topic.
2. **Evaluate:** Calculate price Z-scores against historical distributions.
3. **Stream Anomaly:** If anomalies are flagged, serialize and publish an event to the `anomalies` Kafka topic.
4. **Persist:** The Anomaly Consumer processes the topic stream and commits records to `public.anomaly`.

### 3. Transaction and Delivery Guarantees

Database persistence occurs **strictly after** the respective Kafka producers successfully confirm message delivery. This prevents data state mismatches where a record is permanently committed to PostgreSQL, but a sudden system crash prevents the event from being broadcasted to the rest of the microservices network.

### 4. Intentional Data De-normalization for Real-Time UI

The `public.anomaly` table intentionally violates standard 3NF (Third Normal Form) database normalization by duplicating the `symbol` and `price` fields from the `public.quote` table.

- **The Problem:** Real-time dashboard UIs poll the database frequently to display active anomalies. If the `anomaly` table were normalized, every dashboard fetch would require a relational `JOIN` operation back to the `quote` table to retrieve basic information like the ticker symbol and asset price.
- **The Solution:** By duplicating `symbol` and `price` directly into the `anomaly` record at the insertion phase, the system achieves **O(1) lookups** for UI queries.
- **The Tradeoff:** We sacrifice minimal storage efficiency to completely eliminate CPU-heavy `JOIN` overhead on the PostgreSQL engine, guaranteeing near-real-time rendering speeds for the UI layer.

## License

This project is licensed under the [MIT License](LICENSE).
