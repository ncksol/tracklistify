"""Application Insights monitoring configuration."""

import logging
import os

from opencensus.ext.azure.log_exporter import AzureLogHandler  # type: ignore[import-untyped]
from opencensus.ext.azure.trace_exporter import AzureExporter  # type: ignore[import-untyped]
from opencensus.trace.samplers import ProbabilitySampler  # type: ignore[import-untyped]
from opencensus.trace.tracer import Tracer  # type: ignore[import-untyped]


def setup_monitoring() -> None:
    """Configure Azure Application Insights monitoring.

    Configures trace and log exporters if APPLICATIONINSIGHTS_CONNECTION_STRING
    is set in the environment. Skips setup gracefully if not configured.
    """
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string or connection_string.startswith("your_"):
        return

    try:
        # Configure trace exporter for request/dependency tracking
        _ = Tracer(
            exporter=AzureExporter(connection_string=connection_string),
            sampler=ProbabilitySampler(1.0),
        )

        # Configure logger exporter for log forwarding
        logger = logging.getLogger()
        logger.addHandler(AzureLogHandler(connection_string=connection_string))
        logger.setLevel(logging.INFO)
    except ValueError:
        # Invalid connection string — skip monitoring
        return
