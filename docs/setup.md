# Setup Guide

## Prerequisites

- Home Assistant 2024.1 or newer
- At least one switch or valve entity controlling a water valve
- A weather integration configured in HA (e.g. Met.no, OpenWeatherMap)

## Installation

### Via HACS

1. Ensure HACS is installed: https://hacs.xyz
2. HACS → Integrations → ⋮ → Custom repositories
3. URL: `https://github.com/rcuijpers/ha-garden-watering`, Category: Integration
4. Install **Garden Irrigation**, restart HA

### Manual

```bash
cp -r custom_components/garden_irrigation \
      /config/custom_components/garden_irrigation
```
Restart HA.

## Config Flow Walkthrough

### Step 1 — Main Valve
Select the entity that opens/closes your main water supply. Only `switch.*` and `valve.*` entities are shown.

### Step 2 — Zones
Enter the number of zones (1–8). You will then configure each zone:
- **Name**: Free text, e.g. "Vegetable garden"
- **Type**: `drip`, `sprinkler`, or `other` — affects duration calculation
- **Flow entity**: Optional zone valve / solenoid
- **Default duration**: Base watering time in minutes (can be overridden later via number entity)
- **Enabled**: Uncheck to temporarily disable a zone without deleting it

### Step 3 — Weather
- **Weather entity**: Primary source for forecast rain and temperature
- **Precipitation sensor**: Optional override (takes priority over weather entity)
- **Temperature sensor**: Optional override
- **Rain threshold**: Watering is skipped when forecast rain ≥ this value (default 5 mm)
- **Temperature threshold**: Advice upgrades to `urgent` when temperature ≥ this value (default 20°C)

### Step 4 — Flow Meter (optional)
Skip this step if you don't have a flow meter. With a flow meter you get:
- Water consumption tracking (today / this week)
- Flow verification 60 seconds after a session starts
- Leak detection outside watering hours

### Step 5 — Notifications & Schedule
- **Notification service**: The `notify.*` service to use for alerts
- **Evening advice time**: When to send the daily watering advice (default 20:00)
- **Morning start time**: When auto-start triggers (default 06:00)
- **Auto start**: Automatically water when advice is `recommended` or `urgent`
- **Require confirmation**: Send an actionable notification before starting

## After Setup

- Import automations from `automations/` via **Settings → Automations → Import**
- Import the dashboard from `dashboard/lovelace_dashboard.yaml`
- Adjust zone durations via the `number.garden_irrigation_duration_*` entities
