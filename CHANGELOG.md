# Changelog

All notable changes to SAJ Monitor are documented in this file.

## 0.1.3 - 2026-05-05

### Added

- Added eSolar SEC/load-monitoring KPI sensors for plants with working plant-level `secData` access:
  - SEC Last Data Time
  - SEC Data Age
  - SEC Load Self Consumed Energy
  - SEC Self Consumption Rate
  - SEC Solar Offset Rate
- Added Estimated TNB ToU NEM Cost Today sensor.
- Added `scripts/check_esolar_sec_openapi.py` for safely probing SAJ eSolar SEC OpenAPI access without printing secrets.

### Changed

- Home Load Power now prefers official eSolar SEC `loadPower` when available.
- Home Load Power exposes source metadata so dashboards and automations can distinguish official SEC data from inverter-derived estimates:
  - `source: sec`, `estimated: false` for SEC load data
  - fallback source values for inverter-derived estimates
- Replaced the previous flat RM/kWh import-cost estimate with a Domestic ToU + NEM model based on bill-derived assumptions.
- Bumped integration version to `0.1.3`.

### Notes

- The TNB ToU/NEM cost sensor is marked as estimated because SAJ SEC currently exposes total daily import/export energy, not peak/off-peak bucketed energy.
- Plant-level `secData` should be used for SEC load monitoring. Realtime/history/device-info APIs should continue to use the inverter/device serial number, not the SEC module serial number.

## 0.1.2 and earlier

- Initial SAJ Monitor Home Assistant custom integration features for SAJ solar inverter and battery monitoring.
- Realtime solar, grid, battery, environmental, and estimated load sensors.
