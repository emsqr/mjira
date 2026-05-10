"""OpenTelemetry tracing setup, called once per service at startup.

Each instrumentor is enabled inside its own try/except so a service that
doesn't ship a particular target lib (e.g. notifications has no sqlalchemy)
won't fail to start. Spans go to Jaeger via OTLP gRPC.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = logging.getLogger(__name__)
_initialized = False


def setup_tracing(service_name: str) -> None:
    """Initialize the global tracer provider and enable auto-instrumentors.

    Idempotent — safe to import-then-call from each service's main module.
    Reads OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://jaeger:4317).
    """
    global _initialized
    if _initialized:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

    # Note: FastAPI is NOT instrumented here. Use instrument_fastapi_app(app)
    # after constructing the FastAPI app — global instrument() only patches
    # the class lookup in fastapi.applications, but `from fastapi import
    # FastAPI` has already bound the un-patched class in callers' modules.
    for fn in (
        _instrument_sqlalchemy,
        _instrument_httpx,
        _instrument_pika,
        _instrument_redis,
    ):
        _try(fn)

    _initialized = True
    log.info("tracing enabled for service=%s exporter=%s", service_name, endpoint)


def instrument_fastapi_app(app: "FastAPI") -> None:
    """Per-app FastAPI instrumentation. Call after `app = FastAPI(...)`."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        log.exception("FastAPI app instrumentation failed; continuing")


_OPTIONAL_TARGETS = {"sqlalchemy", "httpx", "pika", "redis"}
_OPTIONAL_INSTRUMENTORS = {f"opentelemetry.instrumentation.{name}" for name in _OPTIONAL_TARGETS}


def _try(fn: Callable[[], None]) -> None:
    try:
        fn()
    except ModuleNotFoundError as exc:
        # Silent only when either the target lib (e.g. sqlalchemy) or its
        # OTel instrumentor isn't installed in this service. Everything else
        # is a real setup problem.
        if exc.name in _OPTIONAL_TARGETS or exc.name in _OPTIONAL_INSTRUMENTORS:
            return
        log.exception("instrumentor %s failed: missing %s", fn.__name__, exc.name)
    except Exception:
        log.exception("instrumentor %s failed; continuing", fn.__name__)


def _instrument_sqlalchemy() -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    SQLAlchemyInstrumentor().instrument()


def _instrument_httpx() -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    HTTPXClientInstrumentor().instrument()


def _instrument_pika() -> None:
    from opentelemetry.instrumentation.pika import PikaInstrumentor
    PikaInstrumentor().instrument()


def _instrument_redis() -> None:
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    RedisInstrumentor().instrument()
