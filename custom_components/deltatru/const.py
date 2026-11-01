"""Constants for the DeltaTru integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "deltatru"
MANUFACTURER: Final = "DeltaTru"

CONF_SUPABASE_URL: Final = "supabase_url"
CONF_ANON_KEY: Final = "anon_key"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_USER_ID: Final = "user_id"
CONF_DEVICE_MAP: Final = "device_map"  # ESPHome device registry id -> system id
CONF_DASHBOARD: Final = "dashboard"
CONF_NOTIFY: Final = "notify_problem"

DEFAULT_SUPABASE_URL: Final = "https://pouvjxctjilvnfzrjjqx.supabase.co"
# Public (anon / publishable) Supabase key. It is the same value the web
# dashboard ships in its JS bundle (NEXT_PUBLIC_SUPABASE_ANON_KEY) and is safe
# to publish; RLS limits every query to the signed-in user's systems.
DEFAULT_ANON_KEY: Final = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBvdXZqeGN0amlsdm5menJqanF4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTIzNTIwMDYsImV4cCI6MjEwNzkyODAwNn0.h-AUfBq2I613VGhHEDTx5AVq80JbfXhpugJx6pq9daY"
)

SCAN_INTERVAL: Final = timedelta(minutes=5)
OFFLINE_AFTER: Final = timedelta(minutes=20)

DASHBOARD_URL: Final = "deltatru"

# Alert families (public.alerts.family check constraint).
ALERT_FAMILIES: Final = (
    "not_running",
    "airflow",
    "capacity",
    "outdoor_side",
    "weak_compressor",
    "wrong_mode",
    "aux_heat",
    "short_cycling",
    "monitor_fault",
    "safety",
)
ACTIVE_ALERT_STATUSES: Final = ("open", "acknowledged")

HEALTH_OK: Final = "ok"
HEALTH_ATTENTION: Final = "attention"
HEALTH_PROBLEM: Final = "problem"
HEALTH_OFFLINE: Final = "offline"
HEALTH_SETUP: Final = "setup"
HEALTH_STATES: Final = [HEALTH_OK, HEALTH_ATTENTION, HEALTH_PROBLEM, HEALTH_OFFLINE, HEALTH_SETUP]

# ESPHome object_ids (slug of the entity name in firmware/) used to recognise
# DeltaTru monitors, including dev boards that have no `project:` block.
AHU_MARKERS: Final = ("delta_t", "blower_amps", "return_air", "supply_air")
COND_MARKERS: Final = ("compressor_amps", "outdoor_air", "contactor_24v_present_y_c")
PROJECT_PREFIX: Final = "hvac-monitor"
