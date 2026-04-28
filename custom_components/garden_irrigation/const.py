"""Constants for the Garden Irrigation integration."""
from __future__ import annotations

DOMAIN = "garden_irrigation"
VERSION = "0.1.0"

PLATFORMS = ["sensor", "switch", "button", "number"]

# Config entry keys — Step 1
CONF_MAIN_VALVE = "main_valve"

# Config entry keys — Step 2
CONF_ZONES = "zones"
CONF_ZONE_ID = "id"
CONF_ZONE_NAME = "name"
CONF_ZONE_TYPE = "type"
CONF_ZONE_FLOW_ENTITY = "flow_entity"
CONF_ZONE_DEFAULT_DURATION = "default_duration"
CONF_ZONE_ENABLED = "enabled"

# Config entry keys — Step 3
CONF_WEATHER_ENTITY = "weather_entity"
CONF_PRECIPITATION_SENSOR = "precipitation_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_RAIN_THRESHOLD = "rain_threshold"
CONF_TEMP_THRESHOLD = "temp_threshold"

# Config entry keys — Step 4
CONF_FLOW_SENSOR = "flow_sensor"
CONF_IDLE_THRESHOLD = "idle_threshold"
CONF_LEAK_DETECTION = "leak_detection"
CONF_LEAK_CHECK_INTERVAL = "leak_check_interval"

# Config entry keys — Step 5
CONF_NOTIFY_SERVICE = "notify_service"
CONF_EVENING_ADVICE_TIME = "evening_advice_time"
CONF_MORNING_START_TIME = "morning_start_time"
CONF_AUTO_START = "auto_start"
CONF_REQUIRE_CONFIRMATION = "require_confirmation"

# Zone types
ZONE_TYPE_DRIP = "drip"
ZONE_TYPE_SPRINKLER = "sprinkler"
ZONE_TYPE_OTHER = "other"
ZONE_TYPES = [ZONE_TYPE_DRIP, ZONE_TYPE_SPRINKLER, ZONE_TYPE_OTHER]

# Advice levels
ADVICE_SKIP = "skip"
ADVICE_OPTIONAL = "optional"
ADVICE_RECOMMENDED = "recommended"
ADVICE_URGENT = "urgent"
ADVICE_LEVELS = [ADVICE_SKIP, ADVICE_OPTIONAL, ADVICE_RECOMMENDED, ADVICE_URGENT]

# Session status
STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_LEAK_DETECTED = "leak_detected"

# Defaults
DEFAULT_RAIN_THRESHOLD = 5.0       # mm
DEFAULT_TEMP_THRESHOLD = 20.0      # °C
DEFAULT_IDLE_THRESHOLD = 0.5       # L/min
DEFAULT_LEAK_CHECK_INTERVAL = 5    # minutes
DEFAULT_ZONE_DURATION = 20         # minutes
DEFAULT_EVENING_ADVICE_TIME = "20:00"
DEFAULT_MORNING_START_TIME = "06:00"
DEFAULT_MAX_ZONES = 8

# Drought/heat duration multipliers
DRY_DAY_MULTIPLIER = 0.20          # +20% per dry day
HOT_DAY_MULTIPLIER = 0.10          # +10% per hot day
MAX_DRY_MULTIPLIER = 3.0           # cap: 3× base
MAX_HEAT_MULTIPLIER = 2.0          # cap: 2× base
MAX_COMBINED_MULTIPLIER = 3.5      # overall cap
SPRINKLER_COMBINED_CAP = 2.0       # sprinklers: max 2× to avoid runoff

# Flow verification delay after valve opens (seconds)
FLOW_VERIFY_DELAY = 60

# Coordinator poll interval (seconds)
COORDINATOR_UPDATE_INTERVAL = 300  # 5 minutes

# Storage key prefix for drought state
STORAGE_KEY_DROUGHT = f"{DOMAIN}_{{entry_id}}_drought"
STORAGE_VERSION = 1

# Unique ID prefixes for entities
ENTITY_ADVICE = "advice"
ENTITY_CONSUMPTION_TODAY = "consumption_today"
ENTITY_CONSUMPTION_WEEK = "consumption_week"
ENTITY_LAST_SESSION = "last_session"
ENTITY_STATUS = "status"
ENTITY_DRY_DAYS = "dry_days"
ENTITY_HOT_DAYS = "hot_days"
ENTITY_RECOMMENDED_DURATION = "recommended_duration"
ENTITY_START_ZONE = "start"
ENTITY_STOP_ALL = "stop_all"
ENTITY_AUTO_MODE = "auto_mode"
ENTITY_LEAK_DETECTION = "leak_detection_switch"
ENTITY_DURATION_NUMBER = "duration"
ENTITY_RAIN_THRESHOLD = "rain_threshold"

# Actionable notification action prefixes
ACTION_SKIP_PREFIX = "IRRIGATE_SKIP_"
ACTION_CONFIRM_PREFIX = "IRRIGATE_CONFIRM_"

# Zone morning states
MORNING_STATE_PENDING = "pending"      # no user response yet
MORNING_STATE_SKIP = "skip"            # user pressed Skip
MORNING_STATE_CONFIRMED = "confirmed"  # user pressed Ready

# Attributes
ATTR_REASON = "reason"
ATTR_RECOMMENDED_DURATION = "recommended_duration"
ATTR_DRY_DAYS = "dry_days"
ATTR_HOT_DAYS = "hot_days"
ATTR_ZONE_TYPE = "zone_type"
ATTR_LAST_SESSION_DURATION = "last_session_duration"
ATTR_LAST_SESSION_LITERS = "last_session_liters"
ATTR_SPLIT_SESSION_SUGGESTED = "split_session_suggested"
