"""Unified Inngest Client for background task orchestration."""
import inngest

# Unified Inngest client shared across CRM, Call Center, Knowledge, and Partner apps
inngest_client = inngest.Inngest(
    app_id="voice-ai-platform",
    api_base_url="http://inngest:8288",
    event_api_base_url="http://inngest:8288",
    is_production=False,
)
