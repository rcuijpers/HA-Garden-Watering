# Configuration Reference

All configuration is stored in the HA config entry — no `configuration.yaml` needed.
Options can be changed post-setup via **Settings → Devices & Services → Garden Irrigation → Configure**.

## Config Entry Data Model

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `main_valve` | entity_id | required | Main water supply valve |
| `zones` | list | required | List of zone configs (see below) |
| `weather_entity` | entity_id | required | HA weather entity |
| `precipitation_sensor` | entity_id | None | Override precipitation source |
| `temperature_sensor` | entity_id | None | Override temperature source |
| `rain_threshold` | float | 5.0 | mm — skip watering above this |
| `temp_threshold` | float | 20.0 | °C — urgent watering above this |
| `flow_sensor` | entity_id | None | Flow meter sensor |
| `idle_threshold` | float | 0.5 | L/min — flow below this = idle |
| `leak_detection` | bool | false | Enable background leak checking |
| `leak_check_interval` | int | 5 | Minutes between leak checks |
| `notify_service` | string | required | notify.* service name |
| `evening_advice_time` | string | "20:00" | HH:MM format |
| `morning_start_time` | string | "06:00" | HH:MM format |
| `auto_start` | bool | false | Auto-start when advice ≥ recommended |
| `require_confirmation` | bool | true | Ask before auto-starting |

## Zone Config

Each zone in the `zones` list:

| Key | Type | Description |
|-----|------|-------------|
| `id` | string | Slug, e.g. `zone_1` |
| `name` | string | Display name |
| `type` | string | `drip` \| `sprinkler` \| `other` |
| `flow_entity` | entity_id | Optional zone valve |
| `default_duration` | int | Base duration in minutes |
| `enabled` | bool | Whether this zone is active |

## Duration Override

Zone durations can be changed at runtime via:
- `number.garden_irrigation_duration_{zone_id}` entity in the UI
- Or programmatically via a service call to `number.set_value`

Overrides are stored in entry options under `duration_overrides`.

## Drought & Heat Multipliers

| Parameter | Value |
|-----------|-------|
| Per dry day | +20% (max 3×) |
| Per hot day | +10% (max 2×) |
| Combined cap (drip/other) | 3.5× |
| Combined cap (sprinkler) | 2× — split session suggested above this |

The drought counter resets to 0 after it rains ≥ rain_threshold.
The heat counter resets to 0 when temperature drops below temp_threshold.
Both counters are persisted in `.storage/garden_irrigation_{entry_id}_drought`.
