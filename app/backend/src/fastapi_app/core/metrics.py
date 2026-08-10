# ABOUTME: Process-global Prometheus instruments that are not per-request (the
# ABOUTME: instrumentator owns HTTP metrics; this module owns job/ingestion gauges).
from prometheus_client import Counter, Gauge

last_ingest_success_timestamp = Gauge(
    "hangar_bay_last_ingest_success_timestamp",
    "Unix time of the last aggregation run that committed data (success or partial).",
)

# Contracts ingestion declined to persist. A skip is silent data loss — a real listing
# the site will not show — so it needs a signal that does not require reading logs, and
# one an alert can be hung on. Labelled by reason from the start: a label set cannot be
# widened later without breaking every recorded series.
contracts_skipped_total = Counter(
    "hangar_bay_ingest_contracts_skipped_total",
    "Contracts dropped during ingestion rather than persisted, by reason.",
    ["reason"],
)
