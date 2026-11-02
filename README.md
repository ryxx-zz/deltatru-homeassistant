# DeltaTru for Home Assistant

Adds your DeltaTru HVAC monitoring to Home Assistant: cloud alerts, system health,
and an automatic **DeltaTru** dashboard built around the ESPHome monitors you already have.

## What you get

For every DeltaTru system on your account a **DeltaTru &lt;system&gt;** device with:

| Entity | Meaning |
|---|---|
| `binary_sensor.*_<family>_alert` (10) | On while the cloud has an open/acknowledged alert of that class (airflow, capacity, short cycling, …) |
| `binary_sensor.*_active_alert` | Any active alert |
| `sensor.*_latest_alert` | Title of the newest active alert (attributes: severity, family, first seen) |
| `sensor.*_system_health` | ok / attention / problem / offline / setup |
| `sensor.*_last_upload` | Last time a monitor reached the cloud |

Data is polled every 5 minutes with your own login; the cloud's row-level security limits it to your systems. Nothing is written to the cloud.

**Automatic extras**

- Your ESPHome monitors (air handler and condenser) are found automatically and shown as connected via the system device. It works with production firmware (`elmer.hvac-monitor-*`, grouped by the firmware's *System ID*) and with dev boards (found by their entities). If you have several systems and a monitor can't be matched, pick its system under **Configure**.
- A **DeltaTru** sidebar dashboard is generated on the fly: an alert banner, tiles, a Delta T gauge, a 24 h history graph and the alert checks. Entity IDs are looked up in the registry, so renaming entities doesn't break it. You can turn it off in the options.
- When a monitor's **Problem** sensor turns on you get a persistent notification showing its Status text. It clears when the problem clears.
- New monitors are discovered over zeroconf, which prompts you to set up DeltaTru.

## Subscription

The ESPHome monitor entities are local and always free. The cloud features (alert sensors, system health, device grouping and the DeltaTru dashboard) need an active DeltaTru subscription. The server enforces this: without one, the integration stays loaded, shows a single *"DeltaTru cloud features need an active subscription"* notice under Settings → Repairs, and puts the same message on the dashboard. The cloud features come back on the next poll after you reactivate.

## Install (HACS)

1. In HACS, open ⋮ → **Custom repositories**, add `https://github.com/ryxx-zz/deltatru-homeassistant` and choose category **Integration**.
2. Search for **DeltaTru**, click **Download**, then restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → DeltaTru** and sign in with your DeltaTru dashboard email and password.

To install by hand, copy `custom_components/deltatru` into `<config>/custom_components/` and restart.

## Development

```bash
uv venv -p 3.14 && uv pip install -r requirements_test.txt
pytest
```
