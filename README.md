# Garden Irrigation for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

[![Open your Home Assistant instance and add a custom repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rcuijpers&repository=HA-Garden-Watering&category=integration)

A fully UI-configurable Home Assistant custom integration for smart garden watering. No YAML required — configure everything through the HA interface.

## Features

- **5-step setup wizard** — main valve, zones, weather, flow meter, notifications
- **Up to 8 watering zones** — drip, sprinkler, or other types
- **Smart advice engine** — calculates skip / optional / recommended / urgent per zone
- **Drought & heat tracking** — adjusts recommended duration based on consecutive dry and hot days
- **Zone-type aware durations** — drip systems get full multiplier; sprinklers are capped at 2× to prevent runoff
- **Flow meter support** — consumption tracking and leak detection
- **Graceful degradation** — works without optional sensors
- **Dutch & English** translations

## Installation

### HACS (recommended)

1. Open HACS → Integrations → Custom repositories
2. Add `https://github.com/rcuijpers/ha-garden-watering` as Integration
3. Install "Garden Irrigation"
4. Restart Home Assistant

### Manual

1. Copy `custom_components/garden_irrigation/` to your HA `custom_components/` folder
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Garden Irrigation**
3. Follow the 5-step wizard:
   - **Step 1**: Select your main water valve (switch or valve entity)
   - **Step 2**: Configure watering zones (1–8)
   - **Step 3**: Select weather entity and set thresholds
   - **Step 4**: Optionally configure a flow meter
   - **Step 5**: Set notification service and schedule

## Watering Advice Logic

The coordinator calculates advice every 5 minutes:

| Level | Condition |
|-------|-----------|
| `skip` | Forecast rain ≥ rain threshold |
| `optional` | 0 dry days and temperature below threshold |
| `recommended` | 1–2 dry days or temperature above threshold |
| `urgent` | ≥3 dry days, or ≥2 dry days + ≥2 hot days |

### Duration Multipliers

Recommended watering duration is adjusted based on drought/heat:

- **+20% per dry day** (max 3× base duration)
- **+10% per hot day** (max 2× base duration)
- **Combined cap**: 3.5× for drip, 2× for sprinklers (to avoid runoff — a split-session notification is shown instead)

## Entities Created

### Sensors
| Entity | Description |
|--------|-------------|
| `sensor.garden_irrigation_advice_{zone}` | Advice level per zone |
| `sensor.garden_irrigation_recommended_duration_{zone}` | Recommended duration (minutes) |
| `sensor.garden_irrigation_status` | idle / running / leak_detected |
| `sensor.garden_irrigation_dry_days` | Consecutive dry days |
| `sensor.garden_irrigation_hot_days` | Consecutive hot days |
| `sensor.garden_irrigation_consumption_today` | Water used today (L) |
| `sensor.garden_irrigation_consumption_week` | Water used this week (L) |
| `sensor.garden_irrigation_last_session` | Timestamp of last session |

### Controls
| Entity | Description |
|--------|-------------|
| `switch.garden_irrigation_start_{zone}` | Start/stop a specific zone |
| `button.garden_irrigation_stop_all` | Emergency stop all zones |
| `switch.garden_irrigation_auto_mode` | Enable automatic watering |
| `switch.garden_irrigation_leak_detection_switch` | Enable leak detection |
| `number.garden_irrigation_duration_{zone}` | Adjust zone duration |
| `number.garden_irrigation_rain_threshold` | Adjust rain threshold |

## Automations

Import the ready-made automations from the `automations/` folder:

- `evening_advice.yaml` — daily evening notification with tomorrow's advice
- `morning_start.yaml` — auto-start based on advice level
- `rain_cancel.yaml` — cancel active session when rain threshold is exceeded
- `leak_detection.yaml` — urgent alert when leak is detected

## Dashboard

Import `dashboard/lovelace_dashboard.yaml` as a new Lovelace view.

## Requirements

- Home Assistant 2024.1+
- Python 3.11+
- A water valve controllable by HA (switch or valve domain)
- A weather entity configured in HA

## License

MIT
