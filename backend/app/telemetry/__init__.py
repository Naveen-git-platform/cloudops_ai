"""OpenTelemetry (OTLP/HTTP) ingestion and storage.

Kept separate from the service/integration registry: telemetry is keyed by
the `service.name` resource attribute reported by instrumented apps, which
may or may not match a registered service.
"""
