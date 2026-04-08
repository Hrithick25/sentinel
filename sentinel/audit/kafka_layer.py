"""
SENTINEL Audit — Kafka Layer
================================
Optional async audit event streaming via Kafka/Redpanda.

When KAFKA_BOOTSTRAP_SERVERS is empty (default), all functions
are safe no-ops. The gateway falls back to direct DB writes.
"""
import asyncio
import logging
from typing import Callable, Optional

from sentinel.config import settings
from sentinel.models import AuditEvent

logger = logging.getLogger("sentinel.kafka")

_producer = None


def _kafka_enabled() -> bool:
    return bool(settings.kafka_bootstrap_servers)


async def init_kafka_producer():
    global _producer
    if not _kafka_enabled():
        logger.info("Kafka disabled (KAFKA_BOOTSTRAP_SERVERS empty)")
        return
    try:
        from aiokafka import AIOKafkaProducer
        _producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await _producer.start()
        logger.info("Kafka producer started: %s", settings.kafka_bootstrap_servers)
    except ImportError:
        logger.warning("aiokafka not installed — pip install sentinel-ai-sdk[kafka]")
    except Exception as e:
        logger.error("Failed to start Kafka producer: %s", e)


async def stop_kafka_producer():
    global _producer
    if _producer:
        await _producer.stop()


async def produce_audit_event(event: AuditEvent) -> bool:
    if not _producer:
        return False
    payload = event.model_dump_json().encode("utf-8")
    try:
        await _producer.send_and_wait("sentinel.audit.events", payload)
        return True
    except Exception as e:
        logger.error("Failed to produce event to Kafka: %s", e)
        return False


async def consume_to_postgres():
    if not _kafka_enabled():
        return
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            "sentinel.audit.events",
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id="postgres_writer_group",
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("Kafka consumer (Postgres writer) started")
    except ImportError:
        logger.warning("aiokafka not installed — skipping Kafka consumer")
        return
    except Exception as e:
        logger.error("Failed to start Postgres consumer: %s", e)
        return

    try:
        from sentinel.audit.logger import AuditLogger
        from sentinel.audit.models import AsyncSessionLocal
        db_writer = AuditLogger()
        async for msg in consumer:
            try:
                event = AuditEvent.model_validate_json(msg.value.decode("utf-8"))
                async with AsyncSessionLocal() as db:
                    await db_writer._write_db(event, db)
            except Exception as e:
                logger.error("Postgres consumer logic error: %s", e)
    finally:
        await consumer.stop()


async def consume_to_websocket(broadcast_callback: Callable):
    if not _kafka_enabled():
        return
    try:
        from aiokafka import AIOKafkaConsumer
        consumer = AIOKafkaConsumer(
            "sentinel.audit.events",
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id="websocket_broadcaster_group",
            auto_offset_reset="latest",
        )
        await consumer.start()
        logger.info("Kafka consumer (WebSocket broadcaster) started")
    except ImportError:
        logger.warning("aiokafka not installed — skipping WS consumer")
        return
    except Exception as e:
        logger.error("Failed to start WS consumer: %s", e)
        return

    try:
        async for msg in consumer:
            try:
                event = AuditEvent.model_validate_json(msg.value.decode("utf-8"))
                await broadcast_callback(event)
            except Exception as e:
                logger.error("WS consumer logic error: %s", e)
    finally:
        await consumer.stop()
