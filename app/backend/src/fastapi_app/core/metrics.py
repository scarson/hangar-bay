# ABOUTME: Process-global Prometheus instruments that are not per-request (the
# ABOUTME: instrumentator owns HTTP metrics; this module owns job/ingestion gauges).
from prometheus_client import Gauge

last_ingest_success_timestamp = Gauge(
    "hangar_bay_last_ingest_success_timestamp",
    "Unix time of the last aggregation run that committed data (success or partial).",
)
